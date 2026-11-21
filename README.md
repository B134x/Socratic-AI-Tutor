# TUNTAS prototype

A Socratic maths tutor that never hands over the answer. A learner brings their own quadratic equation, TUNTAS checks the prerequisite skills first, and each step stays locked until the learner shows mastery on new numbers without help. The name comes from *belajar tuntas*, Indonesian for mastery learning.

This is the working prototype for the essay *TUNTAS: A Socratic AI Tutor that Traces Missing Prerequisites and Gates Every Step to Build Independent Problem-Solvers* (4th International Student Summit 2026, Education).

The rule the code enforces is the essay's own: **the AI talks, the system decides.** Verdicts come from a symbolic checker (SymPy), mastery comes from Bayesian Knowledge Tracing, and the gates are plain code. Language, whether templates or the optional AI rewording, never changes a decision.

## What a session looks like

1. **Prerequisite check.** The learner's equation `x^2 - 5x + 6 = 0` needs two numbers with product 6 and sum -5. TUNTAS asks for that first.
2. **Short review** if the check fails, chosen by the sign pattern of the missed pair.
3. **Gate 1.** New numbers with the same sign pattern until P(mastery) reaches 0.85.
4. **Factor form** of the learner's own equation (guided, not scored).
5. **Gate 2.** Factor new trinomials on their own until mastery reaches 0.85.
6. **Roots**, then a **transfer problem** with new numbers.

Hints come in a ladder of three per item and never state the answer. A correct answer given after a hint is not scored: the learner gets a fresh item to do alone. Three wrong answers in a row at a gate flag the learner for the teacher and switch to a review card.

## Run it

Needs Python 3.10 or newer. From the repository folder:

```powershell
python -m pip install -r requirements.txt
python serve.py
```

Open <http://127.0.0.1:8765> for the learner view and <http://127.0.0.1:8765/teacher> for the teacher view. Both work in English and Bahasa Indonesia.

Options: `--port 9000`, `--db path/to/file.db` (default `data/tuntas.db`), and `--host 0.0.0.0` to let phones on a trusted classroom network connect.

## Tests and the essay's numbers

```powershell
python -m unittest discover -s tests -t .
python scripts/reproduce_table2.py --markdown
```

The first command runs 40 tests (2 are skipped unless the optional `anthropic` package is installed): BKT values, the math checker (including rejected code injection), the full engine flow, the HTTP API, and the AI leak guard. The second prints the decision log used for Table 2 in the essay and a verifier self-test on 1,000 generated trinomials.

## How it is built

| Part | File | Job |
|---|---|---|
| Prerequisite graph | `tuntas/graph.py` | quadratic equations → factoring → integer product and sum → signed-integer rules |
| Mastery | `tuntas/bkt.py` | BKT update with P(L0) 0.30, P(T) 0.15, P(S) 0.10, P(G) 0.20; gate at 0.85 |
| Checker | `tuntas/mathcheck.py` | Parses answers with an allow-list before SymPy, checks pairs, factor forms and roots |
| Items | `tuntas/items.py` | New practice numbers with the same sign pattern as the learner's problem |
| Engine | `tuntas/engine.py` | The step machine: gates, hints, attempt cap, flags |
| Messages | `tuntas/messages.py` | Every tutor sentence, in English and Indonesian |
| AI rewording | `tuntas/tutor.py` | Optional; off by default (see below) |
| Storage | `tuntas/store.py` | SQLite: sessions, a verdict log, mastery per learner |
| Server | `tuntas/server.py` | JSON API and the web pages, Python standard library only |
| Web app | `web/` | Learner and teacher views, plain HTML, CSS and JavaScript |
| Tests | `tests/` | Unit tests and HTTP tests that start a real server on a free port |
| Essay data | `scripts/reproduce_table2.py` | Prints the essay's Table 2 and the verifier self-test |

API: `POST /api/sessions`, `GET /api/sessions/{id}`, `POST /api/sessions/{id}/answer|hint|continue`, `GET /api/classes/{code}`. Errors come back as `{"error": {"code", "message"}}` with a 4xx status.

## Optional AI rewording

With `TUNTAS_PHRASER=claude`, one feedback message per turn (a verdict or a hint) is reworded by Claude in a warmer tutor voice. Questions, review cards, mastery changes and gate decisions always stay as written.

```powershell
python -m pip install -r requirements-ai.txt
$env:ANTHROPIC_API_KEY = "<your key>"
$env:TUNTAS_PHRASER = "claude"
python serve.py
```

- **Model:** `claude-opus-5-5` at low effort, with Anthropic's server-side fallback switched on so a declined request is retried on another model inside the same call. Change the model with `TUNTAS_CLAUDE_MODEL`.
- **Leak guard:** a rewrite is thrown away if it adds any number (digits or words) or any sign word ("negative", "flip", "tanda" and so on) that the original message did not contain. The templates never contain the answer, so an accepted rewrite cannot contain it either.
- **Never blocks the learner:** seven-second limit, no retries. A timeout, refusal, error or rejected rewrite falls back to the template.
- **What is sent:** only the message text and the step name. No class code, learner code or session id.
- **Cost:** each reworded turn is one short request billed to your Anthropic account. The exact amount depends on the tokens used; the response's `usage` field reports it.

## Privacy and security

- Learners are identified only by a class code and a learner code the teacher hands out. No names, no emails.
- Answer text is never stored. The database keeps the checker's verdict and the mastery change.
- Answers are parsed by an allow-list (digits, `x`, `+ - * / ^ ( ) , =`) before SymPy sees them, because SymPy's parser can evaluate Python. Long numbers and exponents other than 2 are refused, which stops calculation bombs.
- The server answers only a fixed list of files (no path traversal), caps request bodies at 4 KB, uses parameterised SQL, and sends a strict Content-Security-Policy. The pages build all text with `textContent`, never HTML strings.
- It listens on 127.0.0.1 unless you pass `--host`.

## Limits

- **Scope:** equations of the form x² + bx + c = 0 with whole-number roots, and one chain of four prerequisite concepts. Other topics need their own graph, items and checkers.
- **Parameters:** the BKT values are standard starting values, not fitted to learner data.
- **No accounts:** a class code is not a password. Anyone who knows it can open the class table, so use it on a trusted network only.
- **Scale:** one SQLite file on one machine, meant for a classroom, not a whole school district. Each learner action is saved in one transaction, and actions on the same session are handled one at a time.
- **AI rewording** was tested against a local stand-in for the Claude API, not against the live service.
- **Leak guard** checks digits, number words and sign words. A model could in theory describe an answer some other way ("one less than the number you typed"); limiting rewording to one feedback message per turn reduces that risk but does not remove it.
- **No learning evidence yet:** the tests check that the code behaves as designed, not that learners learn more. That needs the classroom pilot described in the essay.
