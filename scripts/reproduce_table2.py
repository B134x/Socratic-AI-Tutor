"""Reproduce the essay's Table 2 (decision log) and the verifier self-test.

The logic lives in the tuntas package; this script only scripts the worked example.
Run from the repository root: python scripts/reproduce_table2.py [--markdown]
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tuntas import bkt  # noqa: E402
from tuntas.mathcheck import check_factored, check_pair, parse_quadratic, quadratic_from_pair  # noqa: E402

LABEL = {"signed": "Signed-integer rules", "factoring": "Factoring trinomials"}


def worked_example() -> list[dict]:
    mastery = {"signed": bkt.DEFAULT_PARAMS.p_init, "factoring": 0.72}  # 0.72: carried over from earlier practice
    log = []

    def record(step, concept, answer, verdict, scored):
        before = mastery[concept]
        if scored and verdict.scorable:
            mastery[concept] = bkt.update(before, verdict.status == "correct")
        after = mastery[concept]
        note = verdict.key if scored else f"{verdict.key} (guided step, not scored)"
        log.append({"step": step, "concept": LABEL[concept], "answer": answer, "verdict": note,
                    "before": before, "after": after, "gate": "open" if after >= bkt.MASTERY_THRESHOLD else "locked"})

    problem = parse_quadratic("x^2 - 5x + 6 = 0")
    record("Diagnose", "signed", "2, 3", check_pair("2, 3", problem.c, problem.b), True)
    record("Pressure", "signed", "just tell me the answer", check_pair("just tell me the answer", problem.c, problem.b), True)
    for product, total, answer in [(8, -6, "-2, -4"), (15, -8, "-3, -5")]:
        record("Gate 1", "signed", answer, check_pair(answer, product, total), True)
    for answer in ["x^2 - 5x + 6", "(x - 2)(x - 3)"]:
        record("Factor step", "factoring", answer, check_factored(answer, problem), False)
    record("Gate 2", "factoring", "(x - 4)(x - 5)", check_factored("(x - 4)(x - 5)", parse_quadratic("x^2 - 9x + 20 = 0")), True)
    return log


def verifier_self_test(n: int = 1000, seed: int = 7) -> dict:
    """Synthetic check of the verifier on generated trinomials (tests code, not learning)."""
    rng = random.Random(seed)
    res = {"n": n, "correct_accepted": 0, "sign_flip_rejected": 0, "unfactored_rejected": 0}
    for _ in range(n):
        sign = rng.choice((-1, 1))
        p, q = (sign * v for v in rng.sample(range(1, 9), 2))
        target = quadratic_from_pair(p, q)
        res["correct_accepted"] += check_factored(f"(x + ({p}))(x + ({q}))", target).status == "correct"
        res["sign_flip_rejected"] += check_factored(f"(x - ({p}))(x - ({q}))", target).status != "correct"
        res["unfactored_rejected"] += check_factored(f"x^2 + ({p + q})x + ({p * q})", target).status != "correct"
    return res


def main() -> None:
    p = bkt.DEFAULT_PARAMS
    print(f"Threshold {bkt.MASTERY_THRESHOLD}; BKT P(L0)={p.p_init}, P(T)={p.p_learn}, P(S)={p.p_slip}, P(G)={p.p_guess}\n")
    log = worked_example()
    for r in log:
        print(f"{r['step']:<12} {r['concept']:<21} {r['answer']:<26} {r['verdict']:<52} "
              f"P(L) {r['before']:.2f} -> {r['after']:.2f}  gate {r['gate']}")
    t = verifier_self_test()
    print(f"\nVerifier self-test on {t['n']} generated trinomials: correct accepted {t['correct_accepted']}/{t['n']}, "
          f"sign-flipped rejected {t['sign_flip_rejected']}/{t['n']}, unfactored rejected {t['unfactored_rejected']}/{t['n']}")
    if "--markdown" in sys.argv:
        print("\n| Step | Concept | Learner input | Checker result | P(L) before → after | Gate |")
        for r in log:
            print(f"| {r['step']} | {r['concept']} | {r['answer']} | {r['verdict']} | {r['before']:.2f} → {r['after']:.2f} | {r['gate']} |")


if __name__ == "__main__":
    main()
