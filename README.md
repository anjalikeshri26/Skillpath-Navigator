# SkillPath Navigator

A placement-preparation platform for engineering students. It estimates what you know from quiz results, reads your resume against a target role, and turns both into an ordered study plan. A Groq-backed interviewer and tutor sit on top.

Features: adaptive mock tests, resume review, a prerequisite-aware roadmap, AI-written study notes you can edit and save, your own notes library, a mock interviewer and a tutor.

The part worth reading is how the pieces connect: quiz answers update a per-topic mastery estimate, mastery and resume evidence drive the roadmap, and the roadmap recalculates after every test.

## Run it

Requires Python 3.12.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                      # then add GROQ_API_KEY
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. The API serves the frontend, so there is no CORS setup in the default flow.

Without `GROQ_API_KEY` everything except the interviewer, the tutor, Study generation and AI question generation still works, including writing and saving your own notes. Those endpoints answer 503 with an explanation rather than returning invented text. Get a free key at https://console.groq.com/keys.

In development a demo account is seeded: `demo@skillpath.local` / `DemoPass123`. It is never created when `ENVIRONMENT=production`. Make yourself an admin with `python -m scripts.make_admin you@example.com`.

Docker (PostgreSQL): copy `backend/.env.example` to `backend/.env`, set `POSTGRES_PASSWORD` in a root `.env`, then `docker compose up --build`.

Tests: `cd backend && pytest`, and `node --test frontend/tests/*.test.mjs` for the Markdown renderer. CI runs both (`.github/workflows/ci.yml`).

## How it is organised

```
backend/app/
  domain/      Pure logic, no framework or database imports. Unit-testable on its own.
    mastery.py          Beta-distribution mastery with difficulty weighting and time decay
    adaptive.py         Difficulty recommendation and per-topic session planning
    grading.py          Grades shuffled-option tests
    roadmap_planner.py  Prerequisite-aware plan from mastery + resume evidence
    resume_analysis.py  Rule-based resume scoring with an itemised breakdown
    skills.py           Taxonomy loading and word-boundary alias matching
    embeddings.py       TF-IDF retrieval (see "Honest limits")
    notes_text.py       Titles, excerpts, search escaping, cleaning model-written markdown
  services/    Database-aware use cases (quiz, roadmap, resume, interview, tutor, dashboard)
  routers/     Thin HTTP layer, one file per feature
  ai/          groq_client.py (retries, JSON mode) and prompts.py (all prompt text)
  models/      SQLAlchemy tables, split by concern
  data/        skills.json, resources.json, questions/<topic>.json (one file per topic)
frontend/
  css/         styles.css (design system) and features.css (v2 components)
  js/core/     api, state, router, shell, dom helpers
  js/pages/    one module per feature
  js/voice/    speech recognition and synthesis helpers
  tests/       Markdown renderer tests (node --test)
docs/decisions.md   Why things are built the way they are
```

To add a topic, drop a JSON file in `data/questions/` and restart. To add a role or skill, edit `data/skills.json`. To add resources, edit `data/resources.json`.

## Design decisions

**Mastery is a belief, not a percentage.** Each topic holds a Beta(α, β) estimate. A correct answer on a hard question counts for more than one on an easy question, and a miss on an easy question costs more than a miss on a hard one. Evidence decays toward the prior with a half-life of about 46 days, so the number tracks recent ability. Estimates with fewer than five weighted answers are shown faded and labelled as early.

**Tests are server-side sessions.** Starting a test stores which questions were served and in what option order. Options are shuffled per question, so grading maps the selected position back to the original index on the server. Answers for questions that were not served, duplicate answers and late submissions are rejected. Questions are marked as used only when a test is submitted, so abandoning a test does not burn them.

**AI questions pass three gates before anyone sees them.** Structural validation, near-duplicate rejection against the topic's existing questions, and an independent second model call that solves the question without seeing the generator's answer. A question is stored only if both answers agree. Learners can report a question; three reports pull it from circulation and an admin can review it.

**The roadmap explains itself.** Priority is role weight multiplied by the knowledge gap. The gap comes from quiz mastery if there is any, otherwise from resume evidence (a skill shown in a project counts for more than one merely listed), otherwise a default. Weak prerequisites are pulled in automatically and ordering is topological. Every item states which of those signals produced it.

**The resume score is itemised.** Five components with fixed maximums sum to 100 and each shows its own explanation. It is a checklist, not an ATS simulation, and the UI says so.

**The Groq client keeps no state.** Each call returns a result or raises. Transient failures (429, 5xx, timeouts) are retried with backoff. JSON mode is used for structured tasks and replies are still validated, because valid JSON can have the wrong shape. Interview turns use the fast model (`GROQ_FAST_MODEL`, default `openai/gpt-oss-20b`); generation, verification and evaluation use the main one.

**Notes cannot silently overwrite each other.** Each note carries a revision that an update must echo; a second tab saving stale text gets a 409 instead of winning. Study output is a draft until the learner saves it, and unsaved drafts and edits trigger a leave-page warning.

## Honest limits

- **Study notes are not fact-checked.** They are one model call with an accuracy-focused prompt. The interface says to verify anything important, and truncated output is flagged, but there is no second-pass verification like the quiz questions get.
- **The Markdown renderer is intentionally small.** No images, footnotes or nested blockquotes. Notes with those will show them as plain text.

- **Retrieval is lexical.** Resource search and duplicate detection use TF-IDF over unigrams and bigrams, not neural embeddings. Groq does not offer an embeddings endpoint and this keeps the project free of downloads and extra services. `TfidfIndex` has a two-method surface (`search`, `nearest`), so a sentence-embedding model plus pgvector can replace it without touching callers.
- **The evaluation sets are tiny and not independent.** `scripts/evaluate_resume_skills.py` and `scripts/evaluate_retrieval.py` score 1.00 on the starter cases, but I wrote those cases alongside the taxonomy, so that mostly shows the harness works. Replace them with anonymised real resumes and real queries before quoting numbers anywhere.
- **The seed bank is small.** 68 hand-written questions across 17 topics, with no Advanced-level seeds. Beyond that, depth comes from Groq generation plus verification, or from your own additions.
- **Resource links are not checked automatically.** They were written without network access. Open each once and fix any that moved.
- **Single-process rate limiting.** Login and sign-up throttling is in memory. Behind several workers use Redis or a gateway.
- **No migrations yet.** Tables are created with `create_all`. Add Alembic before changing the schema on a database that holds real data.
- **Scanned PDFs are rejected,** with a message asking for OCR first.
- **Speech depends on the browser.** Recognition works best in Chrome and Edge; voice gender is inferred from voice names.
- **The API layer was never executed where it was written.** The environment had no network, so FastAPI and SQLAlchemy could not be installed. The domain layer (32 tests) and the frontend Markdown tests (10) were run. The API and Groq-client tests in `backend/tests` are written but have not been run. Run `pytest` first and expect to fix a few small things.

- **Groq model IDs change.** Groq retires models (`llama-3.1-8b-instant` shut down on 16 August 2026 for free and developer tiers). If a call fails with HTTP 404, set `GROQ_MODEL` / `GROQ_FAST_MODEL` in `.env` to a model listed at https://console.groq.com/docs/models.

## Ideas for next steps

1. Alembic migrations and a CI workflow that runs `pytest`.
2. Swap in sentence embeddings and pgvector, then compare recall@k on the retrieval cases.
3. Calibrate question difficulty from `times_correct / times_answered` once there is data.
4. Per-skill mastery instead of per-topic, so Pandas and Statistics stop sharing the Data Science estimate.
5. Interview evaluation spot-checks: have two people score the same transcripts and compare with the model.
