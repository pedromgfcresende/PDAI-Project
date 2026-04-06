# CLAUDE.md — AI Trends Explorer

## Project Overview

**AI Trends Explorer** — A multi-agent system that automatically collects AI research papers, news, and signals from public sources, filters out noise, and produces:

1. **Weekly Briefing** — Concise synthesis of the most important AI developments
2. **Monthly Deep Report** — Comprehensive trend analysis with strategic signals

Final project for **Prototyping Products with AI (PDAI)** at ESADE Business School.
Team: **Group A** | MiBA Second Term.

---

## Package Management

This project uses **uv** as the Python package manager with virtual environments.

### Initial Setup

```bash
# Set up centralized venv location (run once per project)
echo "export UV_PROJECT_ENVIRONMENT=\"\$HOME/.venvs/$(basename $PWD)\"" > .envrc && direnv allow

# Install dependencies
uv sync

# Run any Python script
uv run python <script.py>

# Add a new dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>
```

### Key Rules

- **Always use `uv run`** to execute Python commands — never activate venv manually
- **Always use `uv add`** to add dependencies — never `pip install`
- **`uv.lock`** is committed to version control for reproducibility
- **`.envrc`** handles automatic venv activation via direnv

---

## Architecture

```
User / Dashboard (static HTML)
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

---

## Tech Stack & Model Routing

### LLM Budget Strategy (~$13-19/month)

| Role | Model | Cost | Why |
|------|-------|------|-----|
| Filtering & classification | **Claude Haiku 4.5** | ~$2-3/mo | Fast, cheap, great for scoring relevance |
| Synthesis (weekly briefings) | **Claude Sonnet 4.6** | ~$8-12/mo | Best quality-to-cost ratio for writing |
| Monthly deep report | **Claude Sonnet 4.6 Batch API** | ~$3-4/mo | 50% discount, reports aren't urgent |
| Critic / quality review | **Groq Llama 3.3 70B** | $0 | Free, different model family = better cross-validation |
| Embeddings | **all-MiniLM-L6-v2** (local) | $0 | Runs on CPU via sentence-transformers |
| Backup / experiments | **Gemini 2.0 Flash** (free tier) | $0 | Fallback for critic when Groq is unavailable |

### Infrastructure (All Free / Local)

| Component | Choice |
|-----------|--------|
| Scheduling | AWS Lambda + EventBridge (production) |
| Database | PostgreSQL + pgvector (Docker) |
| Agent framework | LangGraph (with LangChain) |
| Observability | LangSmith free tier (5,000 traces/month) |
| Dashboard | Static HTML served locally |
| Deployment | Docker Compose on local machine |

---

## Project Structure

```
PDAI-Project/
├── docker-compose.yml             # PostgreSQL (local infra)
├── Dockerfile                     # Container image for agent service
├── .env.example                   # Environment template
├── .env                           # Never committed — API keys
├── pyproject.toml                 # uv project config
├── uv.lock                       # Committed for reproducibility
├── init-db.sql                   # PostgreSQL schema (3 tables)
├── langgraph.json                # LangGraph dev server config
│
├── agent_service/                # Python backend (FastAPI + LangGraph)
│   ├── main.py                   # FastAPI endpoints & pipeline orchestration
│   ├── config.py                 # Settings & env vars
│   ├── models.py                 # Pydantic schemas
│   ├── db.py                     # PostgreSQL operations
│   ├── agents/
│   │   ├── pipeline.py           # LangGraph writer-critic loop
│   │   ├── filter.py             # Relevance scoring (Haiku)
│   │   ├── synthesizer.py        # Report writing (Sonnet)
│   │   ├── critic.py             # Quality review (Groq Llama)
│   │   └── signals.py            # Trend signal detection
│   ├── ingestion/
│   │   ├── arxiv_source.py       # arXiv papers
│   │   ├── semantic_scholar.py   # Paper metadata & citations
│   │   ├── rss_news.py           # AI news feeds
│   │   ├── github_trending.py    # Trending AI repos
│   │   └── normalize.py          # Common schema + embeddings
│   └── prompts/
│       ├── filter.txt            # Relevance scoring prompt
│       ├── weekly_synthesis.txt  # Weekly briefing prompt
│       ├── monthly_report.txt    # Monthly report prompt
│       └── critic.txt            # Quality review prompt
│
├── lambda-triggers/              # AWS Lambda functions for scheduling
│   ├── daily_ingest.py           # EventBridge: daily → /pipeline/daily
│   ├── weekly_report.py          # EventBridge: Friday → /pipeline/weekly + SES email
│   └── monthly_report.py         # EventBridge: 1st of month → /pipeline/monthly + SES email
│
└── dashboard/
    └── index.html                # Static dashboard (HTML + JS)
```

---

## Multi-Agent Pipeline

### Agent Roles

| Agent | Model | Purpose |
|-------|-------|---------|
| **Filter Agent** | Claude Haiku 4.5 | Scores relevance (0-1) and novelty (0-1), discards junk |
| **Synthesis Agent** | Claude Sonnet 4.6 | Writes weekly briefings and monthly reports |
| **Critic Agent** | Groq Llama 3.3 70B | Adversarial review — scores grounding, coherence, completeness, actionability |

### Writer-Critic Loop

```
Synthesis Agent writes draft
        │
        ▼
Critic Agent reviews (scores 0-10 on 4 dimensions)
        │
   ┌────┴────┐
   │         │
Score ≥ 7   Score < 7
   │         │
   ▼         ▼
 PUBLISH   Feedback → Synthesis Agent rewrites
                      (max 2 retries, then publish with warning)
```

The critic uses a **different model family** (Llama vs Claude) intentionally — same-model review tends to approve its own mistakes.

### Implementation: LangGraph

The writer-critic loop is implemented as a LangGraph `StateGraph` with conditional edges. The graph flow: `synthesize → critique → (approved → publish) | (retry → synthesize) | (force_publish)`.

---

## Data Sources (All Free)

| Source | What | Access |
|--------|------|--------|
| arXiv | AI/ML papers | `arxiv` Python package (cs.AI, cs.LG, cs.CL) |
| Semantic Scholar | Paper metadata, citations | REST API (no auth) |
| AI news RSS | TechCrunch, VentureBeat, MIT Tech Review, etc. | Standard RSS parsing (10 feeds) |
| Company blogs | Google AI, Meta AI, OpenAI, Anthropic | RSS feeds |
| GitHub Trending | Hot AI repos and tools | GitHub API |

---

## Database (PostgreSQL + pgvector)

Three main tables:
- **`items`** — All ingested items with embeddings (vector(384)), relevance scores, topics
- **`reports`** — Generated weekly briefings and monthly reports with quality scores
- **`signals`** — Detected trend signals (emergence, acceleration, disruption)

Schema lives in `init-db.sql`.

---

## Scheduling (AWS Lambda + EventBridge)

For production, three Lambda functions replace manual dashboard triggers:

| Function | Schedule | Action |
|----------|----------|--------|
| `daily_ingest.py` | Every day 06:00 UTC | Ingest → filter → detect signals |
| `weekly_report.py` | Every Friday 08:00 UTC | Daily pipeline + weekly report + email via SES |
| `monthly_report.py` | 1st of month 08:00 UTC | Daily pipeline + monthly report + email via SES |

Each Lambda calls the FastAPI backend via HTTP, then sends the report HTML through Amazon SES. See `lambda-triggers/README.md` for deployment instructions.

---

## Environment Variables

```bash
# .env (never committed)
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GOOGLE_AI_API_KEY=...              # Gemini backup (optional)
DB_PASSWORD=changeme

# LangSmith (optional but recommended)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=ai-trends-explorer

# GitHub (optional — raises API rate limit)
GITHUB_TOKEN=ghp_...
```

---

## Running the Stack

```bash
# Start infrastructure (PostgreSQL)
docker compose up -d

# Run the agent service (dev mode)
uv run uvicorn agent_service.main:app --reload --port 8000

# Open the dashboard
open dashboard/index.html

# Run LangGraph dev server (optional — for pipeline visualization)
uv run langgraph dev
```

---

## Cost Optimization

1. **Haiku as gatekeeper** — Every item goes through Haiku first; only high-scorers reach Sonnet
2. **Batch API** — 50% off for non-urgent work (monthly reports, bulk re-scoring)
3. **Prompt caching** — Claude's 90% savings on repeated system prompts
4. **Structured output** — Force JSON responses to keep outputs concise
5. **Token budgets** — Set `max_tokens` explicitly on every call
6. **Free critic** — Groq Llama 3.3 70B is free and provides cross-model validation

---

## Key Dependencies

```
langchain, langgraph, langchain-anthropic, langchain-groq, langchain-google-genai
langsmith
fastapi, uvicorn
psycopg2-binary, pgvector
sentence-transformers
arxiv, feedparser, httpx
pydantic, pydantic-settings, python-dotenv
markdown
```

---

## Code Conventions

- Python 3.12+
- Use `load_dotenv()` at the top of every file
- Tools return error strings (not raise exceptions) for graceful agent retries
- Always set `checkpointer` when using memory or persistent state
- Use `thread_id` in config for conversation continuity
- Type hints everywhere, Pydantic models for data schemas
