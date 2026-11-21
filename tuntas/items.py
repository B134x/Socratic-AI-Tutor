"""Isomorphic items: the same structure as the learner's own problem, with new numbers."""

from __future__ import annotations

import random

from .mathcheck import Quadratic, quadratic_from_pair


def sign_pattern(pair: tuple[int, int]) -> str:
    p, q = pair
    if p == 0 or q == 0:
        return "zero"
    if p < 0 and q < 0:
        return "both_negative"
    if p > 0 and q > 0:
        return "both_positive"
    return "mixed"


def _pool(pattern: str) -> list[tuple[int, int]]:
    """Every pair with the sign pattern, sizes 1 to 9."""
    sizes = range(1, 10)
    if pattern == "zero":
        return [(0, s * a) for a in sizes for s in (-1, 1)]
    if pattern == "both_negative":
        return [(-a, -b) for a in sizes for b in sizes if a < b]
    if pattern == "both_positive":
        return [(a, b) for a in sizes for b in sizes if a < b]
    return [(a, -b) for a in sizes for b in sizes if a != b]


def new_pair(rng: random.Random, pattern: str, avoid: set[tuple[int, int]]) -> tuple[int, int]:
    """A fresh pair (p, q) with the given sign pattern; once every pair has been used, repeats are allowed."""
    pool = _pool(pattern)
    unused = [pair for pair in pool if tuple(sorted(pair)) not in avoid]
    return rng.choice(unused or pool)


def new_quadratic(rng: random.Random, pattern: str, avoid: set[tuple[int, int]]) -> Quadratic:
    return quadratic_from_pair(*new_pair(rng, pattern, avoid))
