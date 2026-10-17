# Interview Room: AI Interview Simulator

A full-stack interview practice app with an AI interviewer that evaluates every answer, chooses the next question from what you just said, adjusts difficulty, and remembers your weak topics across sessions.

- **Backend:** Python FastAPI, SQLAlchemy, PostgreSQL (SQLite for zero-setup dev), JWT auth, server-side LLM calls
- **Frontend:** React + TypeScript + Tailwind CSS (Vite), Recharts, Web Speech API
- **AI:** Anthropic Claude (default) or any OpenAI-compatible endpoint, with schema-enforced JSON; a clearly labelled **demo mode** runs with no API key

---

## Quick start

Requirements: Python 3.11+, Node 20+.

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # add ANTHROPIC_API_KEY, or leave blank for demo mode
uvicorn app.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                                              # http://localhost:5173 (proxies /api to :8000)
```

Open http://localhost:5173, create an account and start an interview.

**Single-process production build:** `cd frontend && npm run build`, then run uvicorn. FastAPI serves `frontend/dist` at http://localhost:8000.

### PostgreSQL / Supabase

```bash
docker compose up -d db          # local Postgres 16 on :5432
# backend/.env
DATABASE_URL=postgresql+psycopg2://interview:interview@localhost:5432/interview_sim
```

Tables are created on startup. `backend/schema.sql` documents the same schema and can be applied manually (for Supabase, paste it into the SQL editor and use the pooled connection string with the `+psycopg2` driver).

### LLM configuration (`backend/.env`)

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `anthropic` (default), `openai` (any OpenAI-compatible URL), or `demo` |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Claude credentials and model (default `claude-sonnet-5-5`) |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | OpenAI or a compatible gateway / local server |
| `JWT_SECRET` | Long random string for signing session tokens |

Keys are read only by the server. The browser never sees them.

**Demo mode:** with no key, a banner says so throughout the app. Answers are scored by a transparent keyword rubric and questions come from the built-in bank (190+ rubric concepts across 30+ topics). The adaptive engine, memory, reports and roadmap all work the same way.

---

## How the adaptive engine works

```
answer ─▶ evaluate ─▶ validate ─▶ update memory ─▶ decide ─▶ write question ─▶ validate ─▶ ask
          (LLM or      (clamp,     (topic mastery)  (policy,   (LLM, or bank /    (no repeats,
           heuristic)   derive                       pure       templates)         rubric present)
                        verdict)                     Python)
```

**1. Evaluate.** Each answer gets correctness, relevance, depth and clarity (0–10), plus the evaluator's confidence in its own judgement (0–1). The LLM is told explicitly not to reward a confident tone or penalise hesitant phrasing; clarity is scored separately. `engine/scoring.py` clamps and rescales every value and derives the score and verdict itself, so the model can't label a 2/10 answer "correct". Invalid output falls back to the heuristic evaluator.

**2. Decide** (`engine/policy.py`, deterministic and unit-tested). The LLM never decides what happens next; it only writes the question for a decision made here:

| Last answer | Next step |
|---|---|
| Correct | Practical scenario on the same topic, one level harder (adaptive), then move on |
| Partial | Follow-up targeting the specific missing concepts |
| Incorrect / off-topic | Simpler diagnostic question on the same topic, then move on |
| Skipped | Recorded as a gap; new topic at a lower level |

Guard rails: at most 2 follow-ups per topic (no infinite loops), hard question and time limits enforced server-side, no topic twice in a row, near-duplicate questions rejected against this session and your history.

**3. Choose topics.** Ranked by session coverage, long-term mastery (topics you struggled with before are scheduled first), resume and job-description skills, and for mixed interviews a target mix of technical / coding / behavioural / project questions.

**4. Remember** (`engine/mastery.py`). Per-topic mastery (0–1) updates after every answer from correctness and depth only. Higher-confidence evaluations and harder questions move it more; hints reduce it; skips lower it. Strong history starts adaptive interviews at a higher level.

**Not revealing answers.** The rubric and hint are never sent with a question. While the interviewer is probing a gap with a follow-up, the "what was missing" feedback for the previous answer is held back and revealed once the thread is done.

**What the system does not do:** it does not train or fine-tune a model from your answers. Personalisation comes from adaptive prompting, persistent memory and performance-based selection. `backend/scripts/export_training_data.py` exists for a future, separately reviewed improvement process. It exports only users who explicitly opted in (off by default), pseudonymises ids and redacts emails, phones and URLs.

---

## Features by page

| Page | What it does |
|---|---|
| Landing | Explains the adaptive loop with a live example |
| Sign up / Sign in | bcrypt-hashed passwords, JWT sessions |
| Dashboard | Score trend, focus topics, mastery, recent interviews, resume an active interview |
| New interview | Role (6 + custom), type (technical, HR, project, coding, mixed), difficulty incl. adaptive, 10/20/30/45 min, question count, English/Hindi, text/voice, resume and JD upload (PDF/TXT/MD) |
| Interview room | Question, timer, progress, difficulty ladder, "why this question?", hint (2 max), repeat, skip, end, per-answer feedback and score breakdown, speech-to-text and text-to-speech with fallbacks, code-friendly input for coding questions |
| Results | Overall score, technical / problem-solving / communication, "measured directly" counts kept separate from AI estimates, topic table with mastery before → after, answers to revisit with what a strong answer covers, roadmap, comparison with your own past sessions, full transcript, no-guarantee disclaimer |
| Learning roadmap | Prioritised topics with study actions and practice questions; mark as practised |
| History & progress | All sessions and dimension trends |
| Profile & privacy | Profile and saved resume, opt-in training consent, JSON export, delete history, delete account |

---

## API

All endpoints are under `/api`; everything except auth, `meta` and `health` requires `Authorization: Bearer <token>`.

```
POST   /auth/signup | /auth/login         GET /auth/me
GET    /meta                              GET /health
POST   /interviews                        start (config in body)
GET    /interviews                        your history
GET    /interviews/{id}                   live state (no rubric/hints)
POST   /interviews/{id}/answer | skip | hint | repeat | end
GET    /interviews/{id}/report
GET    /analytics/overview                GET /roadmap      PATCH /roadmap/{id}
GET|PUT /profile    PUT /profile/consent  GET /profile/export
DELETE /profile/history                   DELETE /profile
POST   /uploads/extract                   resume / JD text + detected skills
```

Interactive docs: http://localhost:8000/docs

**Isolation:** every query is filtered by the authenticated user's id. Another user's session id returns 404 (not 403), so ids can't be probed.

---

## Tests

```bash
cd backend && pytest                    # 46 tests, SQLite
TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/test_db pytest   # same suite on Postgres
cd frontend && npm run typecheck
```

| File | Covers |
|---|---|
| `test_adaptive_policy.py` | follow-up / diagnostic / scenario selection, level changes, follow-up cap over a 20-question run, limits, weak-topic scheduling, resume/JD steering, mixed coverage, no repeats |
| `test_scoring.py` | clamping, rescaling, derived verdicts, rejection of malformed evaluations, tone vs substance, mastery maths, fallback question composition |
| `test_session_isolation.py` | cross-user access to every session action, history / roadmap / mastery isolation, session-to-session state |
| `test_interview_flow.py` | hints, repeat, skip, question and time limits, report sections, cross-session personalisation, uploads, privacy controls |
| `test_llm_mode.py` | full interview through a faked Anthropic transport; provider outage mid-interview falls back without breaking |

---

## Project layout

```
backend/
  app/
    main.py, config.py, database.py, models.py, schemas.py, security.py
    routers/      auth, interviews, profile (+uploads, privacy), analytics (dashboard, roadmap)
    engine/
      policy.py          adaptive decisions + topic selection (pure)
      scoring.py         evaluation validation
      mastery.py         long-term topic mastery
      llm.py             Anthropic / OpenAI-compatible client, prompts, JSON schemas
      demo_evaluator.py  heuristic rubric evaluator (demo + fallback)
      composer.py        bank / template question composition
      question_bank.py   topics, rubrics, role mapping
      interviewer.py     orchestration + persistence
      report.py          end-of-interview report
      text_utils.py      similarity, skill extraction
  scripts/export_training_data.py
  schema.sql, tests/, .env.example
frontend/src/
  pages/        Landing, Auth, Dashboard, Configure, InterviewRoom, Results, Roadmap, History, Profile
  components/   AppShell, ui, DifficultyLadder, TrendChart, DemoBanner
  lib/          api, auth, useSpeech, types, format
```

---

## Known limitations and next steps

- **Demo evaluator** matches rubric concepts by keyword. It can't detect a confidently stated misconception and is labelled as such. Use an LLM key for real evaluation.
- **Hindi** questions and feedback are fully supported with an LLM. In demo mode the bank is English with Hindi transitions; Hindi or Hinglish answers work either way.
- **Voice input** uses the browser's Web Speech API (best in Chrome and Edge). Without it, or if the microphone is blocked, the app explains why and you type instead.
- **Coding questions** use a monospace editor with tab support rather than Monaco; swapping in `@monaco-editor/react` is a contained change in `InterviewRoom.tsx`.
- **Tokens** live in `localStorage` for simplicity. For production, move to httpOnly cookies and add rate limiting on auth and LLM-backed endpoints.
- **Embeddings:** repeat detection is lexical (`text_utils.similarity`). The interface is narrow, so it can be swapped for embedding similarity.
