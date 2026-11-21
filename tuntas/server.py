"""Local JSON API and static web app for the TUNTAS prototype (standard library only).

Run: python serve.py            (http://127.0.0.1:8765, learner app)
     python serve.py --port 9000 --db data/tuntas.db
Teacher view: /teacher. Optional AI phrasing: set TUNTAS_PHRASER=claude (see tutor.py).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import bkt, engine, tutor
from .graph import CONCEPTS, LABELS
from .mathcheck import MathInputError
from .messages import LANGUAGES, STEP_LABELS, render
from .store import Store

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "tuntas.db"
MAX_BODY_BYTES = 4096
MAX_DRAIN_BYTES = 65536
# Striped locks: one learner action at a time per session, so a double submit cannot lose an update.
_SESSION_LOCKS = [threading.Lock() for _ in range(64)]
CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{2,20}")
SESSION_PATTERN = re.compile(r"[0-9a-f]{32}")

# Explicit file map: nothing outside these paths is ever served, so no path traversal is possible.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/teacher": ("teacher.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/common.js": ("common.js", "text/javascript; charset=utf-8"),
    "/static/teacher.js": ("teacher.js", "text/javascript; charset=utf-8"),
    "/static/styles.css": ("styles.css", "text/css; charset=utf-8"),
}
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def session_view(session: dict, state: engine.SessionState, messages: list[str] | None = None,
                 lang: str | None = None) -> dict:
    lang = lang if lang in LANGUAGES else session["lang"]
    kind, key, args = engine.prompt(state)
    current = state.return_to if state.step == "remediate" else state.step
    steps = []
    for step in engine.FLOW:
        if step in state.completed:
            status = "done"
        elif step in state.skipped:
            status = "skipped"
        elif step == current:
            status = "current"
        else:
            status = "locked"
        steps.append({"key": step, "label": STEP_LABELS[lang][step], "status": status})
    return {
        "session_id": session["id"],
        "lang": lang,
        "problem": state.problem.display(),
        "step": state.step,
        "step_label": STEP_LABELS[lang][state.step],
        "steps": steps,
        "prompt": {"kind": kind, "text": render(lang, key, args)},
        "messages": messages or [],
        "mastery": [
            {"concept": c, "label": LABELS[lang][c], "p": round(state.mastery[c], 2),
             "mastered": state.mastery[c] >= bkt.MASTERY_THRESHOLD}
            for c in reversed(CONCEPTS)
        ],
        "threshold": bkt.MASTERY_THRESHOLD,
        "hints_used": state.hints_used,
        "hints_left": engine.MAX_HINTS_PER_ITEM - state.item_hints if kind in ("pair", "expression", "roots") else 0,
        "flagged": bool(state.flags),
        "done": state.step == "done",
    }


def class_view(store: Store, class_code: str, lang: str) -> dict:
    learners = []
    for row in store.class_summary(class_code):
        state = engine.SessionState.from_dict(row["state"])
        completed = len(state.completed)
        learners.append({
            "learner_code": row["learner_code"],
            "updated_at": row["updated_at"],
            "problem": state.problem.display(),
            "step_label": STEP_LABELS[lang][state.step],
            "done": state.step == "done",
            "hints_used": state.hints_used,
            "hint_dependency": round(state.hints_used / completed, 2) if completed else None,
            "flags": [{"concept_label": LABELS[lang][f["concept"]], "step_label": STEP_LABELS[lang][f["step"]]} for f in state.flags],
            # Only concepts this session actually scored: an untested concept still sits at P(L0) and is not "weak".
            "weakest": min(
                ({"label": LABELS[lang][c], "p": round(state.mastery[c], 2)} for c in state.assessed),
                key=lambda m: m["p"],
                default=None,
            ),
        })
    return {"class_code": class_code, "lang": lang, "threshold": bkt.MASTERY_THRESHOLD, "learners": learners}


class Handler(BaseHTTPRequestHandler):
    server_version = "TUNTAS/0.3"
    store: Store  # set by make_server
    phraser: tutor.Phraser | None = None
    _body_read = True

    # --- plumbing ---------------------------------------------------------------
    def _send(self, status: HTTPStatus, body: bytes, content_type: str, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, err: ApiError) -> None:
        self._json(err.status, {"error": {"code": err.code, "message": err.message}})

    def _drain_body(self) -> None:
        """Read an unread request body before answering, so the client is not reset mid-send (Windows RST)."""
        if self._body_read:
            return
        self._body_read = True
        try:
            length = max(0, int(self.headers.get("Content-Length") or 0))
        except ValueError:
            length = MAX_DRAIN_BYTES + 1
        if length > MAX_DRAIN_BYTES:
            self.close_connection = True
            return
        self.rfile.read(length)

    def _read_json(self) -> dict:
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type", "Send JSON with Content-Type: application/json.")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_length", "Invalid Content-Length.") from None
        if length < 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_length", "Invalid Content-Length.")
        if length > MAX_BODY_BYTES:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large", "Request body is too large.")
        self._body_read = True
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_json", "Request body is not valid JSON.") from None
        if not isinstance(data, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_json", "Request body must be a JSON object.")
        return data

    def log_message(self, fmt: str, *args) -> None:  # quieter than the default, still one line per request
        print(f"{self.address_string()} {fmt % args}")

    # --- routing ----------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        self._guarded(self._route_get)

    def do_POST(self) -> None:  # noqa: N802
        self._guarded(self._route_post)

    def _guarded(self, route) -> None:
        self._body_read = self.command != "POST"
        try:
            route(self.path.split("?", 1)[0])
        except ApiError as err:
            self._drain_body()
            self._error(err)
        except Exception:  # noqa: BLE001 - never drop the connection without an answer
            traceback.print_exc()
            self._drain_body()
            self._error(ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", "Unexpected server error."))

    def _route_get(self, path: str) -> None:
        if path in STATIC_FILES:
            name, ctype = STATIC_FILES[path]
            self._send(HTTPStatus.OK, (WEB_DIR / name).read_bytes(), ctype, cache="no-cache")
        elif m := re.fullmatch(r"/api/sessions/([0-9a-f]{32})", path):
            session, state = self._load(m.group(1))
            self._json(HTTPStatus.OK, session_view(session, state, lang=self._query_lang(session["lang"])))
        elif m := re.fullmatch(r"/api/classes/([A-Za-z0-9_-]{2,20})", path):
            self._json(HTTPStatus.OK, class_view(self.store, m.group(1), self._query_lang("en")))
        else:
            raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "Not found.")

    def _route_post(self, path: str) -> None:
        if path == "/api/sessions":
            self._create_session(self._read_json())
        elif m := re.fullmatch(r"/api/sessions/([0-9a-f]{32})/(answer|hint|continue)", path):
            body = self._read_json()
            with _SESSION_LOCKS[hash(m.group(1)) % len(_SESSION_LOCKS)]:
                session, state = self._load(m.group(1))
                self._act(session, state, m.group(2), body)
        else:
            raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "Not found.")

    # --- actions ----------------------------------------------------------------
    def _query_lang(self, default: str) -> str:
        m = re.search(r"[?&]lang=(en|id)\b", self.path)
        return m.group(1) if m else default

    def _load(self, session_id: str) -> tuple[dict, engine.SessionState]:
        session = self.store.get_session(session_id)
        if session is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "session_not_found", "Session not found.")
        return session, engine.SessionState.from_dict(session["state"])

    def _create_session(self, body: dict) -> None:
        class_code = str(body.get("class_code", "")).strip()
        learner_code = str(body.get("learner_code", "")).strip()
        lang = body.get("lang") if body.get("lang") in LANGUAGES else "en"
        problem = str(body.get("problem", ""))
        if not CODE_PATTERN.fullmatch(class_code) or not CODE_PATTERN.fullmatch(learner_code):
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_code",
                           "Class and learner codes use 2 to 20 letters, digits, - or _.")
        try:
            state, outcome = engine.start(problem, self.store.prior_mastery(class_code, learner_code))
        except MathInputError as exc:
            code = "out_of_scope" if str(exc) == "out of scope" else "unreadable_problem"
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, code, str(exc)) from None
        session_id = self.store.create_session(class_code, learner_code, lang, state.to_dict())
        self.store.log_event(session_id, state.step, "start")
        session = self.store.get_session(session_id)
        messages = tutor.speak(self.phraser, lang, "diagnose", outcome.messages)
        self._json(HTTPStatus.CREATED, session_view(session, state, messages))

    def _act(self, session: dict, state: engine.SessionState, action: str, body: dict) -> None:
        step_before = state.step
        if action == "answer":
            text = body.get("text")
            if not isinstance(text, str) or not text.strip() or len(text) > 200:
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_answer", "Send a non-empty answer of at most 200 characters.")
            outcome = engine.submit(state, text)
        elif action == "hint":
            outcome = engine.hint(state)
        else:
            outcome = engine.continue_after_review(state)
        self.store.save_turn(session["id"], state.to_dict(), step_before, action, verdict=outcome.verdict,
                             concept=outcome.concept, p_before=outcome.p_before, p_after=outcome.p_after,
                             scored=outcome.scored, flagged=outcome.flagged,
                             mastery_owner=(session["class_code"], session["learner_code"]) if outcome.scored else None)
        lang = body.get("lang") if body.get("lang") in LANGUAGES else session["lang"]
        messages = tutor.speak(self.phraser, lang, step_before, outcome.messages)
        self._json(HTTPStatus.OK, session_view(session, state, messages, lang))


def make_server(host: str, port: int, db_path: str | Path, phraser: tutor.Phraser | None = None) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"store": Store(db_path), "phraser": phraser})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the TUNTAS prototype locally.")
    parser.add_argument("--host", default="127.0.0.1", help="Use 0.0.0.0 only on a trusted classroom network.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    phraser = tutor.phraser_from_env()
    server = make_server(args.host, args.port, args.db, phraser)
    print(f"TUNTAS running at http://{args.host}:{args.port}  (teacher view: /teacher)")
    print(f"Tutor voice: {'Claude phrasing with leak guard' if phraser else 'fixed templates'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
