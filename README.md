# AI Trends Explorer

A multi-agent system that automatically collects AI research papers, news, and signals from public sources, filters out noise, and produces actionable intelligence reports.

**Final project** for Prototyping Products with AI (PDAI) at ESADE Business School.
**Team:** Group A | MiBA Second Term, 2025.

## What It Does

| Output | Frequency | Description |
|--------|-----------|-------------|
| **Weekly Briefing** | Every Friday | Concise synthesis of the most important AI developments |
| **Monthly Deep Report** | 1st of each month | Comprehensive trend analysis with strategic signals |

Reports are viewable on the dashboard and exportable as styled HTML or Quarto documents.

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

## Multi-Agent Pipeline

The system uses three specialized agents in a **writer-critic loop** powered by LangGraph:

| Agent | Model | Role |
|-------|-------|------|
| **Filter Agent** | Claude Haiku 4.5 | Scores relevance (0-1) and novelty (0-1), discards noise |
| **Synthesis Agent** | Claude Sonnet 4.6 | Writes weekly briefings and monthly reports |
| **Critic Agent** | Groq Llama 3.3 70B | Adversarial review on grounding, coherence, completeness, actionability |

The critic uses a **different model family** (Llama vs Claude) intentionally -- same-model review tends to approve its own mistakes. Reports must score >= 7/10 or get revised (max 2 retries).

## Data Sources

All free APIs:

- **arXiv** -- AI/ML papers (cs.AI, cs.LG, cs.CL)
- **Semantic Scholar** -- Paper metadata, citations
- **AI News RSS** -- TechCrunch, VentureBeat, MIT Tech Review, and more (10 feeds)
- **Company Blogs** -- Google AI, Meta AI, OpenAI, Anthropic
- **GitHub Trending** -- Hot AI repos and tools

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | LangGraph + LangChain |
| Backend API | FastAPI |
| Workflow Engine | n8n (self-hosted, optional) |
| Database | PostgreSQL + pgvector (Docker) |
| Embeddings | all-MiniLM-L6-v2 (local, CPU) |
| Observability | LangSmith |
| Dashboard | Static HTML + vanilla JS |
| Package Manager | uv |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) installed
- [Docker](https://www.docker.com/) for local infrastructure (OrbStack or Docker Desktop)
- API keys: Anthropic, Groq (optional: Google AI, GitHub)

### Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/PDAI-Project.git
cd PDAI-Project

# Set up centralized venv with direnv (keeps .venv outside OneDrive)
echo "export UV_PROJECT_ENVIRONMENT=\"\$HOME/.venvs/$(basename $PWD)\"" > .envrc && direnv allow

# Install dependencies
uv sync

# Copy environment variables and add your API keys
cp .env.example .env

# Start local infrastructure (Postgres + n8n)
docker compose up -d

# Run the agent service
uv run uvicorn agent_service.main:app --reload --port 8000

# Open the dashboard
open dashboard/index.html
```

## Project Structure

```
PDAI-Project/
├── docker-compose.yml             # PostgreSQL + n8n
├── Dockerfile                     # Agent service container
├── .env.example                   # Environment template
├── pyproject.toml                 # Dependencies
├── uv.lock                       # Lock file
├── init-db.sql                   # Database schema
├── langgraph.json                # LangGraph config
│
├── agent_service/                # Python backend
│   ├── main.py                   # FastAPI endpoints
│   ├── config.py                 # Settings
│   ├── models.py                 # Pydantic schemas
│   ├── db.py                     # Database operations
│   ├── agents/
│   │   ├── pipeline.py           # LangGraph writer-critic loop
│   │   ├── filter.py             # Relevance scoring (Haiku)
│   │   ├── synthesizer.py        # Report writing (Sonnet)
│   │   ├── critic.py             # Quality review (Groq Llama)
│   │   └── signals.py            # Trend detection
│   ├── ingestion/
│   │   ├── arxiv_source.py
│   │   ├── semantic_scholar.py
│   │   ├── rss_news.py
│   │   ├── github_trending.py
│   │   └── normalize.py
│   └── prompts/                  # System prompts for each agent
│
├── n8n-workflows/                # Scheduling workflows (optional)
│
└── dashboard/
    └── index.html                # Static dashboard
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check with item/report counts |
| POST | `/ingest/{source}` | Ingest from: `arxiv`, `semantic_scholar`, `rss`, `github` |
| POST | `/ingest` | Ingest from all sources |
| POST | `/filter?limit=N` | Score N unscored items with Haiku |
| POST | `/signals/detect` | Detect trend signals from scored items |
| GET | `/signals` | List active signals |
| POST | `/reports/generate?report_type=weekly` | Generate report (writer-critic pipeline) |
| GET | `/reports?report_type=weekly&limit=10` | List reports |
| GET | `/reports/{id}/download` | Download report as styled HTML |
| GET | `/reports/{id}/qmd` | Export report as Quarto document |
| POST | `/pipeline/daily` | Full daily pipeline (ingest + filter + signals) |
| POST | `/pipeline/weekly` | Daily + weekly report |
| POST | `/pipeline/monthly` | Daily + monthly report |

## Cost Strategy (~$13-19/month)

| Role | Model | Monthly Cost |
|------|-------|-------------|
| Filtering | Claude Haiku 4.5 ($1/MTok) | ~$2-3 |
| Synthesis | Claude Sonnet 4.6 ($3/MTok) | ~$8-12 |
| Monthly reports | Sonnet Batch API (50% off) | ~$3-4 |
| Critic | Groq Llama 3.3 70B | $0 (free) |
| Embeddings | all-MiniLM-L6-v2 (local) | $0 |

## License

Final project -- ESADE Business School, MiBA 2025.
