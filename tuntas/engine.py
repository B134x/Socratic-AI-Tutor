"""Session state machine: the decision core of TUNTAS.

Flow: diagnose -> (remediate -> gate1) -> factor -> gate2 -> roots -> transfer -> done.
Only unaided items in diagnose, gate1, gate2 and transfer move P(L); guided steps and
answers given after a hint complete the item but are not scored.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field

from . import bkt
from .graph import CONCEPTS, weakest_prerequisites
from .items import new_pair, new_quadratic, sign_pattern
from .mathcheck import Quadratic, Verdict, check_factored, check_pair, check_roots, parse_quadratic

MAX_FAILED_IN_A_ROW = 3
MAX_HINTS_PER_ITEM = 3
FLOW = ("diagnose", "gate1", "factor", "gate2", "roots", "transfer")
SCORED_STEPS = {"diagnose", "gate1", "gate2", "transfer"}
INPUT_KIND = {"diagnose": "pair", "gate1": "pair", "factor": "expression", "gate2": "expression",
              "roots": "roots", "transfer": "roots", "remediate": "continue", "done": "none"}


@dataclass
class SessionState:
    b: int
    c: int
    roots: tuple[int, int]
    step: str
    mastery: dict[str, float]
    seed: int
    item: dict = field(default_factory=dict)
    used_pairs: list[tuple[int, int]] = field(default_factory=list)
    failed_in_a_row: dict[str, int] = field(default_factory=dict)
    completed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    remediate_key: str = ""
    return_to: str = ""
    hints_used: int = 0
    item_hints: int = 0
    draws: int = 0
    flags: list[dict] = field(default_factory=list)
    assessed: list[str] = field(default_factory=list)  # concepts with at least one scored answer this session

    @property
    def problem(self) -> Quadratic:
        return Quadratic(self.b, self.c, tuple(self.roots))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        data = dict(data)
        data["roots"] = tuple(data["roots"])
        data["used_pairs"] = [tuple(p) for p in data.get("used_pairs", [])]
        return cls(**data)


@dataclass
class Outcome:
    """What happened on one learner action; messages are (template key, args) pairs."""

    messages: list[tuple[str, dict]] = field(default_factory=list)
    scored: bool = False
    concept: str = ""
    p_before: float | None = None
    p_after: float | None = None
    verdict: str = ""
    flagged: bool = False


def pair_concept(pair: tuple[int, int]) -> str:
    return "signed_integer_rules" if min(pair) < 0 else "integer_product_sum"


def start(problem_text: str, prior_mastery: dict[str, float] | None = None, seed: int | None = None) -> tuple[SessionState, Outcome]:
    """Begin a session on the learner's own problem. Raises mathcheck.MathInputError if out of scope."""
    q = parse_quadratic(problem_text)
    mastery = {c: (prior_mastery or {}).get(c, bkt.DEFAULT_PARAMS.p_init) for c in CONCEPTS}
    state = SessionState(b=q.b, c=q.c, roots=q.roots, step="diagnose", mastery=mastery,
                         seed=seed if seed is not None else random.randrange(1 << 30),
                         used_pairs=[tuple(sorted(q.pair))])
    out = Outcome()
    concept = pair_concept(q.pair)
    weak = weakest_prerequisites("factoring_trinomials", mastery, bkt.MASTERY_THRESHOLD)
    if concept in weak:
        state.item = {"kind": "pair", "concept": concept, "product": q.c, "total": q.b}
        out.messages.append(("start_diagnose", {"poly": q.display()}))
    else:
        state.skipped += ["diagnose", "gate1"]
        _enter_factor(state)
        out.messages.append(("start_skip", {"concept": concept}))
    return state, out


def submit(state: SessionState, text: str) -> Outcome:
    handler = {"diagnose": _submit_pair, "gate1": _submit_pair, "factor": _submit_factor,
               "gate2": _submit_gate2, "roots": _submit_roots, "transfer": _submit_transfer}.get(state.step)
    if handler is None:
        return Outcome()
    return handler(state, text)


def continue_after_review(state: SessionState) -> Outcome:
    """Leave the remediation card and return to a gate with a fresh item."""
    if state.step != "remediate":
        return Outcome()
    target, state.return_to = state.return_to, ""
    if target == "gate2":
        _enter_gate2(state)
    else:
        _enter_gate1(state)
    return Outcome()


def hint(state: SessionState) -> Outcome:
    out = Outcome()
    family = {"diagnose": "pair", "gate1": "pair", "factor": "factor", "gate2": "factor",
              "roots": "roots", "transfer": "transfer"}.get(state.step)
    if family is None:
        out.messages.append(("no_hints_here", {}))
        return out
    if state.item_hints >= MAX_HINTS_PER_ITEM:
        out.messages.append(("hints_exhausted", {}))
        return out
    state.item_hints += 1
    state.hints_used += 1
    out.messages.append((f"hint_{family}_{state.item_hints}", _hint_args(state)))
    return out


def prompt(state: SessionState) -> tuple[str, str, dict]:
    """(input kind, template key, args) for what the learner is asked right now."""
    item, q, step = state.item, state.problem, state.step
    if step in ("diagnose", "gate1"):
        key, args = "prompt_pair", {"product": item["product"], "total": item["total"]}
    elif step == "factor":
        key, args = "prompt_factor", {"poly": q.display()}
    elif step == "gate2":
        key, args = "prompt_gate2", {"poly": _item_quadratic(item).display()}
    elif step == "roots":
        key, args = "prompt_roots", {"factored": q.factored_display()}
    elif step == "transfer":
        key, args = "prompt_transfer", {"poly": _item_quadratic(item).display()}
    elif step == "remediate":
        key, args = state.remediate_key, {}
    else:
        key, args = ("done_flagged" if state.flags else "done"), {"hints": state.hints_used}
    return INPUT_KIND[step], key, args


# --- step handlers -------------------------------------------------------------

def _submit_pair(state: SessionState, text: str) -> Outcome:
    item = state.item
    verdict = check_pair(text, item["product"], item["total"])
    out = _score(state, item["concept"], verdict)
    if not out.scored:
        return out
    if verdict.status == "correct":
        if _mastered(state, item["concept"]):
            out.messages.append(("gate_open", {}))
            state.completed.append(state.step)
            if state.step == "diagnose":
                state.skipped.append("gate1")
            _enter_factor(state)
        else:
            if state.step == "diagnose":
                state.completed.append("diagnose")
            out.messages.append(("one_more", {}))
            _enter_gate1(state)
    elif state.step == "diagnose":
        state.completed.append("diagnose")
        _enter_remediate(state, f"remediate_{sign_pattern(_solve_pair(item['product'], item['total']))}", "gate1")
    elif not _cap_reached(state, item["concept"], out):
        out.messages.append(("one_more", {}))
        _enter_gate1(state)
    return out


def _submit_factor(state: SessionState, text: str) -> Outcome:
    verdict = check_factored(text, state.problem)
    out = Outcome(verdict=verdict.status, messages=[(verdict.key, verdict.args)])
    if verdict.status == "correct":
        state.completed.append("factor")
        if _mastered(state, "factoring_trinomials"):
            state.skipped.append("gate2")
            _enter_roots(state)
        else:
            _enter_gate2(state)
    return out


def _submit_gate2(state: SessionState, text: str) -> Outcome:
    verdict = check_factored(text, _item_quadratic(state.item))
    out = _score(state, "factoring_trinomials", verdict)
    if not out.scored:
        return out
    if verdict.status == "correct":
        if _mastered(state, "factoring_trinomials"):
            out.messages.append(("gate_open", {}))
            state.completed.append("gate2")
            _enter_roots(state)
        else:
            out.messages.append(("one_more", {}))
            _enter_gate2(state)
    elif not _cap_reached(state, "factoring_trinomials", out):
        out.messages.append(("one_more", {}))
        _enter_gate2(state)
    return out


def _submit_roots(state: SessionState, text: str) -> Outcome:
    verdict = check_roots(text, state.problem)
    out = Outcome(verdict=verdict.status, messages=[(verdict.key, verdict.args)])
    if verdict.status == "correct":
        state.completed.append("roots")
        _enter_transfer(state)
    return out


def _submit_transfer(state: SessionState, text: str) -> Outcome:
    verdict = check_roots(text, _item_quadratic(state.item))
    out = _score(state, "quadratic_equations", verdict)
    if not out.scored:
        return out
    if verdict.status == "correct":
        state.completed.append("transfer")
        state.step, state.item = "done", {}
    else:
        if state.failed_in_a_row.get("quadratic_equations", 0) >= MAX_FAILED_IN_A_ROW:
            _flag(state, "quadratic_equations", out)
            state.step, state.item = "done", {}
        else:
            out.messages.append(("one_more", {}))
            _enter_transfer(state)
    return out


# --- helpers ---------------------------------------------------------------------

def _score(state: SessionState, concept: str, verdict: Verdict) -> Outcome:
    out = Outcome(verdict=verdict.status, concept=concept, messages=[(verdict.key, verdict.args)])
    if not verdict.scorable:
        return out
    if state.item_hints and verdict.status == "correct":
        # Aided success completes nothing: the learner gets a fresh, unaided item instead.
        out.verdict = "aided_correct"
        out.messages = [("aided_not_scored", {})]
        _refresh_item(state)
        return out
    before = state.mastery[concept]
    after = bkt.update(before, verdict.status == "correct")
    state.mastery[concept] = after
    state.failed_in_a_row[concept] = 0 if verdict.status == "correct" else state.failed_in_a_row.get(concept, 0) + 1
    if concept not in state.assessed:
        state.assessed.append(concept)
    out.scored, out.p_before, out.p_after = True, before, after
    out.messages.append(("mastery_change", {"concept": concept, "before": before, "after": after}))
    return out


def _cap_reached(state: SessionState, concept: str, out: Outcome) -> bool:
    if state.failed_in_a_row.get(concept, 0) < MAX_FAILED_IN_A_ROW:
        return False
    _flag(state, concept, out)
    key = "remediate_factoring" if concept == "factoring_trinomials" else f"remediate_{sign_pattern(state.problem.pair)}"
    _enter_remediate(state, key, state.step)
    return True


def _flag(state: SessionState, concept: str, out: Outcome) -> None:
    state.failed_in_a_row[concept] = 0
    state.flags.append({"concept": concept, "step": state.step})
    out.flagged = True
    out.messages.append(("cap_reached", {}))


def _mastered(state: SessionState, concept: str) -> bool:
    return state.mastery[concept] >= bkt.MASTERY_THRESHOLD


def _rng(state: SessionState) -> random.Random:
    state.draws += 1
    return random.Random(f"{state.seed}:{state.draws}")


def _avoid(state: SessionState) -> set[tuple[int, int]]:
    return {tuple(p) for p in state.used_pairs}


def _new_pair_item(state: SessionState) -> dict:
    avoid = _avoid(state)
    pair = new_pair(_rng(state), sign_pattern(state.problem.pair), avoid)
    state.used_pairs.append(tuple(sorted(pair)))
    return {"kind": "pair", "concept": pair_concept(pair), "product": pair[0] * pair[1], "total": pair[0] + pair[1]}


def _new_quadratic_item(state: SessionState) -> dict:
    avoid = _avoid(state)
    q = new_quadratic(_rng(state), sign_pattern(state.problem.pair), avoid)
    state.used_pairs.append(tuple(sorted(q.pair)))
    return {"kind": "quadratic", "b": q.b, "c": q.c, "roots": list(q.roots)}


def _refresh_item(state: SessionState) -> None:
    if state.step == "diagnose":
        state.completed.append("diagnose")
        _enter_gate1(state)
    elif state.step == "gate1":
        _enter_gate1(state)
    elif state.step == "gate2":
        _enter_gate2(state)
    elif state.step == "transfer":
        _enter_transfer(state)


def _enter_gate1(state: SessionState) -> None:
    state.step, state.item, state.item_hints = "gate1", _new_pair_item(state), 0


def _enter_factor(state: SessionState) -> None:
    state.step, state.item, state.item_hints = "factor", {}, 0


def _enter_gate2(state: SessionState) -> None:
    state.step, state.item, state.item_hints = "gate2", _new_quadratic_item(state), 0


def _enter_roots(state: SessionState) -> None:
    state.step, state.item, state.item_hints = "roots", {}, 0


def _enter_transfer(state: SessionState) -> None:
    state.step, state.item, state.item_hints = "transfer", _new_quadratic_item(state), 0


def _enter_remediate(state: SessionState, key: str, return_to: str) -> None:
    state.step, state.item, state.item_hints = "remediate", {}, 0
    state.remediate_key, state.return_to = key, return_to


def _item_quadratic(item: dict) -> Quadratic:
    return Quadratic(item["b"], item["c"], tuple(item["roots"]))


def _solve_pair(product: int, total: int) -> tuple[int, int]:
    root = math.isqrt(total * total - 4 * product)
    return ((total - root) // 2, (total + root) // 2)


def _hint_args(state: SessionState) -> dict:
    item, q = state.item, state.problem
    if state.step in ("diagnose", "gate1"):
        return {"product": item["product"], "total": item["total"]}
    target = _item_quadratic(item) if state.step in ("gate2", "transfer") else q
    return {"b": target.b, "c": target.c, "poly": target.display()}
