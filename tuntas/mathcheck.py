"""Deterministic answer checking with SymPy.

SymPy's parser evaluates Python, so learner text is never handed to it until it passes
an allow-list: digits, x, arithmetic signs, brackets, '=', ',' and spaces, exponent 2 only.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from tokenize import TokenError

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

X = sp.Symbol("x")
MAX_INPUT_LENGTH = 60

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
_SAFE_GLOBALS = {name: getattr(sp, name) for name in ("Add", "Mul", "Pow", "Integer", "Rational", "Float", "Symbol")}
_ALLOWED = re.compile(r"[0-9x+\-*/^().,=\s]*")
_BAD_EXPONENT = re.compile(r"(\^|\*\*)\s*(?!2(?![0-9.]))")  # any exponent other than a plain 2
_LONG_NUMBER = re.compile(r"\d{5,}")
_UNICODE = str.maketrans({"²": "^2", "−": "-", "–": "-", "×": "*", "·": "*", "X": "x", "÷": "/"})


class MathInputError(ValueError):
    """Text that is not something the checker will evaluate."""


@dataclass(frozen=True)
class Verdict:
    status: str  # "correct" | "wrong" | "not_an_answer" | "not_factored"
    key: str
    args: dict = field(default_factory=dict)

    @property
    def scorable(self) -> bool:
        return self.status in ("correct", "wrong")


@dataclass(frozen=True)
class Quadratic:
    """x^2 + b*x + c with integer roots; factors as (x + p)(x + q)."""

    b: int
    c: int
    roots: tuple[int, int]

    @property
    def pair(self) -> tuple[int, int]:
        return (-self.roots[0], -self.roots[1])

    @property
    def expr(self) -> sp.Expr:
        return X**2 + self.b * X + self.c

    def display(self) -> str:
        return display_polynomial(self.b, self.c)

    def factored_display(self) -> str:
        # A bare x factor reads better first: x(x - 4), not (x - 4)x.
        return "".join(_bracket(p) for p in sorted(self.pair, key=lambda p: (p != 0, -p)))


def normalise(text: str) -> str:
    return text.translate(_UNICODE).strip()


def _guard(text: str) -> str:
    cleaned = normalise(text)
    if not cleaned:
        raise MathInputError("empty")
    if len(cleaned) > MAX_INPUT_LENGTH:
        raise MathInputError("too long")
    if not _ALLOWED.fullmatch(cleaned):
        raise MathInputError("characters outside the allow-list")
    if _BAD_EXPONENT.search(cleaned):
        raise MathInputError("only the exponent 2 is supported")
    if _LONG_NUMBER.search(cleaned):
        raise MathInputError("number too large")
    return cleaned


def parse_expression(text: str) -> sp.Expr:
    cleaned = _guard(text)
    if "=" in cleaned or "," in cleaned:
        raise MathInputError("expected a single expression")
    try:
        expr = parse_expr(cleaned, local_dict={"x": X}, global_dict=dict(_SAFE_GLOBALS),
                          transformations=_TRANSFORMS, evaluate=False)
    except (SyntaxError, TypeError, ValueError, NameError, sp.SympifyError, TokenError) as exc:
        raise MathInputError("could not parse") from exc
    if not isinstance(expr, sp.Expr) or not expr.free_symbols <= {X}:
        raise MathInputError("not an expression in x")
    return expr


def parse_quadratic(text: str) -> Quadratic:
    """Read a learner's problem such as 'x^2 - 5x + 6 = 0' into a monic quadratic with integer roots."""
    cleaned = _guard(text)
    sides = cleaned.split("=")
    if len(sides) > 2:
        raise MathInputError("more than one '='")
    lhs = parse_expression(sides[0])
    rhs = parse_expression(sides[1]) if len(sides) == 2 and sides[1].strip() else sp.Integer(0)
    poly = sp.Poly(sp.expand(lhs - rhs), X)
    coeffs = poly.all_coeffs()
    if poly.degree() != 2 or coeffs[0] != 1 or not all(cf.is_integer for cf in coeffs):
        raise MathInputError("out of scope")
    b, c = int(coeffs[1]), int(coeffs[2])
    disc = b * b - 4 * c
    if disc < 0 or math.isqrt(disc) ** 2 != disc:
        raise MathInputError("out of scope")
    s = math.isqrt(disc)
    return Quadratic(b=b, c=c, roots=((-b - s) // 2, (-b + s) // 2))


def check_pair(text: str, product: int, total: int) -> Verdict:
    """Two integers with a given product and sum, typed as 'a, b'."""
    parts = [p.strip() for p in normalise(text).split(",")]
    if len(parts) != 2 or not all(re.fullmatch(r"[+-]?\d{1,4}", p) for p in parts):
        return Verdict("not_an_answer", "pair_not_an_answer")
    a, b = int(parts[0]), int(parts[1])
    if a * b == product and a + b == total:
        return Verdict("correct", "pair_correct")
    return Verdict("wrong", "pair_wrong", {"a": a, "b": b, "got_product": a * b, "got_sum": a + b,
                                           "product": product, "total": total})


def is_factored(expr: sp.Expr) -> bool:
    """True if the expression is written as a product of linear factors in x."""
    if isinstance(expr, sp.Pow):
        factors = [expr.base]
    elif isinstance(expr, sp.Mul):
        factors = [f.base if isinstance(f, sp.Pow) else f for f in expr.args if f.has(X)]
    else:
        return False
    return bool(factors) and all(sp.degree(f, X) == 1 for f in factors)


def check_factored(text: str, target: Quadratic) -> Verdict:
    try:
        expr = parse_expression(text)
    except MathInputError:
        return Verdict("not_an_answer", "expression_not_an_answer")
    if sp.expand(expr - target.expr) != 0:
        return Verdict("wrong", "factor_wrong", {"poly": target.display()})
    if not is_factored(expr):
        return Verdict("not_factored", "factor_not_factored")
    return Verdict("correct", "factor_correct")


def check_roots(text: str, target: Quadratic) -> Verdict:
    """Both solutions, typed as '2, 3' or 'x = 2 or x = 3' (Indonesian 'atau'/'dan' also accepted)."""
    cleaned = normalise(text).lower()
    cleaned = re.sub(r"\b(or|and|atau|dan)\b", ",", cleaned)
    cleaned = re.sub(r"x\s*=", "", cleaned)
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if not parts or len(parts) > 2 or not all(re.fullmatch(r"[+-]?\d{1,4}", p) for p in parts):
        return Verdict("not_an_answer", "roots_not_an_answer")
    if {int(p) for p in parts} == set(target.roots):
        return Verdict("correct", "roots_correct")
    return Verdict("wrong", "roots_wrong")


def quadratic_from_pair(p: int, q: int) -> Quadratic:
    """The trinomial that factors as (x + p)(x + q)."""
    return Quadratic(b=p + q, c=p * q, roots=tuple(sorted((-p, -q))))


def display_polynomial(b: int, c: int) -> str:
    """Learner-facing text, e.g. 'x² − 5x + 6'."""
    out = "x²"
    if b:
        out += f" {'+' if b > 0 else '−'} {'' if abs(b) == 1 else abs(b)}x"
    if c:
        out += f" {'+' if c > 0 else '−'} {abs(c)}"
    return out


def _bracket(p: int) -> str:
    return f"(x {'+' if p > 0 else '−'} {abs(p)})" if p else "x"
