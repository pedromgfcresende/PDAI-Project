# AI Trends Explorer — Final Project Report

**Prototyping Products with AI (PDAI) | ESADE Business School**
**Group A | MiBA Second Term, 2025**

---

## 1. The Problem

Consulting firms, investment teams, and technology strategists face the same problem: the AI landscape moves faster than any individual can track. Every week, hundreds of research papers are published on arXiv, companies announce new models and products, open-source projects gain traction overnight, and funding rounds reshape competitive dynamics. The volume of information is not the issue — the issue is that most of it is noise.

A strategist who misses a single paradigm-shifting paper or a quietly announced product launch can give outdated advice. Yet reading everything is impossible. Current solutions — newsletters, analyst reports, RSS readers — either arrive too late, cover too little, or require significant manual effort to curate.

We asked: *what if an AI system could do the ingestion, filtering, and synthesis automatically — and deliver a concise, quality-reviewed intelligence report every week?*

---

## 2. Our Approach

We built **AI Trends Explorer**, a multi-agent system that continuously monitors public AI data sources, filters out noise, detects emerging trend signals, and produces weekly and monthly intelligence reports. The key insight behind the design is that no single LLM call can do all of this well. Instead, we decompose the problem into specialized agents, each optimized for a specific task, connected through a stateful pipeline with a quality feedback loop.

### Design Principles

- **Breadth at ingestion, selectivity at filtering.** We cast a wide net across four data sources (up to ~265 items per run), then use an LLM-powered filter to surface only what matters.
- **Different models for different jobs.** Fast, cheap models (Claude Haiku) handle high-volume classification. A stronger model (Claude Sonnet) writes the reports. A completely different model family (Groq Llama) reviews them — because same-model review tends to approve its own blind spots.
- **Writer-critic loop for quality assurance.** Reports are never published after a single pass. A critic agent scores each draft on four dimensions and provides specific, actionable feedback. The writer revises up to twice before publication.
- **Embeddings for semantic understanding.** Every ingested item is embedded using a local model (all-MiniLM-L6-v2), enabling semantic search and signal-to-item linking through pgvector.

---

## 3. Data Ingestion: How We Retrieve Information

The system ingests data from four public sources. The strategy is to **retrieve the most recent items first**, then filter for importance afterwards. No relevance judgment is made during ingestion — that is the Filter Agent's job.

### Sources

| Source | What it fetches | Items per run | Sorting |
|--------|----------------|---------------|---------|
| **arXiv** | AI/ML research papers from cs.AI, cs.LG, cs.CL | ~45 (15 per category) | By submission date (newest first) |
| **RSS Feeds** | Articles from 10 feeds: TechCrunch, VentureBeat, MIT Tech Review, Google AI, OpenAI, Anthropic, Meta AI, HuggingFace, Crunchbase, SecurityWeek | ~150 (15 per feed) | By publication date |
| **GitHub Trending** | AI repositories across 6 topics (machine-learning, deep-learning, LLMs, etc.) | ~30 (5 per topic) | By stars, only repos pushed in last 7 days with >10 stars |
| **Semantic Scholar** | Papers matching 4 queries (artificial intelligence, LLMs, machine learning, neural networks) | ~40 (10 per query) | By publication date |

### Processing Pipeline

Every item, regardless of source, passes through a normalization step that:

1. **Generates a deterministic ID** (`source:SHA256(unique_key)`) for deduplication — the same paper ingested twice is stored only once.
2. **Normalizes timestamps** to UTC so date-range queries work correctly across sources.
3. **Computes a 384-dimensional embedding** of the item's `title + summary` using the `all-MiniLM-L6-v2` sentence-transformer model (runs locally on CPU, no API cost).
4. **Stores everything** in PostgreSQL with the pgvector extension, including the embedding vector.

The key design decision is that ingestion is deliberately unfiltered. We want the database to have a complete picture of what was published, and then apply intelligent filtering as a separate step. This separation means we can re-filter with different thresholds without re-ingesting.

---

## 4. The Multi-Agent Pipeline

The pipeline has four stages, each handled by a specialized agent. The stages run sequentially, with the output of each feeding into the next.

### Stage 1: Filter Agent (Claude Haiku 4.5)

Every unscored item is evaluated by Claude Haiku on two dimensions:

- **Relevance (0.0–1.0):** How important is this to AI/ML trends, with emphasis on business and strategic significance? The prompt provides three calibration examples (a major model release at 0.92, a survey paper at 0.15, an incremental efficiency gain at 0.55) to anchor the model's scoring.
- **Novelty (0.0–1.0):** How surprising or new is this? Rehashed concepts score low; genuinely new approaches score high.

The agent also assigns 1–3 topic tags from a fixed taxonomy (LLMs, agents, safety, efficiency, funding, etc.). Items scoring below 0.5 relevance are excluded from report generation. The prompt includes the current date so the model can judge timeliness.

The filter processes items sequentially with a 1.5-second delay between calls to stay under rate limits (~40 requests/minute). Exponential backoff handles transient 429 errors.

### Stage 2: Signal Detection (Claude Haiku 4.5)

Once items are scored and tagged, the signal detector analyzes the full batch to identify cross-cutting patterns. It produces exactly 5 signals, each classified as:

- **Emergence** — A new topic appearing for the first time across multiple sources.
- **Acceleration** — An existing trend gaining significantly more attention.
- **Disruption** — Something challenging or replacing an established approach.

Each signal includes a strength score (0.0–1.0) and links back to the specific items that support it. The prompt explicitly requires signals to be distinct and non-overlapping — the model must merge related patterns rather than listing them separately. Old signals are deactivated before each new detection run to prevent accumulation.

### Stage 3: Synthesis Agent (Claude Sonnet 4.5)

The synthesis agent receives all items with relevance ≥ 0.5 for the report period (last 7 days for weekly, 30 days for monthly) plus the active trend signals. It generates a structured Markdown report with:

- **TL;DR** — 3–5 bullet points with the week's must-know developments.
- **Key Developments** — Prose analysis of the most significant items, explaining *why* each matters, not just *what* happened.
- **Industry Moves** — Acquisitions, funding rounds, competitive dynamics.
- **Trend Signals** — Narrative connecting patterns across the items.
- **What to Watch** — Upcoming events and expected announcements.

The prompt enforces a critical constraint: **the agent may only reference information from the provided source items.** It cannot introduce facts, metrics, or company names from its training data. Every claim must be traceable to a specific item, cited inline as `[Title](URL)`. This anti-hallucination guardrail is the single most important prompt engineering decision in the system — without it, the model fills gaps with plausible-sounding but unverifiable claims.

### Stage 4: Critic Agent (Groq Llama 3.3 70B)

The critic evaluates the draft on four dimensions, each scored 0–10:

| Dimension | What it evaluates |
|-----------|-------------------|
| **Grounding** | Are claims supported by source items? The critic must identify ≥3 specific factual claims and verify them against the source list. Untraced claims are flagged as potential hallucinations. |
| **Coherence** | Does the report flow logically? Are sections well-structured with clear transitions? |
| **Completeness** | Does it cover the key developments? Are major items from the source list missing? |
| **Actionability** | Can a reader act on the insights? Are recommendations specific enough to be useful? |

The overall score is the average of all four dimensions. Reports scoring **≥ 7.0** are approved and published. Reports scoring below 7.0 receive specific, actionable feedback — the critic must quote an exact sentence from the report and suggest a concrete rewrite.

We intentionally use a **different model family** for the critic (Llama via Groq) than for the writer (Claude via Anthropic). Same-model review tends to approve its own mistakes because the models share similar blind spots. Cross-model review catches errors that within-family review misses. If Groq is unavailable (rate limit), the system falls back to Gemini 2.0 Flash as an alternative reviewer.

### The Writer-Critic Loop (LangGraph)

The entire synthesis-critique cycle is orchestrated as a **LangGraph StateGraph** — a directed graph where nodes are functions and edges define the control flow:

```
synthesize → critique → should_retry?
                            ├── approved (score ≥ 7) → publish → END
                            ├── retries < 2          → synthesize (with feedback)
                            └── retries ≥ 2          → force_publish → END
```

The state object carries everything: input items, signals, the current draft, critic feedback, quality scores, and retry count. On revision, the critic's feedback is appended to the synthesis prompt so the writer knows exactly what to fix. Maximum 2 revision attempts (3 total passes), after which the report is published regardless with whatever quality score it achieved.

---

## 5. Semantic Search: Using RAG with pgvector

Every ingested item has a 384-dimensional embedding stored alongside it in PostgreSQL. The `all-MiniLM-L6-v2` model (from the sentence-transformers library) converts text into dense vectors that capture semantic meaning — similar concepts have similar vectors regardless of exact wording.

The **search bar** on the dashboard implements a form of retrieval-augmented generation (RAG) at the retrieval step: when a user types a query like "multimodal agents," the system:

1. Computes the query's embedding using the same model.
2. Runs a SQL query using pgvector's `<=>` cosine distance operator: `ORDER BY embedding <=> query_vector LIMIT 10`.
3. Returns the 10 most semantically similar items, ranked by relevance.

This is not keyword matching — it understands meaning. A search for "computer vision models" will surface items about "image recognition architectures" even if those exact words don't appear.

The same mechanism powers the **signal detail view**: clicking a trend signal computes an embedding from its topic and description, then finds the most semantically related items in the database. Users can toggle between this semantic mode and an evidence mode that shows only the specific items the signal detector originally cited.

The pgvector extension adds a specialized `ivfflat` index (`vector_cosine_ops`) to the embedding column, making similarity searches fast even with thousands of items.

---

## 6. How the Tech Stack Fits Together

The system runs as a set of Docker containers orchestrated by Docker Compose, with a FastAPI backend connecting all components.

### Architecture

```
Browser (Dashboard)
    │
    ▼
nginx (:80) ─── serves static HTML + proxies API paths
    │
    ▼
FastAPI (:8000) ─── REST API with 16 endpoints
    │
    ├── Ingestion modules ─── arXiv, RSS, GitHub, Semantic Scholar APIs
    │
    ├── LangGraph pipeline ─── orchestrates the writer-critic loop
    │       ├── Claude Haiku (filter + signals) ─── Anthropic API
    │       ├── Claude Sonnet (synthesis) ─── Anthropic API
    │       └── Groq Llama / Gemini Flash (critic) ─── Groq / Google APIs
    │
    ├── sentence-transformers ─── local embedding computation (CPU)
    │
    └── PostgreSQL + pgvector ─── items, reports, signals, embeddings
```

**FastAPI** serves as the central orchestrator. It exposes endpoints for each pipeline stage (ingest, filter, detect signals, generate report) as well as composite endpoints (`/pipeline/daily`, `/pipeline/weekly`) that chain them together. The framework was chosen for its async support, automatic API documentation, and Pydantic integration for request/response validation.

**PostgreSQL with pgvector** stores three tables: `items` (ingested content + embeddings), `reports` (generated reports with quality scores), and `signals` (detected trends). The pgvector extension enables vector similarity search directly in SQL, avoiding the need for a separate vector database.

**Docker Compose** runs the database locally for development. In production, a `production` profile adds the API as a containerized service alongside Postgres. The Dockerfile uses `uv` (a fast Python package manager) for dependency installation.

**LangGraph** manages the stateful writer-critic loop. Rather than chaining LLM calls with ad-hoc Python code, the pipeline is defined as a graph with typed state, conditional edges, and automatic retry logic. This makes the flow explicit, testable, and observable through LangSmith.

**LangSmith** provides observability — every LLM call, its inputs, outputs, latency, and token usage are logged. This was essential for debugging prompt issues and understanding why the critic rejected specific drafts.

**nginx** runs on the EC2 instance, serving the static HTML dashboard on port 80 and proxying API paths (`/health`, `/ingest`, `/reports`, etc.) to the FastAPI container on port 8000. This allows the dashboard to use relative URLs without knowing the server's IP.

For production scheduling, **AWS Lambda** functions triggered by **EventBridge** cron rules replace the need for an always-on workflow engine. Each Lambda simply makes an HTTP request to the API and (for weekly/monthly reports) sends the result via **Amazon SES** email.

---

## 7. Challenges Encountered

**LLM output parsing.** The most persistent technical challenge was parsing structured JSON from LLM responses. Models frequently wrap JSON in markdown code blocks, add trailing commas, or include preamble text before the JSON array. We built a multi-layered parser: first try extracting from code blocks, then search for raw JSON arrays, then fix common syntax issues (trailing commas), and as a final fallback, extract individual JSON objects separately.

**Cross-model critic calibration.** The Groq Llama critic was initially either too harsh or too lenient depending on the prompt phrasing. Requiring the critic to verify specific claims against source items (rather than giving a general impression) significantly improved consistency. The key insight was making the feedback format concrete: "quote the exact sentence, suggest a rewrite" instead of "could be more actionable."

**Hallucination in reports.** Early versions of the synthesis prompt produced reports that mixed real source items with plausible-sounding but fabricated claims — especially in the "What to Watch" section. The anti-hallucination guardrail ("only reference provided source items") and the grounding dimension in the critic together reduced this substantially, though it remains the area requiring most vigilance.

**Docker Compose and deployment.** Getting the API container to work alongside Postgres in Docker Compose required careful handling of service dependencies, health checks, and network configuration. We solved this with Docker Compose profiles — the `production` profile includes the API container while local development only runs Postgres.

**Rate limiting across multiple APIs.** The system calls Anthropic (filter + signals + synthesis), Groq (critic), and optionally Google (critic fallback) APIs. Each has different rate limits. We implemented per-source delays, exponential backoff, and automatic fallback chains to handle this gracefully.

**Embedding model memory.** The `all-MiniLM-L6-v2` model requires ~500MB of RAM, which ruled out the smallest EC2 instance types. We use a lazy singleton pattern to load the model once and keep it in memory for the lifetime of the process.
