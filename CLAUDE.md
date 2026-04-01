# CLAUDE.md — AI Trends Explorer

## Project Overview

**AI Trends Explorer** — A multi-agent system that automatically collects AI research papers, news, and signals from public sources, filters out noise, and produces:

1. **Weekly Briefing** — Concise synthesis of the most important AI developments
2. **Monthly Deep Report** — Comprehensive trend analysis with strategic signals

University project for **Prototyping Products with AI (PDAI)** at ESADE Business School.
Student: **Pedro Resende** | MiBA Second Term | 2-3 week build timeline.

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
┌──────────────────────────────────────────────────┐
│             SCHEDULED TRIGGERS (cron)              │
│         Daily ingestion + Weekly/Monthly synth     │
└──────────────┬───────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────┐
│          n8n (Workflow Orchestration)              │
│                                                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ Ingest  │→ │ Filter  │→ │ Store   │           │
│  │ Sources │  │ & Score │  │ in DB   │           │
│  └─────────┘  └─────────┘  └─────────┘           │
│                                                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │Synthesize│→│ Critic  │→ │ Deliver │           │
│  │ (LLM)   │  │ (LLM)  │  │ Email/  │           │
│  │         │← │ Review  │  │ PDF     │           │
│  └─────────┘  └─────────┘  └─────────┘           │
└──────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────┐
│  PostgreSQL + pgvector (items, embeddings, reports)│
└──────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────┐
│     Simple Dashboard (Next.js or plain HTML)       │
│     Browse items, read reports, download PDFs      │
└──────────────────────────────────────────────────┘
```

---

## Tech Stack & Model Routing

### LLM Budget Strategy (~€20-25/month)

| Role | Model | Cost | Why |
|------|-------|------|-----|
| Filtering & classification | **Claude Haiku 4.5** | ~$2-3/mo | Fast, cheap, great for scoring relevance |
| Synthesis (weekly briefings) | **Claude Sonnet 4.6** | ~$8-12/mo | Best quality-to-cost ratio for writing |
| Monthly deep report | **Claude Sonnet 4.6 Batch API** | ~$3-4/mo | 50% discount, reports aren't urgent |
| Critic / quality review | **Groq Llama 3.3 70B** | $0 | Free, different model family = better cross-validation |
| Embeddings | **all-MiniLM-L6-v2** (local) | $0 | Runs on CPU via sentence-transformers |
| Backup / experiments | **Gemini 2.0 Flash** (free tier) | $0 | Fallback for exploratory analysis |

### Infrastructure (All Free)

| Component | Choice |
|-----------|--------|
| Workflow engine | n8n (self-hosted Docker) |
| Database | PostgreSQL + pgvector (Docker) |
| Agent framework | LangGraph (with LangChain) |
| Observability | LangSmith free tier (5,000 traces/month) |
| Email delivery | Resend free tier (3,000 emails/month) |
| Deployment | Docker Compose on local machine |

---

## Project Structure

```
ai-trends-explorer/
├── docker-compose.yml
├── .env.example
├── .env                           # Never committed — API keys
├── pyproject.toml                 # uv project config
├── uv.lock                       # Committed for reproducibility
├── init-db.sql                   # PostgreSQL schema
│
├── agent-service/                # Python backend (FastAPI + LangGraph)
│   ├── Dockerfile
│   ├── main.py                   # FastAPI endpoints
│   ├── agents/
│   │   ├── filter.py             # Relevance scoring (Haiku)
│   │   ├── synthesizer.py        # Report writing (Sonnet)
│   │   ├── critic.py             # Quality review (Groq Llama)
│   │   └── signals.py            # Pattern detection
│   ├── ingestion/
│   │   ├── arxiv_source.py
│   │   ├── semantic_scholar.py
│   │   ├── rss_news.py
│   │   ├── github_trending.py
│   │   └── normalize.py          # Common schema
│   ├── models.py                 # Pydantic schemas
│   └── prompts/
│       ├── filter.txt
│       ├── weekly_synthesis.txt
│       ├── monthly_report.txt
│       └── critic.txt
│
├── n8n-workflows/                # Exported n8n workflow JSON files
│   ├── daily-ingest.json
│   ├── weekly-briefing.json
│   └── monthly-report.json
│
└── dashboard/                    # Optional simple frontend
    └── ...
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

The writer-critic loop is implemented as a LangGraph `StateGraph` with conditional edges. See the blueprint for the full code pattern.

---

## Data Sources (All Free)

| Source | What | Access | Frequency |
|--------|------|--------|-----------|
| arXiv | AI/ML papers | `arxiv` Python package or RSS (cs.AI, cs.LG, cs.CL) | Daily |
| Semantic Scholar | Paper metadata, citations | REST API (no auth, 1000 req/sec) | Daily |
| HuggingFace | Trending models, datasets | API + trending page | Daily |
| AI news RSS | TechCrunch, VentureBeat, etc. | Standard RSS parsing | Every few hours |
| Company blogs | Google AI, Meta AI, OpenAI, Anthropic | RSS feeds | As published |
| GitHub Trending | Hot AI repos and tools | GitHub API (5000 req/hr with token) | Daily |

---

## Database (PostgreSQL + pgvector)

Three main tables:
- **`items`** — All ingested items with embeddings (vector(384)), relevance scores, topics
- **`reports`** — Generated weekly briefings and monthly reports with quality scores
- **`signals`** — Detected trend signals (emergence, acceleration, disruption)

Schema lives in `init-db.sql`.

---

## n8n Workflows

| Workflow | Trigger | Action |
|----------|---------|--------|
| `daily-ingest` | Cron: daily 6am | Pull all sources → normalize → store in Postgres |
| `weekly-briefing` | Cron: Friday 8am | Fetch week's items → LangGraph pipeline → email |
| `monthly-report` | Cron: 1st of month 8am | Fetch month's items → deep analysis → PDF/HTML |

n8n calls the LangGraph pipeline via HTTP Request node → FastAPI backend.

---

## Environment Variables

```bash
# .env (never committed)
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GOOGLE_AI_API_KEY=...              # Gemini backup
DB_PASSWORD=changeme

# LangSmith (optional but recommended)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=ai-trends-explorer

# GitHub (for trending source)
GITHUB_TOKEN=ghp_...
```

---

## Running the Stack

```bash
# Start infrastructure
docker compose up -d

# Access n8n
open http://localhost:5678

# Access agent API
open http://localhost:8000

# Run agent service locally (dev mode)
uv run uvicorn agent-service.main:app --reload --port 8000

# Run LangGraph dev server
uv run langgraph dev
```

---

## Cost Optimization

1. **Prompt caching** — Claude's 90% savings on repeated system prompts
2. **Batch API** — 50% off for non-urgent work (monthly reports, bulk re-scoring)
3. **Haiku as gatekeeper** — Every item goes through Haiku first; only high-scorers reach Sonnet
4. **Structured output** — Force JSON responses to keep outputs concise
5. **Token budgets** — Set `max_tokens` explicitly on every call

---

## Key Dependencies

```
langchain
langgraph
langchain-anthropic
langchain-groq
langchain-google-genai
langsmith
fastapi
uvicorn
psycopg2-binary
pgvector
sentence-transformers
arxiv
feedparser
httpx
pydantic
python-dotenv
```

---

## Code Conventions

- Python 3.12+
- Use `load_dotenv()` at the top of every file
- Tools return error strings (not raise exceptions) for graceful agent retries
- MCP operations use `await` / `ainvoke`
- Always set `checkpointer` when using memory or persistent state
- Use `thread_id` in config for conversation continuity
- Type hints everywhere, Pydantic models for data schemas
