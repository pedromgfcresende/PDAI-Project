# AI Trends Explorer — Final Project Report

**Prototyping Products with AI (PDAI) | ESADE Business School**
**Group A | MiBA Second Term, 2025**

---

## 1. The Problem

Consulting firms, investment teams, and technology strategists face the same problem: the AI landscape moves faster than any individual can track. Every week, hundreds of research papers are published on arXiv alone. Companies announce new models, open-source projects surge overnight, and funding rounds reshape competitive dynamics. A strategist who misses a single paradigm-shifting paper or a quietly announced product launch can give outdated advice. Yet reading everything is impossible — the volume of information is not the issue, the issue is that most of it is noise.

Current solutions fall short in different ways. Curated newsletters like The Batch or Import AI arrive weekly but reflect a single editor's judgment and cover only a fraction of developments. Analyst reports from firms like Gartner or McKinsey are thorough but appear quarterly and cost thousands. RSS readers and social media feeds provide raw volume but no filtering — a consultant monitoring 10 feeds still needs to read hundreds of articles to find the 5 that matter. None of these solutions combine breadth of coverage, speed of delivery, intelligent filtering, and quality-assured synthesis.

We asked: *what if an AI system could do the ingestion, filtering, and synthesis automatically — and deliver a concise, quality-reviewed intelligence report every week?*

The key insight is that this is not a single-LLM problem. A single prompt that says "summarize this week's AI news" produces hallucination-prone, shallow output. The problem decomposes naturally into specialized stages: broad data collection, intelligent relevance scoring, pattern detection across items, structured synthesis with source citations, and adversarial quality review. Each stage requires different capabilities and different cost-performance tradeoffs.

---

## 2. Our Approach

We built **AI Trends Explorer**, a multi-agent system that continuously monitors public AI data sources, filters out noise, detects emerging trend signals, and produces weekly and monthly intelligence reports through a writer-critic feedback loop.

### Design Principles

**Breadth at ingestion, selectivity at filtering.** We cast a wide net across four data sources, pulling up to ~265 items per run (45 arXiv papers, 150 RSS articles, 30 GitHub repositories, 40 Semantic Scholar papers). No relevance judgment is made during ingestion — the database receives everything. Filtering happens as a separate stage using an LLM-powered scoring agent, which means we can re-filter with different thresholds without re-ingesting, and the raw data remains available for semantic search regardless of its relevance score.

**Different models for different jobs.** We route each task to the most cost-effective model that can handle it. Claude Haiku 4.5 ($1/MTok input) handles the high-volume work: scoring every ingested item for relevance and novelty, and detecting trend signals. This is fast classification work where Haiku excels. Claude Sonnet 4.5 ($3/MTok input) writes the reports — this is creative synthesis requiring nuanced judgment and long-form coherence. Groq Llama 3.3 70B (free tier) reviews the reports as a critic. This last choice is deliberate: same-model review tends to approve its own blind spots, so we use a completely different model family for quality assurance.

**Writer-critic loop for quality assurance.** Reports are never published after a single pass. A critic agent scores each draft on four explicit dimensions (grounding, coherence, completeness, actionability) and provides specific feedback quoting exact sentences that should be changed. The writer revises up to twice before publication. This loop is implemented as a LangGraph StateGraph — a directed graph with typed state and conditional edges — not ad-hoc retry logic.

**Embeddings for semantic understanding.** Every ingested item is embedded using a local model (all-MiniLM-L6-v2, 384 dimensions) at ingestion time, with vectors stored in PostgreSQL via the pgvector extension. This enables semantic search across the full item database and powers the signal-to-item linking feature, where clicking a trend signal retrieves the most semantically related items via cosine similarity.

---

## 3. Data Ingestion: How We Retrieve Information

The system ingests data from four public sources. The strategy is to **retrieve the most recent items first, store everything, then filter for importance afterwards.** This separation is critical: it means the database always has a complete picture of what was published, and relevance judgments can be revised without re-ingesting.

### Sources in Detail

**arXiv (up to 45 papers per run).** We query three categories: cs.AI (Artificial Intelligence), cs.LG (Machine Learning), and cs.CL (Computation and Language). The `arxiv` Python package fetches the 15 most recently submitted papers per category, sorted by submission date descending. Each paper's full metadata is captured: title, abstract, authors, publication date, PDF URL, primary and secondary categories. The abstract serves as the item's summary for downstream filtering and embedding.

**RSS Feeds (up to 150 articles per run).** We monitor 10 feeds organized into three tiers. News outlets (TechCrunch AI, VentureBeat AI, MIT Technology Review) provide industry coverage. Company blogs (Google AI, OpenAI, Anthropic, Meta AI, HuggingFace) provide first-party announcements — these are often the earliest signal of new products and research directions. Industry feeds (Crunchbase News, SecurityWeek) cover funding rounds and security incidents. The `feedparser` library processes each feed, extracting the 15 most recent entries. HTML tags are stripped from article summaries, and content is truncated to 500 characters to keep embedding inputs consistent.

**GitHub Trending (up to 30 repositories per run).** We track six topics: machine-learning, deep-learning, large-language-models, artificial-intelligence, transformers, and generative-ai. The GitHub API returns the 5 most-starred repositories per topic that were pushed within the last 7 days and have more than 10 stars. This filters out abandoned projects and surfaces actively maintained tools. A runtime deduplication set prevents the same repository from appearing across multiple topics. Metadata includes star count, fork count, primary language, and repository topics.

**Semantic Scholar (up to 40 papers per run).** We search four queries — "artificial intelligence," "large language models," "machine learning," and "neural networks" — each returning the 10 most recent results via the Semantic Scholar REST API. This complements arXiv by capturing papers from conferences, journals, and preprint servers beyond arXiv. Metadata includes citation count and publication year, which are useful signals for identifying high-impact work.

### Normalization and Embedding

Every item, regardless of source, passes through a normalization function (`normalize_item`) that creates a standardized `IngestedItem` object. This function:

1. **Generates a deterministic source ID** using `{source}:{SHA256(unique_key)[:16]}`. The unique key varies by source (arXiv entry ID, article URL, repository full name, Semantic Scholar paper ID). This enables deduplication at the database level: the `items` table has a unique constraint on `source_id`, so `INSERT ... ON CONFLICT (source_id) DO NOTHING` silently skips duplicates.

2. **Normalizes timestamps to UTC.** Some sources return timezone-naive datetimes, others return various timezones. The `ensure_utc` function forces everything to UTC so that date-range queries (`WHERE published_at >= start AND published_at < end`) work correctly across sources.

3. **Computes a 384-dimensional embedding** by passing the concatenated `title + summary` through the `all-MiniLM-L6-v2` sentence-transformer model. This model runs locally on CPU with no API cost. The model is loaded once (lazy singleton pattern via a module-level `_model` variable) and reused across all embedding calls, since loading it takes ~2 seconds and ~500MB of RAM.

4. **Stores the item** in PostgreSQL including the embedding vector, raw metadata as JSONB, and the publication timestamp. The embedding is stored in a `vector(384)` column provided by pgvector, with an `ivfflat` index using `vector_cosine_ops` for fast approximate nearest-neighbor search.

---

## 4. The Multi-Agent Pipeline

The pipeline has four stages, each handled by a specialized agent. The stages run sequentially, with the output of each feeding into the next.

### Stage 1: Filter Agent

**Model:** Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | **Temperature:** 0 (deterministic) | **Max tokens:** 300

Every unscored item is sent to Claude Haiku with a system prompt that acts as an AI relevance filter. The model evaluates each item on two independent dimensions:

**Relevance (0.0–1.0)** measures how important the item is to current AI/ML trends, with explicit emphasis on business and strategic significance. The prompt lists specific categories to consider: breakthrough methods, new model architectures, significant benchmarks, industry applications, policy and safety developments, competitive dynamics, funding and market signals, and security incidents. The prompt instructs the model that "most items should score below 0.5 relevance" and "only genuinely important developments should score above 0.7."

**Novelty (0.0–1.0)** measures how surprising or new the item is. A well-known concept rehashed (e.g., a survey paper) scores near 0. A genuinely new approach or unexpected result scores high.

To stabilize scoring across batches, the prompt includes three few-shot calibration examples with detailed reasoning: a major model release (relevance: 0.92, novelty: 0.85), a survey paper (0.15, 0.05), and an incremental efficiency gain (0.55, 0.35). The prompt also includes today's date so the model can judge timeliness. The agent additionally assigns 1–3 topic tags from a fixed taxonomy of 19 categories (LLMs, agents, safety, efficiency, funding, etc.).

The filter processes items sequentially with a 1.5-second delay between calls (~40 requests/minute), safely under Haiku's rate limit. On 429 errors, exponential backoff kicks in (5s, 10s, 20s). JSON parsing failures trigger a graceful fallback: the item receives default scores of 0.3 for both dimensions rather than being lost.

Items with `relevance_score >= 0.5` are eligible for inclusion in reports. Items with `relevance_score >= 0.4` are included in signal detection (a slightly lower bar since patterns can emerge from moderately relevant items).

### Stage 2: Signal Detection

**Model:** Claude Haiku 4.5 | **Temperature:** 0.1 (slightly stochastic for creative pattern discovery) | **Max tokens:** 1024

The signal detector receives all scored items from the last 7 days (with relevance ≥ 0.4) formatted as a numbered list showing each item's ID, source, title, and topic tags. The model analyzes this batch to identify cross-cutting patterns, producing exactly 5 signals classified into three types:

- **Emergence** — A new topic or approach appearing for the first time across multiple sources. Example: "Neurosymbolic agent architectures" appearing in 4 unrelated papers.
- **Acceleration** — An existing trend gaining significantly more attention. Example: "Agentic AI systems" dominating both research papers and GitHub trending simultaneously.
- **Disruption** — Something challenging or replacing an established approach. Example: "Inference-time compute scaling replacing training-time scaling."

Each signal includes a strength score (0.0–1.0 confidence) and evidence IDs linking back to supporting items. The prompt explicitly requires signals to be distinct and non-overlapping — the model must merge related patterns. Before storing new signals, the system deactivates all previous signals (`UPDATE signals SET active = FALSE`) to prevent accumulation across runs.

A heuristic fallback (`detect_signals_simple`) is available when the LLM is unavailable. It uses a simple topic frequency counter: topics appearing in ≥3 items become "acceleration" signals with strength proportional to frequency.

### Stage 3: Synthesis Agent

**Model:** Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) | **Temperature:** 0.3 (creative but grounded) | **Max tokens:** 4096

The synthesis agent receives all items with relevance ≥ 0.5 for the report period, plus active trend signals. For weekly reports, the period is the last 7 days; for monthly reports, the last 30 days. Items are formatted with their source type, title, topic tags, URL, and a 300-character summary excerpt. Signals are formatted as a list showing type, topic, description, and strength.

The prompt establishes a specific persona: "an expert AI analyst at a consulting firm's internal intelligence team" writing for "technology leaders and business strategists." The required structure is:

1. **TL;DR** (3–5 bullet points) — The absolute must-know developments.
2. **Key Developments** — Prose analysis explaining *why* each development matters, not just what happened.
3. **Industry Moves** — Acquisitions, funding rounds, partnerships, competitive dynamics.
4. **Trend Signals** — Narrative connecting patterns across items.
5. **What to Watch Next Week** — Upcoming events and expected announcements.

The prompt enforces the system's most critical constraint: **the agent may only reference information from the provided source items.** It cannot introduce facts, metrics, company names, funding amounts, or benchmark scores from its training data. Every claim must be traceable to a specific source item, cited inline as `[Title](URL)`. If a section has insufficient material, it must be omitted rather than padded with generic commentary. This anti-hallucination guardrail is the single most important prompt engineering decision in the system.

On revision rounds, the critic's feedback is appended to the prompt under a "Critic Feedback" section, so the writer knows exactly what to fix.

### Stage 4: Critic Agent

**Primary model:** Llama 3.3 70B Versatile (via Groq, free tier) | **Fallback:** Gemini 2.0 Flash (via Google AI, free tier) | **Temperature:** 0 | **Max tokens:** 1024

The critic receives the complete draft report plus the full list of source items (formatted as a numbered list with source, title, and 200-character summary). It evaluates the draft on four dimensions, each scored 0–10:

**Grounding (0–10):** Are claims supported by the source items? The prompt requires the critic to identify at least 3 specific factual claims in the report (company names, metrics, funding amounts, benchmark scores, product features) and verify whether each one appears in the source items. Any claims that cannot be traced back to a source item must be listed as potential hallucinations. This is the primary defense against the synthesis agent introducing information from its training data.

**Coherence (0–10):** Is the report logically structured? Do sections flow naturally? Are there internal contradictions?

**Completeness (0–10):** Does the report cover the key developments from the source items? Are major items missing? This checks that the synthesis agent didn't cherry-pick easy topics while ignoring important ones.

**Actionability (0–10):** Can a reader act on the insights? Are recommendations specific enough to be useful? This pushes the report beyond description toward strategic advice.

The overall score is the average of all four dimensions. Reports scoring **≥ 7.0** are approved and published. Reports scoring below 7.0 receive feedback that must include (1) at least one exact sentence from the report that should be changed, and (2) a concrete rewrite suggestion. The prompt explicitly rejects vague feedback like "could be more actionable."

We use a different model family (Llama via Groq, not Claude via Anthropic) because same-model review tends to approve its own blind spots. A Claude model reviewing Claude-generated text shares the same training biases and will overlook errors that a Llama model catches. If Groq is rate-limited, the system falls back to Gemini 2.0 Flash. If both fail, the report receives default scores of 5.0 with a manual review recommendation.

### The Writer-Critic Loop (LangGraph StateGraph)

The synthesis-critique cycle is orchestrated as a **LangGraph StateGraph** — not ad-hoc retry logic, but a formally defined directed graph with typed state and conditional routing.

**State:** A `PipelineState` TypedDict carries all data through the graph: input fields (report type, date range, items, signals), working state (current draft title and content, critic feedback, retry count), and output fields (final title, content, quality score, approval status).

**Nodes:** Three functions that transform state:
- `synthesize_node` — Calls Claude Sonnet with the synthesis prompt. On first pass, feedback is empty. On revisions, critic feedback is included.
- `critique_node` — Calls Groq Llama with the critic prompt. Updates quality score, feedback, and approval status. Increments retry count.
- `publish_node` — Terminal node. Copies draft fields to final fields.

**Edges:** After `synthesize`, control always flows to `critique`. After `critique`, a conditional edge (`should_retry`) routes based on three conditions:
- `approved == true` → `publish` → END (quality bar met)
- `retry_count >= 2` → `publish` → END (exhausted retries, force-publish)
- Otherwise → `synthesize` (loop back with feedback)

This means a report goes through at most 3 synthesis passes and 2 critique passes. The compiled graph is instantiated once at import time as `report_pipeline` and invoked via `report_pipeline.invoke({...})` from the FastAPI endpoint.

---

## 5. Semantic Search: Using Embeddings with pgvector

Every ingested item has a 384-dimensional embedding stored alongside its structured data in PostgreSQL. The `all-MiniLM-L6-v2` model converts text into dense vectors that capture semantic meaning — similar concepts produce similar vectors regardless of exact wording.

### How It Works

The **search bar** on the dashboard implements vector similarity search: when a user types a query like "multimodal agents," the system:

1. **Computes the query's embedding** using the same `all-MiniLM-L6-v2` model and `compute_embedding()` function used during ingestion. This ensures the query vector lives in the same embedding space as the stored item vectors.

2. **Executes a pgvector cosine distance query:**
   ```sql
   SELECT id, source, title, summary, url, relevance_score, topics, published_at
   FROM items
   WHERE relevance_score IS NOT NULL AND embedding IS NOT NULL
   ORDER BY embedding <=> query_vector
   LIMIT 10
   ```
   The `<=>` operator computes cosine distance (1 - cosine similarity). The `ivfflat` index with `vector_cosine_ops` makes this an approximate nearest-neighbor search, trading a small amount of accuracy for significant speed gains.

3. **Returns the 10 most semantically similar items**, ranked by distance. Results include source badges, relevance scores, and topic tags.

This is not keyword matching — it understands meaning. A search for "computer vision models" surfaces items about "image recognition architectures" even if those exact words don't appear. It searches the full database regardless of publication date, providing a complete view of the topic across all ingested history.

### Signal-Item Linking

The same mechanism powers the **signal detail view**: clicking a trend signal computes an embedding from `signal.topic + " " + signal.description`, then finds the most semantically related items. Users can toggle between this "semantic" mode and an "evidence" mode that shows only the specific items the signal detector originally cited via their database IDs (`WHERE id = ANY(evidence_ids)`).

---

## 6. How the Tech Stack Fits Together

### Component Architecture

```
Browser (Dashboard — static HTML + vanilla JS)
    │
    ▼
nginx (:80) ─── serves dashboard + proxies API paths to :8000
    │
    ▼
FastAPI (:8000) ─── REST API, 16 endpoints, CORS enabled
    │
    ├── Ingestion modules ─── arXiv API, feedparser, GitHub API, Semantic Scholar API
    │
    ├── sentence-transformers ─── all-MiniLM-L6-v2, local CPU, 384-dim embeddings
    │
    ├── LangGraph StateGraph ─── writer-critic loop orchestration
    │       ├── Claude Haiku 4.5 ──── filter + signal detection (Anthropic API)
    │       ├── Claude Sonnet 4.5 ─── report synthesis (Anthropic API)
    │       └── Llama 3.3 70B ─────── critic review (Groq API, Gemini fallback)
    │
    └── PostgreSQL 17 + pgvector ─── items, reports, signals, vector embeddings
```

**FastAPI** is the central orchestrator. It exposes endpoints for each pipeline stage individually (`/ingest/{source}`, `/filter`, `/signals/detect`, `/reports/generate`) as well as composite pipelines (`/pipeline/daily` chains ingest → filter → signals; `/pipeline/weekly` adds report generation). The framework was chosen for its automatic OpenAPI documentation, Pydantic request/response validation, async support, and `@traceable` decorator integration with LangSmith. CORS middleware is configured to allow requests from any origin, enabling the static dashboard to call the API from `file://` protocol during local development.

**PostgreSQL with pgvector** stores three tables defined in `init-db.sql`. The `items` table holds all ingested content with a `vector(384)` column for embeddings, float columns for relevance and novelty scores, and a text array for topic tags. The `reports` table stores generated reports with both markdown and rendered HTML, quality scores, critic feedback as JSONB, and revision count. The `signals` table tracks detected trends with an `active` boolean flag, strength scores, and an integer array of evidence item IDs. All tables use auto-incrementing primary keys and timestamp defaults.

**Docker Compose** defines the infrastructure. In development, `docker compose up -d` starts only PostgreSQL (the API runs locally via `uv run uvicorn`). In production, `docker compose --profile production up -d --build` additionally starts the API as a containerized service. The `production` profile pattern keeps the compose file unified while allowing different deployment modes. The API container is built from a `python:3.12-slim` base image, uses `uv` for fast dependency installation, and exposes port 8000.

**LangGraph** manages the writer-critic loop as a compiled `StateGraph`. Rather than implementing retry logic with while loops and if-statements, the pipeline is a formal graph with three nodes (synthesize, critique, publish) and conditional edges (approve, revise, or force-publish). The state is a typed dictionary that flows through the graph, accumulating draft content, critic feedback, and quality scores. LangGraph handles the execution loop, state management, and branching logic. The compiled graph is observable through **LangSmith**, which logs every node execution, LLM call, input/output, latency, and token usage.

**nginx** runs on the EC2 production instance as a reverse proxy. It serves the static HTML dashboard from `/home/ubuntu/app/dashboard/` on port 80 and proxies all API paths (`/health`, `/ingest`, `/filter`, `/signals`, `/reports`, `/items`, `/pipeline`) to the FastAPI container on port 8000. This allows the dashboard to auto-detect its API URL: when loaded from `localhost` or `file://`, it uses `http://localhost:8000` directly; when loaded from any other host, it uses `window.location.origin`, which nginx routes to the API.

**AWS Lambda + EventBridge** handle production scheduling. Three Lambda functions, each triggered by an EventBridge cron rule, replace the need for an always-on workflow engine. The daily function (06:00 UTC) calls `/pipeline/daily` to ingest, filter, and detect signals. The weekly function (Friday 08:00 UTC) calls `/pipeline/weekly` and sends the resulting report via Amazon SES email. The monthly function (1st of month 08:00 UTC) does the same for monthly reports. Each Lambda uses only `boto3` (pre-installed in Lambda) and `urllib` (stdlib) — no additional dependencies.

**Pydantic Settings** (`agent_service/config.py`) centralizes configuration. All API keys, database credentials, and LangSmith settings are defined as a `BaseSettings` class that reads from environment variables and `.env` files. Sensitive values are marked with `sensitive=True` in the Terraform variable definitions. A `database_url` property constructs the PostgreSQL connection string from individual components.

---

## 7. Challenges Encountered

**LLM output parsing.** The most persistent technical challenge was parsing structured JSON from LLM responses. Models frequently wrap JSON in markdown code blocks (` ```json ... ``` `), add trailing commas before closing brackets, include conversational preamble before the JSON array, or produce subtly malformed syntax. We built a multi-layered parser: first attempt extraction from markdown code blocks via regex, then search for a raw JSON array pattern, then fix common syntax issues (trailing commas via `re.sub(r",\s*([}\]])", r"\1", raw)`), and as a final fallback, extract individual JSON objects separately using `re.findall(r'\{[^{}]+\}', raw)` and parse each one independently. This fallback saved the signal detection feature, which frequently received malformed arrays from Haiku.

**Cross-model critic calibration.** The Groq Llama critic was initially either too harsh (rejecting good reports with scores of 4–5) or too lenient (approving hallucinatory reports with 8+) depending on prompt phrasing. Two changes fixed this. First, requiring the critic to verify at least 3 specific factual claims against the source items — this anchored the grounding score to observable facts rather than subjective impression. Second, requiring feedback to quote exact sentences and provide concrete rewrites — this forced the model to engage with the text rather than producing generic assessments.

**Hallucination in reports.** Early versions of the synthesis prompt produced reports that mixed real source items with plausible-sounding but fabricated claims. The "What to Watch" section was especially problematic: the model would invent upcoming events and expected announcements from its training data. The anti-hallucination guardrail — "CRITICAL: Only reference developments from the source items provided below. Do not introduce facts, companies, metrics, funding amounts, or benchmark scores from your own knowledge." — combined with the grounding dimension in the critic, reduced this substantially. It remains the area requiring the most vigilance.

**Rate limiting across multiple APIs.** The system calls Anthropic (filter + signals + synthesis), Groq (critic), and optionally Google (critic fallback) APIs, each with different rate limits. We implemented per-source delays (1.5s between filter calls), exponential backoff on 429 errors (5s → 10s → 20s), and automatic model fallback chains (Groq → Gemini → default scores). The Semantic Scholar API was particularly aggressive with rate limiting from EC2 IP addresses, often returning 429 on all queries; this is handled gracefully by the try/except in each source fetcher, which logs the error and returns an empty list.
