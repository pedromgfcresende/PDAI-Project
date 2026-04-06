# AI Trends Explorer — Test Instructions

## Prerequisites

- **Python 3.12+** installed
- **uv** installed (`brew install uv`)
- **direnv** installed (`brew install direnv`)
- **Docker** runtime installed (OrbStack or Docker Desktop)
- **Quarto** installed (`brew install --cask quarto`) — optional, for QMD report rendering

---

## 1. Clone & Setup Environment

```bash
git clone <repo-url>
cd PDAI-Project
```

### Configure direnv (one-time setup)

```bash
# Add direnv hook to your shell (only needed once, ever)
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc

# Allow the project's .envrc
direnv allow
```

This sets `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/PDAI-Project"` so the virtual environment lives outside OneDrive (avoids sync issues).

### Install dependencies

```bash
uv sync
```

Verify it works:

```bash
uv run python -c "import langchain, fastapi; print('OK')"
```

---

## 2. Configure API Keys

```bash
cp .env.example .env
```

Edit `.env` with your keys:

| Variable | Required | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `GROQ_API_KEY` | **Yes** | [console.groq.com](https://console.groq.com) → API Keys |
| `GOOGLE_AI_API_KEY` | Recommended | [aistudio.google.com](https://aistudio.google.com) → Get API Key (free, used as critic fallback) |
| `LANGCHAIN_API_KEY` | Optional | [smith.langchain.com](https://smith.langchain.com) → Settings → API Keys (for tracing) |
| `GITHUB_TOKEN` | Optional | GitHub → Settings → Developer settings → Personal access tokens (raises rate limit) |

All `DB_*` values work as-is with the default Docker Compose setup. Don't change them.

---

## 3. Start Infrastructure

Open OrbStack (or Docker Desktop), then:

```bash
docker compose up -d
```

This starts:
- **PostgreSQL + pgvector** on port 5432
- **n8n** on port 5678 (workflow engine, optional)

Verify:

```bash
docker compose ps
```

Both containers should show `running` / `healthy`.

---

## 4. Start the API Server

```bash
uv run uvicorn agent_service.main:app --reload --port 8000
```

> **Important:** If you see the server restarting in a loop (WatchFiles detecting changes in `.venv`), it means a local `.venv` was created by mistake. Fix: `rm -rf .venv` and restart.

Verify:

```bash
# In another terminal
curl http://localhost:8000/health
```

Expected:

```json
{
  "status": "ok",
  "db_connected": true,
  "items_count": 0,
  "scored_count": 0,
  "reports_count": 0,
  "signal_count": 0
}
```

---

## 5. Test the Pipeline Step by Step

### Step 1: Ingest data (no API keys needed)

```bash
# Ingest from arXiv (AI/ML papers)
curl -X POST http://localhost:8000/ingest/arxiv

# Ingest from RSS feeds (AI news)
curl -X POST http://localhost:8000/ingest/rss

# Ingest from all sources at once
curl -X POST http://localhost:8000/ingest
```

Check item count:

```bash
curl http://localhost:8000/health
# items_count should be > 0
```

### Step 2: Score items with Filter Agent (requires ANTHROPIC_API_KEY)

```bash
# Score 10 items (quick test)
curl -X POST "http://localhost:8000/filter?limit=10"
```

Expected:

```json
{
  "scored": 10,
  "avg_relevance": 0.6,
  "avg_novelty": 0.35
}
```

> **Note:** There's a 1.5s delay between calls to stay under Haiku's 50 req/min rate limit. Scoring 50 items takes ~75 seconds.

### Step 3: Detect trend signals (requires ANTHROPIC_API_KEY)

```bash
curl -X POST http://localhost:8000/signals/detect
```

### Step 4: Generate a weekly report (requires ANTHROPIC_API_KEY + GROQ_API_KEY)

```bash
curl -X POST "http://localhost:8000/reports/generate?report_type=weekly"
```

This runs the full writer-critic pipeline:
1. **Synthesis Agent** (Claude Sonnet) writes a draft
2. **Critic Agent** (Groq Llama, falls back to Gemini Flash) reviews it
3. If score < 7/10, the draft is revised (max 2 retries)
4. Final report is stored in the database

Takes 30-60 seconds. Expected response includes `title`, `content_md`, `content_html`, `quality_score`.

### Step 5: Generate with custom date range

```bash
curl -X POST "http://localhost:8000/reports/generate?report_type=weekly&period_start=2026-03-20&period_end=2026-03-27"
```

---

## 6. Full Pipeline (all steps at once)

```bash
# Daily: ingest + filter + signals
curl -X POST http://localhost:8000/pipeline/daily

# Weekly: daily + generate weekly report
curl -X POST http://localhost:8000/pipeline/weekly

# Monthly: daily + generate monthly report
curl -X POST http://localhost:8000/pipeline/monthly
```

---

## 7. View Reports

### Dashboard

Open the dashboard in your browser:

```bash
open dashboard/index.html
```

The dashboard connects to `http://localhost:8000` and shows:
- Health status (items, scored, reports, signals)
- Action buttons (Run Daily Pipeline, Generate Weekly/Monthly Report)
- Report list with quality scores
- Click a report to view it rendered as HTML
- Download button for each report

### API endpoints

```bash
# List weekly reports
curl http://localhost:8000/reports?report_type=weekly

# Download report as styled HTML
curl http://localhost:8000/reports/1/download -o report.html
open report.html

# Export as Quarto document
curl http://localhost:8000/reports/1/qmd -o report.qmd
quarto render report.qmd  # requires Quarto installed
```

---

## 8. LangGraph Studio (optional)

Visualize the writer-critic pipeline interactively:

```bash
uv run langgraph dev
```

Opens at `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024` (requires LangSmith login).

---

## 9. n8n Workflows (optional)

1. Open `http://localhost:5678` in your browser
2. Create an owner account on first launch
3. Import workflows from `n8n-workflows/`:
   - `daily-ingest.json` — Cron: daily 6am → calls `/pipeline/daily`
   - `weekly-briefing.json` — Cron: Friday 8am → calls `/pipeline/weekly`
   - `monthly-report.json` — Cron: 1st of month 8am → calls `/pipeline/monthly`

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check with item/report counts |
| POST | `/ingest/{source}` | Ingest from: `arxiv`, `semantic_scholar`, `rss`, `github` |
| POST | `/ingest` | Ingest from all sources |
| POST | `/filter?limit=N` | Score N unscored items with Haiku |
| POST | `/signals/detect` | Detect trend signals from scored items |
| GET | `/signals` | List active signals |
| POST | `/reports/generate?report_type=weekly` | Generate report (with optional `period_start`, `period_end`) |
| GET | `/reports?report_type=weekly&limit=10` | List reports |
| GET | `/reports/{id}/download` | Download report as styled HTML |
| GET | `/reports/{id}/qmd` | Export report as Quarto document |
| POST | `/pipeline/daily` | Full daily pipeline |
| POST | `/pipeline/weekly` | Daily + weekly report |
| POST | `/pipeline/monthly` | Daily + monthly report |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `uv sync` creates `.venv` locally | Run `direnv allow` first, or `source .envrc` before `uv sync` |
| Server restarts in a loop | Delete local `.venv`: `rm -rf .venv` |
| `429 rate limit` on Haiku | Wait a minute — the retry logic handles it automatically |
| `429 rate limit` on Groq | Critic falls back to Gemini Flash automatically (needs `GOOGLE_AI_API_KEY`) |
| `model not found` error | Check model IDs — Haiku: `claude-haiku-4-5-20251001`, Sonnet: `claude-sonnet-4-5-20250929` |
| Dashboard doesn't show data | Make sure the API server is running on port 8000 |
| Docker containers won't start | Open OrbStack/Docker Desktop first |
| `port 2024 already in use` (langgraph) | `lsof -ti:2024 \| xargs kill -9` |

---

## Architecture

```
User / Dashboard
       │
       ▼
   FastAPI (port 8000)
       │
       ├── Ingestion: arXiv, Semantic Scholar, RSS, GitHub
       │       │
       │       ▼
       ├── Filter Agent (Claude Haiku) → scores relevance & novelty
       │       │
       │       ▼
       ├── Signal Detection (Claude Haiku) → trend patterns
       │       │
       │       ▼
       └── Report Pipeline (LangGraph)
               │
               ├── Synthesis Agent (Claude Sonnet) → writes draft
               ├── Critic Agent (Groq Llama / Gemini Flash) → reviews
               └── Loop: revise if score < 7 (max 2 retries)
                       │
                       ▼
                   PostgreSQL + pgvector
```
