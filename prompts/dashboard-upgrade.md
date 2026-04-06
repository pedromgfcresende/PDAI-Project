## Task: Upgrade Dashboard & Report Formatting

### Context

This is the AI Trends Explorer project — a multi-agent system (FastAPI + LangGraph) that ingests AI news/papers, scores them with Claude Haiku, and generates reports via a writer-critic pipeline (Sonnet + Groq Llama). The stack runs locally with Docker Compose (Postgres + pgvector) and the FastAPI agent service.

### Current State

**API endpoints already working:**
- `POST /ingest/{source}` — ingest from arxiv, rss, semantic_scholar, github
- `POST /filter?limit=N` — score items with Haiku
- `POST /signals/detect` — detect trend signals
- `POST /reports/generate?report_type=weekly|monthly` — full writer-critic pipeline
- `GET /reports?report_type=weekly|monthly&limit=N` — list reports
- `GET /health` — health check
- `GET /signals` — list active signals

**Reports table schema (Postgres):**
```sql
CREATE TABLE reports (
    id              BIGSERIAL PRIMARY KEY,
    report_type     TEXT NOT NULL,           -- 'weekly' or 'monthly'
    title           TEXT NOT NULL,
    content_md      TEXT NOT NULL,           -- Markdown body
    content_html    TEXT,                    -- Rendered HTML (currently NULL — not populated yet)
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    quality_score   REAL,
    critic_feedback JSONB DEFAULT '{}',
    revision_count  INT DEFAULT 0,
    item_ids        BIGINT[],
    published       BOOLEAN DEFAULT FALSE
);
```

**Current dashboard:** `dashboard/index.html` — a single static HTML file with inline CSS/JS. Uses `fetch()` to call `http://localhost:8000`. CORS is already enabled on the API (`allow_origins=["*"]`).

**Current report response model (`agent_service/models.py`):**
```python
class ReportResponse(BaseModel):
    id: int
    report_type: ReportType
    title: str
    content_md: str
    quality_score: float | None
    revision_count: int
    published: bool
```

**Key files:**
- `agent_service/main.py` — FastAPI app with all endpoints
- `agent_service/db.py` — all DB operations (psycopg2, no ORM)
- `agent_service/models.py` — Pydantic models
- `agent_service/agents/pipeline.py` — LangGraph StateGraph (synthesize → critique → publish)
- `agent_service/agents/synthesizer.py` — Sonnet report generation (outputs Markdown)
- `dashboard/index.html` — current dashboard

### What I Need

#### 1. Interactive Dashboard (upgrade `dashboard/index.html`)

Replace the current static dashboard with a proper interactive UI (still single HTML file with inline CSS/JS, no build tools needed). Requirements:

- **Report generation controls:**
  - "Generate Weekly Report" button with a date picker for the week (default: last 7 days)
  - "Generate Monthly Report" button with a month picker (default: last 30 days)
  - Loading spinner while the pipeline runs (it takes 30-60 seconds)
  - Show success/error feedback

- **Report browsing:**
  - List of all generated reports (weekly and monthly tabs)
  - Click a report to view it rendered as HTML (not raw markdown)
  - Quality score badge, revision count, date range for each report

- **Download button** on each report (download as styled HTML file)

- **Pipeline status section:**
  - Item count, scored count, signal count
  - "Run Daily Pipeline" button (ingest + filter + signals)
  - Last ingestion timestamp

- Keep the dark theme aesthetic (current colors: `#0f172a` background, `#1e293b` cards, `#38bdf8` accents)

#### 2. HTML Report Rendering (backend changes)

- **Add `markdown` or `markdown-it` rendering:** After the synthesizer generates `content_md`, convert it to `content_html` and store both in the DB
- **Update the API:** Add `content_html` to `ReportResponse` model and populate it
- **Update `db.py`:** The `insert_report` function should accept and store `content_html`
- **Update the report generation endpoint** in `main.py` to render markdown → HTML before storing
- Add a **download endpoint**: `GET /reports/{id}/download` that returns a self-contained styled HTML file

For markdown → HTML conversion, add the `markdown` package (`uv add markdown`) and use it with extensions like `tables`, `fenced_code`, `codehilite`.

#### 3. QMD Report Template

Create `agent_service/templates/report.qmd` — a Quarto template that can render reports beautifully. The template should:

- Use this YAML header:
```yaml
---
title: "{title}"
subtitle: "AI Trends Explorer | {report_type} Report"
author: "AI Trends Explorer"
date: "{date}"
format:
  html:
    theme: cosmo
    toc: true
    toc-depth: 3
    toc-location: left
    embed-resources: true
    smooth-scroll: true
    code-fold: true
---
```

- Have sections for: Executive Summary, Research Highlights, Industry Moves, Open Source & Tools, Trend Signals, Outlook
- Use Quarto callout blocks for key insights (`::: {.callout-tip}`, `::: {.callout-important}`)
- Add a metadata footer with quality score, revision count, items analyzed, period covered

Also create an API endpoint `GET /reports/{id}/qmd` that returns the report content rendered into this QMD template (so I can download and render with `quarto render`).

### Technical Notes

- **Package manager:** Use `uv add` for new dependencies, never pip
- **Python 3.12+**, type hints everywhere
- **All DB operations** go through `agent_service/db.py` (raw psycopg2, no ORM)
- **Pydantic models** for all API request/response schemas
- The `generate_report` endpoint in `main.py` currently accepts `report_type` as a query param. Extend it to also accept `period_start` and `period_end` as optional query params (default to last 7/30 days)
- The `content_html` column already exists in the DB schema but is never populated — start using it
- Don't create a separate frontend project or use npm/node — keep it as a single `index.html` with inline everything
- Use a CSS library loaded via CDN if needed (e.g., `marked.js` for client-side markdown rendering as a fallback)
