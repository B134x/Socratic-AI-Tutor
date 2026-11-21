"""Bayesian Knowledge Tracing (Corbett & Anderson, 1995)."""

from __future__ import annotations

from dataclasses import dataclass

MASTERY_THRESHOLD = 0.85


@dataclass(frozen=True)
class BKTParams:
    """Illustrative parameters; a pilot would fit these from learner data."""

    p_init: float = 0.30
    p_learn: float = 0.15
    p_slip: float = 0.10
    p_guess: float = 0.20


DEFAULT_PARAMS = BKTParams()


def update(p_known: float, correct: bool, params: BKTParams = DEFAULT_PARAMS) -> float:
    """Posterior P(L) after one observed answer, then the learning transition."""
    if correct:
        hit = p_known * (1 - params.p_slip)
        posterior = hit / (hit + (1 - p_known) * params.p_guess)
    else:
        miss = p_known * params.p_slip
        posterior = miss / (miss + (1 - p_known) * (1 - params.p_guess))
    return posterior + (1 - posterior) * params.p_learn
