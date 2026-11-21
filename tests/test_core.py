import json
import unittest

from tuntas import bkt, engine
from tuntas.graph import ancestors, weakest_prerequisites
from tuntas.messages import render
from tuntas.mathcheck import MathInputError, check_factored, check_pair, check_roots, parse_expression, parse_quadratic


class BKTTest(unittest.TestCase):
    def test_table2_trace(self):
        # Numbers printed in the essay's Table 2.
        p = bkt.update(0.30, False)
        self.assertAlmostEqual(p, 0.193, places=3)
        p = bkt.update(p, True)
        self.assertAlmostEqual(p, 0.591, places=3)
        p = bkt.update(p, True)
        self.assertAlmostEqual(p, 0.887, places=3)
        self.assertGreaterEqual(p, bkt.MASTERY_THRESHOLD)
        self.assertAlmostEqual(bkt.update(0.72, True), 0.932, places=3)

    def test_one_guess_cannot_open_gate(self):
        self.assertLess(bkt.update(bkt.update(0.30, False), True), bkt.MASTERY_THRESHOLD)


class GraphTest(unittest.TestCase):
    def test_backward_walk(self):
        self.assertEqual(ancestors("quadratic_equations"),
                         ["factoring_trinomials", "integer_product_sum", "signed_integer_rules"])

    def test_weakest_first(self):
        mastery = {"integer_product_sum": 0.6, "signed_integer_rules": 0.2}
        self.assertEqual(weakest_prerequisites("factoring_trinomials", mastery, 0.85),
                         ["signed_integer_rules", "integer_product_sum"])


class MathCheckTest(unittest.TestCase):
    def setUp(self):
        self.q = parse_quadratic("x² − 5x + 6 = 0")

    def test_parse_problem(self):
        self.assertEqual((self.q.b, self.q.c, self.q.roots), (-5, 6, (2, 3)))
        self.assertEqual(self.q.factored_display(), "(x − 2)(x − 3)")
        self.assertEqual(parse_quadratic("x^2 = 4x").factored_display(), "x(x − 4)")

    def test_out_of_scope_problems(self):
        for text in ("x^2 + 1 = 0", "2x^2 - 5x + 3 = 0", "x - 3 = 0", "x^2 - 2 = 0"):
            with self.assertRaises(MathInputError, msg=text):
                parse_quadratic(text)

    def test_rejects_code_and_expensive_input(self):
        for text in ('__import__("os").system("dir")', "x.__class__", "9^9^9", "x**99", "2^1000",
                     "123456789*x", "(" * 30 + "x" + ")" * 30, "lambda: 1", "x; import os"):
            with self.assertRaises(MathInputError, msg=text):
                parse_expression(text)

    def test_factored_checks(self):
        self.assertEqual(check_factored("(x-2)(x-3)", self.q).status, "correct")
        self.assertEqual(check_factored("(x - 3)*(x - 2)", self.q).status, "correct")
        self.assertEqual(check_factored("x^2 - 5x + 6", self.q).status, "not_factored")
        self.assertEqual(check_factored("(x+2)(x+3)", self.q).status, "wrong")
        self.assertEqual(check_factored("just tell me", self.q).status, "not_an_answer")

    def test_pair_and_roots(self):
        self.assertEqual(check_pair("-2, -3", 6, -5).status, "correct")
        self.assertEqual(check_pair("2, 3", 6, -5).status, "wrong")
        self.assertEqual(check_pair("tell me the answer", 6, -5).status, "not_an_answer")
        self.assertEqual(check_roots("x = 2 or x = 3", self.q).status, "correct")
        self.assertEqual(check_roots("x=3 atau x=2", self.q).status, "correct")
        self.assertEqual(check_roots("2", self.q).status, "wrong")
        self.assertEqual(check_roots("two and three", self.q).status, "not_an_answer")


def solve(state):
    """The correct answer for whatever the session is asking now."""
    item, q = state.item, state.problem
    if state.step in ("diagnose", "gate1"):
        a, b = engine._solve_pair(item["product"], item["total"])
        return f"{a}, {b}"
    if state.step == "factor":
        return q.factored_display().replace("−", "-")
    if state.step == "gate2":
        return engine._item_quadratic(item).factored_display().replace("−", "-")
    if state.step == "roots":
        return ", ".join(str(r) for r in q.roots)
    if state.step == "transfer":
        return ", ".join(str(r) for r in engine._item_quadratic(item).roots)
    raise AssertionError(state.step)


class EngineFlowTest(unittest.TestCase):
    def test_worked_example_full_flow(self):
        state, out = engine.start("x^2 - 5x + 6 = 0", seed=7)
        self.assertEqual(state.step, "diagnose")
        self.assertEqual(state.item["concept"], "signed_integer_rules")

        out = engine.submit(state, "2, 3")
        self.assertEqual((out.verdict, round(out.p_after, 2)), ("wrong", 0.19))
        self.assertEqual(state.step, "remediate")

        out = engine.submit(state, "just tell me the answer")  # typing on the review card does nothing
        self.assertFalse(out.scored)
        engine.continue_after_review(state)
        self.assertEqual(state.step, "gate1")

        out = engine.submit(state, "just tell me the answer")
        self.assertEqual(out.verdict, "not_an_answer")
        self.assertFalse(out.scored)
        self.assertAlmostEqual(state.mastery["signed_integer_rules"], 0.193, places=3)

        engine.submit(state, solve(state))
        engine.submit(state, solve(state))
        self.assertEqual(state.step, "factor")
        self.assertGreaterEqual(state.mastery["signed_integer_rules"], 0.85)

        out = engine.submit(state, "x^2 - 5x + 6")
        self.assertEqual((out.verdict, out.scored, state.step), ("not_factored", False, "factor"))
        engine.submit(state, solve(state))
        self.assertEqual(state.step, "gate2")
        self.assertNotEqual((state.item["b"], state.item["c"]), (-5, 6), "gate items use new numbers")

        while state.step == "gate2":
            engine.submit(state, solve(state))
        self.assertEqual(state.step, "roots")
        engine.submit(state, solve(state))
        self.assertEqual(state.step, "transfer")
        engine.submit(state, solve(state))
        self.assertEqual(state.step, "done")
        self.assertEqual(state.flags, [])

    def test_prior_mastery_skips_diagnosis(self):
        state, out = engine.start("x^2 - 5x + 6 = 0", {"signed_integer_rules": 0.9}, seed=1)
        self.assertEqual(state.step, "factor")
        self.assertEqual(out.messages[0][0], "start_skip")
        self.assertIn("gate1", state.skipped)

    def test_hint_makes_correct_answer_unscored(self):
        state, _ = engine.start("x^2 - 5x + 6 = 0", seed=3)
        engine.submit(state, "2, 3")
        engine.continue_after_review(state)
        before = state.mastery["signed_integer_rules"]
        first_item = dict(state.item)
        engine.hint(state)
        out = engine.submit(state, solve(state))
        self.assertEqual(out.verdict, "aided_correct")
        self.assertFalse(out.scored)
        self.assertEqual(state.mastery["signed_integer_rules"], before)
        self.assertNotEqual(state.item, first_item, "a fresh unaided item follows")

    def test_hint_ladder_stops_before_answer(self):
        state, _ = engine.start("x^2 - 5x + 6 = 0", seed=3)
        keys = [engine.hint(state).messages[0][0] for _ in range(4)]
        self.assertEqual(keys, ["hint_pair_1", "hint_pair_2", "hint_pair_3", "hints_exhausted"])

    def test_attempt_cap_flags_teacher(self):
        state, _ = engine.start("x^2 - 5x + 6 = 0", seed=5)
        engine.submit(state, "2, 3")
        engine.continue_after_review(state)
        flagged = False
        for _ in range(engine.MAX_FAILED_IN_A_ROW):
            flagged = engine.submit(state, "1, 1").flagged or flagged
        self.assertTrue(flagged)
        self.assertEqual(state.step, "remediate")
        self.assertEqual(state.flags[0]["concept"], "signed_integer_rules")

    def test_state_survives_json_round_trip(self):
        state, _ = engine.start("x^2 + x - 6 = 0", seed=9)
        engine.submit(state, "1, 1")
        restored = engine.SessionState.from_dict(json.loads(json.dumps(state.to_dict())))
        self.assertEqual(restored, state)

    def test_struggling_learner_never_runs_out_of_items(self):
        state, _ = engine.start("x^2 - 3x = 0", seed=4)  # zero pattern: only 18 distinct pairs exist
        engine.submit(state, "1, 1")
        for _ in range(60):
            if state.step == "remediate":
                engine.continue_after_review(state)
            engine.submit(state, "1, 1")
        self.assertIn(state.step, ("gate1", "remediate"))

    def test_assessed_lists_only_scored_concepts(self):
        state, _ = engine.start("x^2 - 5x + 6 = 0", seed=7)
        self.assertEqual(state.assessed, [])
        engine.submit(state, "2, 3")
        engine.continue_after_review(state)
        engine.hint(state)
        engine.submit(state, solve(state))  # aided, so not scored
        self.assertEqual(state.assessed, ["signed_integer_rules"])
        legacy = {k: v for k, v in state.to_dict().items() if k != "assessed"}
        self.assertEqual(engine.SessionState.from_dict(legacy).assessed, [])

    def test_mixed_sign_problem_uses_matching_items(self):
        state, _ = engine.start("x^2 + x - 6 = 0", seed=2)
        engine.submit(state, "1, 1")
        engine.continue_after_review(state)
        self.assertLess(state.item["product"], 0, "mixed-sign problem gets mixed-sign gate items")



class MessagesTest(unittest.TestCase):
    def test_indonesian_uses_decimal_comma(self):
        args = {"concept": "signed_integer_rules", "before": 0.30, "after": 0.19}
        self.assertEqual(render("id", "mastery_change", args), "Penguasaan aturan tanda bilangan bulat: 0,30 → 0,19.")
        self.assertEqual(render("en", "mastery_change", args), "Mastery of signed-integer rules: 0.30 → 0.19.")

    def test_negative_factors_get_brackets(self):
        text = render("en", "pair_wrong", {"a": 2, "b": -4, "got_product": -8, "got_sum": -2, "product": -8, "total": 2})
        self.assertIn("2 × (-4) = -8 and 2 + (-4) = -2", text)

    def test_done_message_reads_for_one_hint(self):
        self.assertEqual(render("en", "done", {"hints": 1}), "Done. You solved it yourself. Hints used along the way: 1.")


if __name__ == "__main__":
    unittest.main()
