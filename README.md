# AI Trends Explorer

A multi-agent system that automatically collects AI research papers, news, and signals from public sources, filters out noise, and produces actionable intelligence reports.

**University project** for Prototyping Products with AI (PDAI) at ESADE Business School.

## Architecture

[![AWS Infrastructure](https://storage.googleapis.com/second-petal-295822.appspot.com/elements/autoDiagram%3A08c825e9ab60d83bf3e5b1c277046a6a4a111d79f2e92867cc4909df58502056.png)](https://app.eraser.io/workspace/37qJnP2t9fLeBYLLdhv2)

> [View full diagram on Eraser](https://app.eraser.io/workspace/37qJnP2t9fLeBYLLdhv2)

## What It Does

| Output | Frequency | Description |
|--------|-----------|-------------|
| **Weekly Briefing** | Every Friday | Concise synthesis of the most important AI developments |
| **Monthly Deep Report** | 1st of each month | Comprehensive trend analysis with strategic signals |

Both delivered via email (Amazon SES) and viewable on a static dashboard (S3 + CloudFront).

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
- **HuggingFace** -- Trending models and datasets
- **AI News RSS** -- TechCrunch, VentureBeat, Ars Technica
- **Company Blogs** -- Google AI, Meta AI, OpenAI, Anthropic
- **GitHub Trending** -- Hot AI repos and tools

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | LangGraph + LangChain |
| Backend API | FastAPI |
| Workflow Engine | n8n (self-hosted) |
| Database | PostgreSQL + pgvector |
| Embeddings | all-MiniLM-L6-v2 (local, CPU) |
| Observability | LangSmith |
| Infrastructure | AWS (ECS Fargate, RDS, S3, CloudFront, SES, EventBridge) |
| Package Manager | uv |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) installed
- [Docker](https://www.docker.com/) for local infrastructure
- API keys: Anthropic, Groq, (optional: Google AI, GitHub)

### Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/PDAI-Project.git
cd PDAI-Project

# Set up centralized venv with direnv
echo "export UV_PROJECT_ENVIRONMENT=\"\$HOME/.venvs/$(basename $PWD)\"" > .envrc && direnv allow

# Install dependencies
uv sync

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Start local infrastructure (Postgres + n8n)
docker compose up -d

# Run the agent service
uv run uvicorn agent-service.main:app --reload --port 8000
```

## Project Structure

```
PDAI-Project/
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── uv.lock
├── init-db.sql
│
├── agent-service/
│   ├── main.py                  # FastAPI endpoints
│   ├── agents/
│   │   ├── filter.py            # Relevance scoring (Haiku)
│   │   ├── synthesizer.py       # Report writing (Sonnet)
│   │   ├── critic.py            # Quality review (Groq Llama)
│   │   └── signals.py           # Pattern detection
│   ├── ingestion/
│   │   ├── arxiv_source.py
│   │   ├── semantic_scholar.py
│   │   ├── rss_news.py
│   │   ├── github_trending.py
│   │   └── normalize.py
│   ├── models.py
│   └── prompts/
│       ├── filter.txt
│       ├── weekly_synthesis.txt
│       ├── monthly_report.txt
│       └── critic.txt
│
├── n8n-workflows/
│   ├── daily-ingest.json
│   ├── weekly-briefing.json
│   └── monthly-report.json
│
└── dashboard/
```

## Cost Strategy (~$13-19/month)

| Role | Model | Monthly Cost |
|------|-------|-------------|
| Filtering | Claude Haiku 4.5 ($1/MTok) | ~$2-3 |
| Synthesis | Claude Sonnet 4.6 ($3/MTok) | ~$8-12 |
| Monthly reports | Sonnet Batch API (50% off) | ~$3-4 |
| Critic | Groq Llama 3.3 70B | $0 (free) |
| Embeddings | all-MiniLM-L6-v2 (local) | $0 |

## License

University project -- ESADE Business School, MiBA 2025.
