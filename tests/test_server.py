import http.client
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from tuntas.server import make_server


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = make_server("127.0.0.1", 0, Path(cls.tmp.name) / "test.db")
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def request(self, method, path, body=None, raw=None, content_type="application/json"):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, dict(resp.headers), json.loads(resp.read() or b"null") if "json" in resp.headers.get("Content-Type", "") else resp.read()
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), json.loads(err.read())

    def request_raw_length(self, length):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        try:
            conn.putrequest("POST", "/api/sessions")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(length))
            conn.endheaders()
            resp = conn.getresponse()
            return resp.status, dict(resp.headers), json.loads(resp.read())
        finally:
            conn.close()

    def start(self, learner="L01", problem="x^2 - 5x + 6 = 0", lang="en"):
        status, _, view = self.request("POST", "/api/sessions",
                                       {"class_code": "X2", "learner_code": learner, "problem": problem, "lang": lang})
        self.assertEqual(status, 201, view)
        return view

    def test_session_flow_and_persistence(self):
        view = self.start()
        self.assertEqual(view["step"], "diagnose")
        self.assertEqual(view["prompt"]["kind"], "pair")
        sid = view["session_id"]

        status, _, view = self.request("POST", f"/api/sessions/{sid}/answer", {"text": "2, 3"})
        self.assertEqual(status, 200)
        self.assertEqual(view["step"], "remediate")
        self.assertTrue(any("0.19" in m for m in view["messages"]))

        status, _, view = self.request("POST", f"/api/sessions/{sid}/continue", {})
        self.assertEqual(view["step"], "gate1")
        status, _, view = self.request("POST", f"/api/sessions/{sid}/hint", {})
        self.assertEqual(view["hints_used"], 1)
        self.assertEqual(view["hints_left"], 2)

        status, _, again = self.request("GET", f"/api/sessions/{sid}")
        self.assertEqual((status, again["step"]), (200, "gate1"))

        # Mastery carries over: a new session for the same learner starts from saved values.
        status, _, cls = self.request("GET", "/api/classes/X2?lang=id")
        self.assertEqual(status, 200)
        self.assertEqual(cls["learners"][0]["learner_code"], "L01")
        self.assertEqual(cls["lang"], "id")

    def test_teacher_view_names_no_weakest_concept_before_any_scored_answer(self):
        self.request("POST", "/api/sessions", {"class_code": "W1", "learner_code": "L09", "problem": "x^2 - 5x + 6 = 0"})
        _, _, cls = self.request("GET", "/api/classes/W1")
        self.assertIsNone(cls["learners"][0]["weakest"])

    def test_phraser_rewords_feedback_but_never_the_question(self):
        class Echo:
            def phrase(self, text, lang, step_label):
                return "Reworded: " + text

        self.server.RequestHandlerClass.phraser = Echo()
        try:
            view = self.start(learner="L10")
        finally:
            self.server.RequestHandlerClass.phraser = None
        self.assertTrue(view["messages"][0].startswith("Reworded: "))
        self.assertFalse(view["prompt"]["text"].startswith("Reworded"))

    def test_indonesian_messages(self):
        view = self.start(learner="L02", lang="id")
        self.assertIn("hasil kali", view["prompt"]["text"])
        self.assertEqual(view["steps"][0]["label"], "Cek prasyarat")

    def test_validation_errors(self):
        status, _, err = self.request("POST", "/api/sessions", {"class_code": "X", "learner_code": "L1", "problem": "x^2-1=0"})
        self.assertEqual((status, err["error"]["code"]), (422, "invalid_code"))
        status, _, err = self.request("POST", "/api/sessions", {"class_code": "X2", "learner_code": "L1", "problem": "x^2+1=0"})
        self.assertEqual((status, err["error"]["code"]), (422, "out_of_scope"))
        status, _, err = self.request("POST", "/api/sessions", {"class_code": "X2", "learner_code": "L1", "problem": "import os"})
        self.assertEqual((status, err["error"]["code"]), (422, "unreadable_problem"))
        status, _, err = self.request("POST", "/api/sessions", raw=b"{not json")
        self.assertEqual((status, err["error"]["code"]), (400, "invalid_json"))
        status, _, err = self.request("POST", "/api/sessions", raw=b"x" * 5000)
        self.assertEqual((status, err["error"]["code"]), (413, "payload_too_large"))
        status, _, err = self.request("POST", "/api/sessions", raw=b"{}", content_type="text/plain")
        self.assertEqual((status, err["error"]["code"]), (415, "unsupported_media_type"))
        status, _, err = self.request_raw_length(-1)
        self.assertEqual((status, err["error"]["code"]), (400, "invalid_length"))
        status, _, err = self.request("GET", "/api/sessions/" + "0" * 32)
        self.assertEqual((status, err["error"]["code"]), (404, "session_not_found"))
        sid = self.start(learner="L03")["session_id"]
        status, _, err = self.request("POST", f"/api/sessions/{sid}/answer", {"text": ""})
        self.assertEqual((status, err["error"]["code"]), (422, "invalid_answer"))

    def test_static_files_and_headers(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"<html lang=", body)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        for path in ("/static/../tuntas/engine.py", "/static/%2e%2e/serve.py", "/web/app.js", "/data/tuntas.db"):
            status, _, err = self.request("GET", path)
            self.assertEqual(status, 404, path)


if __name__ == "__main__":
    unittest.main()
