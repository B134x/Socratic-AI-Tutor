# TUNTAS prototype

TUNTAS is a Socratic maths tutor that keeps the answer to itself. You bring your own quadratic equation. TUNTAS checks the skills underneath it first, then locks each step until you solve a fresh version without help. The name comes from *belajar tuntas*, Indonesian for mastery learning.

This repository holds the working prototype for the essay *TUNTAS: A Socratic AI Tutor that Traces Missing Prerequisites and Gates Every Step to Build Independent Problem-Solvers* (4th International Student Summit 2026, Education).

One rule runs through the code: the AI talks, the system decides. SymPy checks each answer, Bayesian Knowledge Tracing (BKT) estimates mastery, and plain code opens the gates. The tutor's wording, from templates or from the optional AI layer, cannot change any of those decisions.

## A session, step by step

Take `x^2 - 5x + 6 = 0`.

1. **Prerequisite check.** TUNTAS asks for two whole numbers with product 6 and sum -5.
2. **Short review** if you miss. TUNTAS picks the review that matches the sign pattern you got wrong.
3. **Gate 1.** You answer new pairs with the same sign pattern until your mastery estimate reaches 0.85.
4. **Factor form.** You rewrite your own equation as two brackets. TUNTAS guides this step and leaves it unscored.
5. **Gate 2.** You factor new trinomials alone until mastery reaches 0.85.
6. **Roots and transfer.** You solve your equation, then one new equation.

Each item offers three hints, and none of them states the answer. If you answer right after a hint, TUNTAS keeps your score as it was and gives you a fresh item to solve alone. Three wrong answers in a row at a gate send you to a review card and flag you for the teacher.

## Run it

You need Python 3.10 or newer. From the repository folder:

```powershell
python -m pip install -r requirements.txt
python serve.py
```

Open <http://127.0.0.1:8765> as a learner and <http://127.0.0.1:8765/teacher> as a teacher. Both views switch between English and Bahasa Indonesia.

`python serve.py --help` lists the options: `--port`, `--db` (default `data/tuntas.db`) and `--host`. On a network you trust, `--host 0.0.0.0` lets phones in the classroom connect.

## Tests and the essay's numbers

```powershell
python -m unittest discover -s tests -t .
python scripts/reproduce_table2.py --markdown
```

The suite runs 40 tests and skips 2 of them unless you install the optional `anthropic` package. The tests cover the BKT numbers, the math checker with code-injection attempts, the full session flow, the HTTP API and the AI leak guard. The script prints the decision log behind Table 2 in the essay, then runs the checker on 1,000 generated trinomials.

## How it fits together

| Part | File | Job |
|---|---|---|
| Prerequisite graph | `tuntas/graph.py` | quadratic equations → factoring → integer product and sum → signed-integer rules |
| Mastery | `tuntas/bkt.py` | BKT update with P(L0) 0.30, P(T) 0.15, P(S) 0.10, P(G) 0.20; gate at 0.85 |
| Checker | `tuntas/mathcheck.py` | Screens answers with an allow-list, then checks pairs, factor forms and roots in SymPy |
| Items | `tuntas/items.py` | Draws practice numbers with the sign pattern of your problem |
| Engine | `tuntas/engine.py` | Runs the steps: gates, hints, attempt cap, flags |
| Messages | `tuntas/messages.py` | Holds each tutor sentence in English and Indonesian |
| AI rewording | `tuntas/tutor.py` | Optional; off unless you turn it on |
| Storage | `tuntas/store.py` | SQLite: sessions, a verdict log, mastery per learner |
| Server | `tuntas/server.py` | JSON API and web pages on the Python standard library |
| Web app | `web/` | Learner and teacher views in plain HTML, CSS and JavaScript |
| Tests | `tests/` | Unit tests, plus HTTP tests that start a real server on a free port |
| Essay data | `scripts/reproduce_table2.py` | Prints Table 2 and the checker self-test |

The JSON API has six routes: `POST /api/sessions`, `GET /api/sessions/{id}`, `POST /api/sessions/{id}/answer`, `/hint` and `/continue`, and `GET /api/classes/{code}`. A failed request gets a 4xx status and `{"error": {"code", "message"}}`.

## Optional AI rewording

Set `TUNTAS_PHRASER=claude` and Claude rewords one feedback message per turn, a verdict or a hint, in a warmer tutor voice. Questions, review cards, mastery changes and gate decisions keep their fixed wording.

```powershell
python -m pip install -r requirements-ai.txt
$env:ANTHROPIC_API_KEY = "<your key>"
$env:TUNTAS_PHRASER = "claude"
python serve.py
```

- **Model:** `claude-opus-5-5` at low effort. The request turns on Anthropic's server-side fallback, so if Claude declines, the API retries on another model inside the same call. Set `TUNTAS_CLAUDE_MODEL` to pick a different model.
- **Leak guard:** TUNTAS throws out a rewrite that adds a number, in digits or words, or a sign word such as "negative", "flip" or "tanda" that the original message lacks. The templates never contain the answer, so a rewrite that passes cannot contain it either.
- **No waiting on the AI:** TUNTAS gives Claude seven seconds and no retries. After a timeout, refusal, error or rejected rewrite, you see the template message.
- **What leaves your machine:** the message text and the step name. TUNTAS sends no class code, learner code or session id.
- **Cost:** Anthropic bills each reworded turn to your account as one short request. The `usage` field in each response shows the tokens.

## Privacy and security

- The teacher hands out class and learner codes. TUNTAS asks for no names or emails.
- The database keeps the checker's verdict and the mastery change. It stores no answer text.
- An allow-list (digits, `x`, `+ - * / ^ ( ) , =`) screens each answer before SymPy parses it, because SymPy's parser can run Python. TUNTAS also refuses long numbers and any exponent other than 2, which blocks calculation bombs.
- The server answers a fixed list of files, caps request bodies at 4 KB, uses parameterised SQL and sends a strict Content-Security-Policy. The pages write text with `textContent` and build no HTML strings.
- The server listens on 127.0.0.1 unless you pass `--host`.

## Limits

- **Scope:** equations of the form x² + bx + c = 0 with whole-number roots, on one chain of four prerequisite concepts. Another topic needs its own graph, items and checker.
- **Parameters:** the BKT values are standard starting values. We have not fitted them to learner data yet.
- **No accounts:** a class code works like a shared link. Anyone who knows it can open the class table, so run TUNTAS on a network you trust.
- **Scale:** one SQLite file on one machine, sized for a classroom. TUNTAS saves each learner action in one transaction and handles actions on the same session one at a time.
- **AI rewording:** we tested it against a local stand-in for the Claude API. It has not run against the live service.
- **Leak guard gaps:** the guard checks digits, number words and sign words. A model could hint at an answer some other way, for example "one less than the number you typed". Keeping the rewording to one feedback message per turn shrinks that risk without removing it.
- **No learning evidence yet:** the tests show that the code behaves as designed. To show that learners learn more, we need the classroom pilot the essay proposes.
