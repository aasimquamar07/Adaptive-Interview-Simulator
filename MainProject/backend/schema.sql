-- PostgreSQL schema for the AI Interview Simulator.
-- The app creates these tables automatically on startup (SQLAlchemy create_all); this file documents
-- the schema and can be applied manually:  psql "$DATABASE_URL" -f schema.sql
-- Supabase: run it in the SQL editor. The app does its own JWT auth and filters every query by
-- user_id; if you also expose tables through Supabase's REST API, enable the RLS policies at the end.

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,          -- bcrypt
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS candidate_profiles (
    id                   SERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name            VARCHAR(120) NOT NULL DEFAULT '',
    target_role          VARCHAR(120) NOT NULL DEFAULT '',
    experience_level     VARCHAR(40)  NOT NULL DEFAULT '',
    preferred_language   VARCHAR(10)  NOT NULL DEFAULT 'en',
    resume_text          TEXT NOT NULL DEFAULT '',
    resume_skills        JSON NOT NULL DEFAULT '[]',
    training_consent     BOOLEAN NOT NULL DEFAULT FALSE,   -- explicit opt-in only
    training_consent_at  TIMESTAMPTZ,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS interview_sessions (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role             VARCHAR(120) NOT NULL,
    custom_role      VARCHAR(120) NOT NULL DEFAULT '',
    interview_type   VARCHAR(30)  NOT NULL,      -- technical | hr | project | coding | mixed
    difficulty_mode  VARCHAR(20)  NOT NULL,      -- beginner | intermediate | advanced | adaptive
    current_level    INTEGER NOT NULL DEFAULT 2, -- 1..3
    duration_minutes INTEGER NOT NULL DEFAULT 20,
    max_questions    INTEGER NOT NULL DEFAULT 8,
    language         VARCHAR(10) NOT NULL DEFAULT 'en',
    mode             VARCHAR(10) NOT NULL DEFAULT 'text',
    resume_text      TEXT NOT NULL DEFAULT '',
    job_description  TEXT NOT NULL DEFAULT '',
    jd_skills        JSON NOT NULL DEFAULT '[]',
    status           VARCHAR(20) NOT NULL DEFAULT 'active',
    ai_provider      VARCHAR(30) NOT NULL DEFAULT 'demo',
    engine_state     JSON NOT NULL DEFAULT '{}',  -- session-scoped working memory of the adaptive engine
    report           JSON,
    overall_score    DOUBLE PRECISION,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at         TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON interview_sessions(user_id);

CREATE TABLE IF NOT EXISTS interview_questions (
    id                  SERIAL PRIMARY KEY,
    session_id          INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    seq                 INTEGER NOT NULL,
    topic               VARCHAR(80) NOT NULL,
    level               INTEGER NOT NULL,
    kind                VARCHAR(20) NOT NULL,     -- core | followup | diagnostic | scenario | behavioral | project | coding
    text                TEXT NOT NULL,
    bank_id             VARCHAR(80),
    parent_question_id  INTEGER REFERENCES interview_questions(id),
    key_concepts        JSON NOT NULL DEFAULT '[]', -- hidden rubric
    hint                TEXT NOT NULL DEFAULT '',
    rationale           TEXT NOT NULL DEFAULT '',   -- why the engine asked it
    hints_used          INTEGER NOT NULL DEFAULT 0,
    repeats             INTEGER NOT NULL DEFAULT 0,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    asked_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_questions_session ON interview_questions(session_id);

CREATE TABLE IF NOT EXISTS candidate_answers (
    id                SERIAL PRIMARY KEY,
    question_id       INTEGER NOT NULL UNIQUE REFERENCES interview_questions(id) ON DELETE CASCADE,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text              TEXT NOT NULL,
    input_mode        VARCHAR(10) NOT NULL DEFAULT 'text',
    response_seconds  DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_answers_user ON candidate_answers(user_id);

CREATE TABLE IF NOT EXISTS answer_evaluations (
    id                SERIAL PRIMARY KEY,
    answer_id         INTEGER NOT NULL UNIQUE REFERENCES candidate_answers(id) ON DELETE CASCADE,
    correctness       DOUBLE PRECISION NOT NULL,  -- 0..10
    relevance         DOUBLE PRECISION NOT NULL,  -- 0..10
    depth             DOUBLE PRECISION NOT NULL,  -- 0..10
    clarity           DOUBLE PRECISION NOT NULL,  -- 0..10, communication only
    confidence        DOUBLE PRECISION NOT NULL,  -- 0..1, evaluator's confidence in its own judgement
    score             DOUBLE PRECISION NOT NULL,  -- 0..10 weighted
    mastery_estimate  DOUBLE PRECISION NOT NULL,  -- 0..1 topic mastery after this answer
    verdict           VARCHAR(20) NOT NULL,       -- correct | partial | incorrect | off_topic
    did_well          TEXT NOT NULL DEFAULT '',
    missing           TEXT NOT NULL DEFAULT '',
    improvement       TEXT NOT NULL DEFAULT '',
    missing_concepts  JSON NOT NULL DEFAULT '[]',
    evaluator         VARCHAR(30) NOT NULL DEFAULT 'demo',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS interview_events (
    id           SERIAL PRIMARY KEY,
    session_id   INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    question_id  INTEGER REFERENCES interview_questions(id) ON DELETE CASCADE,
    kind         VARCHAR(20) NOT NULL,   -- hint | repeat | skip | end
    detail       TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_events_session ON interview_events(session_id);

CREATE TABLE IF NOT EXISTS topic_mastery (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic           VARCHAR(80) NOT NULL,
    mastery         DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    attempts        INTEGER NOT NULL DEFAULT 0,
    correct_count   INTEGER NOT NULL DEFAULT 0,
    struggle_count  INTEGER NOT NULL DEFAULT 0,
    last_level      INTEGER NOT NULL DEFAULT 2,
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_mastery_user_topic UNIQUE (user_id, topic)
);
CREATE INDEX IF NOT EXISTS ix_mastery_user ON topic_mastery(user_id);

CREATE TABLE IF NOT EXISTS learning_recommendations (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id          INTEGER REFERENCES interview_sessions(id) ON DELETE CASCADE,
    topic               VARCHAR(80) NOT NULL,
    priority            INTEGER NOT NULL DEFAULT 2,
    reason              TEXT NOT NULL DEFAULT '',
    actions             JSON NOT NULL DEFAULT '[]',
    practice_questions  JSON NOT NULL DEFAULT '[]',
    status              VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_recs_user ON learning_recommendations(user_id);

-- Optional (Supabase): defence-in-depth row level security if tables are ever exposed via PostgREST.
-- The FastAPI backend connects as the table owner and is unaffected.
-- ALTER TABLE interview_sessions ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY own_sessions ON interview_sessions USING (user_id = current_setting('app.user_id')::int);
