"""Optional AI phrasing layer: "the AI talks, the system decides".

The engine decides every verdict, gate and next question; messages.py renders that
decision as a fixed template. A phraser may only reword one feedback message per turn
in a warmer tutor voice. It never sees learner or class codes, it never rewords the
question itself, and its output is discarded unless it passes the leak guard.

Off by default. Enable with TUNTAS_PHRASER=claude (needs `pip install anthropic`
and Anthropic API credentials); any failure falls back to the template text.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Protocol

from .messages import STEP_LABELS, render

log = logging.getLogger(__name__)

# Feedback and hints may be reworded. Mastery changes, gate decisions, remediation cards
# and the flag notice are system statements and always stay verbatim.
PHRASABLE = {
    "start_diagnose", "pair_correct", "pair_wrong", "pair_not_an_answer",
    "factor_correct", "factor_not_factored", "factor_wrong", "expression_not_an_answer",
    "roots_correct", "roots_wrong", "roots_not_an_answer",
    "hint_pair_1", "hint_pair_2", "hint_pair_3", "hint_factor_1", "hint_factor_2", "hint_factor_3",
    "hint_roots_1", "hint_roots_2", "hint_roots_3", "hint_transfer_1", "hint_transfer_2", "hint_transfer_3",
}

_SIGN_WORD = re.compile(r"\b(?:minus|negative|negatif)\s+", re.IGNORECASE)
_SQUARE = re.compile(r"\^\s*2|²")
_NUMBER = re.compile(r"-\s?\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")
# "one"/"satu" are left out: they are everyday words ("this one", "satu soal") and 1 is caught as a digit.
_NUMBER_WORDS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
    "nol", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas",
    "belas", "puluh",
}
# Sign words let a rewrite say "keep your numbers but make both negative" without a single digit.
_SIGN_WORDS = {
    "negative", "negatives", "positive", "positives", "minus", "plus", "sign", "signs", "opposite", "flip",
    "negatif", "positif", "tanda", "berlawanan", "kebalikan", "balik",
}


def _numbers(text: str) -> set[str]:
    text = _SQUARE.sub("", text.replace("−", "-"))
    text = _SIGN_WORD.sub("-", text)
    return {m.group().replace(" ", "").replace(",", ".") for m in _NUMBER.finditer(text)}


def _words(text: str, vocabulary: set[str]) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w in vocabulary}


def is_safe(candidate: str, original: str) -> bool:
    """Leak guard: a rewrite may not add any number (digits or words) or sign word the template lacks.

    Templates never contain the answer to the open question, so a rewrite that passes
    cannot state it either, even if the model worked the answer out by itself.
    """
    if not candidate or len(candidate) > 2 * len(original) + 160:
        return False
    if _numbers(candidate) - _numbers(original):
        return False
    vocabulary = _NUMBER_WORDS | _SIGN_WORDS
    return not (_words(candidate, vocabulary) - _words(original, vocabulary))


class Phraser(Protocol):
    def phrase(self, text: str, lang: str, step_label: str) -> str | None:
        """Return a reworded message, or None to keep the template."""


SYSTEM_PROMPT = """You reword one feedback message from a mathematics tutoring system for a secondary-school or university learner. The system has already decided what the message says; you only change the wording so it sounds like a patient human tutor.

Keep the meaning, the verdict and every number exactly as given. Do not add any number, equation or worked step that is not in the message, and never give or hint at an answer, even one you can work out. Write one to three short sentences of plain text in {language}, with no greeting, emoji or formatting. Reply with the reworded message only."""

LANGUAGE_NAMES = {"en": "English", "id": "Bahasa Indonesia, using the informal 'kamu' register teachers use with learners"}


class ClaudePhraser:
    """Rewords a message with Claude. Seven-second budget, no retries: the template is always a valid answer."""

    def __init__(self, model: str | None = None, timeout: float = 7.0):
        import anthropic  # imported here so the default install needs no extra package

        self._anthropic = anthropic
        self.model = model or os.environ.get("TUNTAS_CLAUDE_MODEL") or "claude-opus-5-5"
        self.client = anthropic.Anthropic(timeout=timeout, max_retries=0)

    def phrase(self, text: str, lang: str, step_label: str) -> str | None:
        anthropic = self._anthropic
        try:
            # Server-side fallback reroutes a policy decline to another model inside the same call.
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=2048,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=SYSTEM_PROMPT.format(language=LANGUAGE_NAMES[lang]),
                messages=[{"role": "user", "content": f"Step: {step_label}\nMessage: {text}"}],
            )
        except anthropic.RateLimitError:
            log.warning("phraser: rate limited, using the template")
            return None
        except anthropic.APIStatusError as exc:
            log.warning("phraser: API error %s, using the template", exc.status_code)
            return None
        except anthropic.APIConnectionError:
            log.warning("phraser: API unreachable or slow, using the template")
            return None
        if response.stop_reason != "end_turn":
            return None
        return "".join(block.text for block in response.content if block.type == "text").strip() or None


def phraser_from_env() -> Phraser | None:
    if os.environ.get("TUNTAS_PHRASER", "").lower() != "claude":
        return None
    try:
        return ClaudePhraser()
    except ImportError:
        log.warning("TUNTAS_PHRASER=claude but the anthropic package is not installed; using templates")
        return None


def speak(phraser: Phraser | None, lang: str, step: str, messages: list[tuple[str, dict]]) -> list[str]:
    """Render the turn's messages; reword at most one, and only if the rewrite passes the leak guard."""
    texts, used = [], False
    for key, args in messages:
        text = render(lang, key, args)
        if phraser is not None and not used and key in PHRASABLE:
            used = True
            try:
                candidate = phraser.phrase(text, lang, STEP_LABELS[lang].get(step, step))
            except Exception:  # noqa: BLE001 - an optional layer must never break the learner's turn
                log.exception("phraser failed, using the template")
                candidate = None
            if candidate and is_safe(candidate, text):
                text = candidate
            elif candidate:
                log.info("phraser: rewrite rejected by the leak guard")
        texts.append(text)
    return texts
