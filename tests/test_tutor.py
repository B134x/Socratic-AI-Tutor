import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from tuntas import tutor
from tuntas.messages import render


class LeakGuardTest(unittest.TestCase):
    ORIGINAL = "Not yet: 2 × 3 = 6 and 2 + 3 = 5. You need product 6 and sum -5."

    def test_rewording_with_the_same_numbers_passes(self):
        self.assertTrue(tutor.is_safe("Close! 2 × 3 is 6, but 2 + 3 is 5, and you need a sum of -5 with product 6.", self.ORIGINAL))

    def test_signed_answer_is_blocked_even_when_digits_appear(self):
        for leak in ("Try -2 and -3 instead.", "Try −2 and −3.", "Think of minus 2 and minus 3.", "So it is (x - 2)(x - 3)."):
            self.assertFalse(tutor.is_safe(leak, self.ORIGINAL), leak)

    def test_number_words_are_blocked(self):
        self.assertFalse(tutor.is_safe("The pair is negative two and negative three.", self.ORIGINAL))
        self.assertFalse(tutor.is_safe("Coba dua dan tiga yang negatif.", self.ORIGINAL))

    def test_sign_words_are_blocked(self):
        self.assertFalse(tutor.is_safe("Very close: keep your two numbers but make both of them negative.", self.ORIGINAL))
        self.assertFalse(tutor.is_safe("Hampir: ubah tanda kedua bilanganmu.", self.ORIGINAL))
        self.assertTrue(tutor.is_safe("Look at the signs again.", "Check the signs: what must they be?"))

    def test_runaway_output_is_blocked(self):
        self.assertFalse(tutor.is_safe("Keep going. " * 60, self.ORIGINAL))
        self.assertFalse(tutor.is_safe("", self.ORIGINAL))

    def test_squares_and_decimal_commas_are_not_new_numbers(self):
        self.assertTrue(tutor.is_safe("Try factoring x^2 - 5x + 6 first.", "Before we factor x² − 5x + 6, a quick check."))
        self.assertTrue(tutor.is_safe("Penguasaanmu naik dari 0.30 ke 0.59.", "Penguasaan 0,30 → 0,59."))


class FakePhraser:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def phrase(self, text, lang, step_label):
        self.calls.append((text, lang, step_label))
        if self.error:
            raise self.error
        return self.reply


class SpeakTest(unittest.TestCase):
    TURN = [("pair_wrong", {"a": 2, "b": 3, "got_product": 6, "got_sum": 5, "product": 6, "total": -5}),
            ("mastery_change", {"concept": "signed_integer_rules", "before": 0.30, "after": 0.19})]

    def test_templates_without_a_phraser(self):
        texts = tutor.speak(None, "en", "diagnose", self.TURN)
        self.assertEqual(texts[0], render("en", *self.TURN[0]))
        self.assertEqual(texts[1], "Mastery of signed-integer rules: 0.30 → 0.19.")

    def test_safe_rewrite_replaces_only_the_feedback(self):
        fake = FakePhraser("Almost: 2 × 3 = 6 but 2 + 3 = 5. Aim for product 6 and sum -5.")
        texts = tutor.speak(fake, "en", "diagnose", self.TURN)
        self.assertEqual(texts[0], fake.reply)
        self.assertEqual(texts[1], render("en", *self.TURN[1]))
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0][2], "Prerequisite check")

    def test_leaking_rewrite_falls_back_to_the_template(self):
        texts = tutor.speak(FakePhraser("The answer is -2 and -3."), "en", "diagnose", self.TURN)
        self.assertEqual(texts[0], render("en", *self.TURN[0]))

    def test_phraser_crash_never_breaks_the_turn(self):
        with self.assertLogs("tuntas.tutor", level="ERROR"):
            texts = tutor.speak(FakePhraser(error=RuntimeError("boom")), "en", "diagnose", self.TURN)
        self.assertEqual(texts[0], render("en", *self.TURN[0]))

    def test_system_statements_are_never_sent(self):
        fake = FakePhraser("anything")
        tutor.speak(fake, "en", "gate1", [("gate_open", {}), ("cap_reached", {})])
        self.assertEqual(fake.calls, [])


class FakeMessagesApi(BaseHTTPRequestHandler):
    """Stands in for the Messages API so the request shape is checked without a key or a bill."""

    reply = {"stop_reason": "end_turn", "text": "Almost there."}
    status = 200
    seen: list = []

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeMessagesApi.seen.append({"path": self.path, "beta": self.headers.get("anthropic-beta"), "body": body})
        if self.status != 200:
            payload = {"type": "error", "error": {"type": "api_error", "message": "down"}}
        else:
            payload = {"id": "msg_test", "type": "message", "role": "assistant", "model": body["model"],
                       "content": [{"type": "text", "text": self.reply["text"]}],
                       "stop_reason": self.reply["stop_reason"], "stop_sequence": None,
                       "usage": {"input_tokens": 50, "output_tokens": 8}}
        data = json.dumps(payload).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


try:
    import anthropic  # noqa: F401
    HAVE_SDK = True
except ImportError:
    HAVE_SDK = False


@unittest.skipUnless(HAVE_SDK, "anthropic SDK not installed (optional dependency)")
class ClaudePhraserWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = ThreadingHTTPServer(("127.0.0.1", 0), FakeMessagesApi)
        threading.Thread(target=cls.api.serve_forever, daemon=True).start()
        cls.env = mock.patch.dict(os.environ, {"ANTHROPIC_BASE_URL": f"http://127.0.0.1:{cls.api.server_address[1]}",
                                               "ANTHROPIC_API_KEY": "test-key", "TUNTAS_CLAUDE_MODEL": ""})
        cls.env.start()

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.api.shutdown()
        cls.api.server_close()

    def setUp(self):
        FakeMessagesApi.seen.clear()
        FakeMessagesApi.status = 200
        FakeMessagesApi.reply = {"stop_reason": "end_turn", "text": "Almost there."}

    def test_request_shape(self):
        phraser = tutor.ClaudePhraser()
        self.assertEqual(phraser.phrase("Not yet.", "id", "Cek prasyarat"), "Almost there.")
        sent = FakeMessagesApi.seen[0]
        self.assertTrue(sent["path"].startswith("/v1/messages"))
        self.assertIn("server-side-fallback-2026-07-01", sent["beta"])
        body = sent["body"]
        self.assertEqual(body["model"], "claude-opus-5-5")
        self.assertEqual(body["fallbacks"], "default")
        self.assertEqual(body["output_config"], {"effort": "low"})
        self.assertIn("Bahasa Indonesia", body["system"])
        self.assertEqual(body["messages"], [{"role": "user", "content": "Step: Cek prasyarat\nMessage: Not yet."}])

    def test_refusal_and_errors_keep_the_template(self):
        phraser = tutor.ClaudePhraser()
        FakeMessagesApi.reply = {"stop_reason": "refusal", "text": ""}
        self.assertIsNone(phraser.phrase("Not yet.", "en", "Gate 1"))
        FakeMessagesApi.status = 500
        with self.assertLogs("tuntas.tutor", level="WARNING"):
            self.assertIsNone(phraser.phrase("Not yet.", "en", "Gate 1"))


if __name__ == "__main__":
    unittest.main()
