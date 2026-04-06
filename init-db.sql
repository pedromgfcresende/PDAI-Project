-- AI Trends Explorer — Database Schema
-- PostgreSQL + pgvector

CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────
-- Items: every ingested piece of content
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS items (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,           -- 'arxiv', 'semantic_scholar', 'rss', 'github'
    source_id       TEXT UNIQUE NOT NULL,    -- dedup key (e.g. arxiv paper id, URL hash)
    title           TEXT NOT NULL,
    summary         TEXT,
    url             TEXT,
    authors         TEXT[],
    published_at    TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedding       vector(384),            -- all-MiniLM-L6-v2 output dimension
    relevance_score REAL,                   -- 0-1, set by Filter Agent
    novelty_score   REAL,                   -- 0-1, set by Filter Agent
    topics          TEXT[],                 -- assigned by Filter Agent
    raw_metadata    JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_items_source ON items (source);
CREATE INDEX IF NOT EXISTS idx_items_published ON items (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_relevance ON items (relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_items_embedding ON items USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- ─────────────────────────────────────────────
-- Reports: weekly briefings and monthly reports
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id              BIGSERIAL PRIMARY KEY,
    report_type     TEXT NOT NULL,           -- 'weekly' or 'monthly'
    title           TEXT NOT NULL,
    content_md      TEXT NOT NULL,            -- Markdown body
    content_html    TEXT,                     -- Rendered HTML (for email / dashboard)
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    quality_score   REAL,                    -- Critic Agent overall score (0-10)
    critic_feedback JSONB DEFAULT '{}',      -- Full critic output
    revision_count  INT DEFAULT 0,
    item_ids        BIGINT[],                -- items referenced in this report
    published       BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_reports_type ON reports (report_type);
CREATE INDEX IF NOT EXISTS idx_reports_period ON reports (period_start DESC);

-- ─────────────────────────────────────────────
-- Signals: detected trend patterns
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals (
    id              BIGSERIAL PRIMARY KEY,
    signal_type     TEXT NOT NULL,           -- 'emergence', 'acceleration', 'disruption'
    topic           TEXT NOT NULL,
    description     TEXT NOT NULL,
    strength        REAL NOT NULL,           -- 0-1
    evidence_ids    BIGINT[],               -- item IDs supporting this signal
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now(),
    active          BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_signals_type ON signals (signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_active ON signals (active) WHERE active = TRUE;
