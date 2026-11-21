"""Prerequisite graph for the demonstration domain (quadratic equations)."""

from __future__ import annotations

# concept -> its direct prerequisites
PREREQUISITES: dict[str, tuple[str, ...]] = {
    "quadratic_equations": ("factoring_trinomials",),
    "factoring_trinomials": ("integer_product_sum",),
    "integer_product_sum": ("signed_integer_rules",),
    "signed_integer_rules": (),
}

CONCEPTS: tuple[str, ...] = tuple(PREREQUISITES)

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "quadratic_equations": "Quadratic equations",
        "factoring_trinomials": "Factoring trinomials",
        "integer_product_sum": "Integer product and sum",
        "signed_integer_rules": "Signed-integer rules",
    },
    "id": {
        "quadratic_equations": "Persamaan kuadrat",
        "factoring_trinomials": "Pemfaktoran trinomial",
        "integer_product_sum": "Hasil kali dan jumlah bilangan bulat",
        "signed_integer_rules": "Aturan tanda bilangan bulat",
    },
}


def ancestors(concept: str) -> list[str]:
    """All prerequisites of a concept, nearest first (breadth-first, backward walk)."""
    order: list[str] = []
    frontier = list(PREREQUISITES[concept])
    while frontier:
        current = frontier.pop(0)
        if current not in order:
            order.append(current)
            frontier.extend(PREREQUISITES[current])
    return order


def weakest_prerequisites(concept: str, mastery: dict[str, float], threshold: float, limit: int = 2) -> list[str]:
    """Prerequisites below the mastery threshold, weakest first; ties keep the nearer concept first."""
    below = [c for c in ancestors(concept) if mastery.get(c, 0.0) < threshold]
    return sorted(below, key=lambda c: mastery.get(c, 0.0))[:limit]
