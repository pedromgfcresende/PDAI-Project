# Prompt: Semantic Search + Signal Detail View

## Context

This is the **AI Trends Explorer** project — a multi-agent system (FastAPI + LangGraph) that ingests AI news/papers, scores them with Claude Haiku, detects trend signals, and generates reports via a writer-critic pipeline (Sonnet + Groq Llama). The stack runs locally with Docker Compose (Postgres + pgvector) and a FastAPI agent service.

**Key fact:** Every ingested item already has a 384-dimensional embedding stored in the `items` table (`vector(384)` column, computed via `all-MiniLM-L6-v2` in `agent_service/ingestion/normalize.py`). An `ivfflat` cosine similarity index already exists. However, **no feature currently queries these embeddings** — they are stored but unused. This task fixes that.

Signals already store `evidence_ids` (list of item IDs that support the signal).

## What to Build

### 1. Semantic Search (pgvector)

**DB layer** (`agent_service/db.py`) — Add a function:
```python
def search_items_by_embedding(query_embedding: list[float], limit: int = 10) -> list[dict]:
```
- Query: `SELECT id, source, title, summary, url, relevance_score, novelty_score, topics, published_at FROM items WHERE relevance_score IS NOT NULL ORDER BY embedding <=> %s LIMIT %s`
- Returns items sorted by cosine similarity to the query embedding.

**API endpoint** (`agent_service/main.py`) — Add:
```
GET /items/search?q=<query_text>&limit=10
```
- Takes a natural language query string.
- Computes its embedding using the existing `compute_embedding()` function from `agent_service/ingestion/normalize.py`.
- Calls `search_items_by_embedding()` and returns the results.
- Response should include each item's `id`, `source`, `title`, `summary`, `url`, `relevance_score`, `topics`, and `published_at`.

### 2. Signal Detail — Get Related Items

**DB layer** (`agent_service/db.py`) — Add a function:
```python
def get_items_by_ids(item_ids: list[int]) -> list[dict]:
```
- Query: `SELECT id, source, title, summary, url, relevance_score, novelty_score, topics, published_at FROM items WHERE id = ANY(%s) ORDER BY relevance_score DESC`

**Also add** a semantic search variant for signals:
```python
def get_signal_by_id(signal_id: int) -> dict | None:
```
- Simple select from `signals` table by ID.

**API endpoint** (`agent_service/main.py`) — Add:
```
GET /signals/{signal_id}/items?mode=semantic&limit=10
```
- Two modes:
  - `mode=evidence` (default): Returns items matching the signal's `evidence_ids` using `get_items_by_ids()`.
  - `mode=semantic`: Computes an embedding from the signal's `topic + " " + description`, then runs `search_items_by_embedding()` to find semantically related items.
- Response: list of items with `id`, `source`, `title`, `summary`, `url`, `relevance_score`, `topics`.

### 3. Dashboard UI Changes (`dashboard/index.html`)

**Search bar** — Add a search input to the dashboard page (above or alongside the actions bar):
- Text input with a search icon and placeholder "Search items semantically..."
- On submit (Enter or click), call `GET /items/search?q=<query>`.
- Display results in a dropdown or panel below the search bar showing: title, source badge, relevance score, and a truncated summary.
- Clicking a result could open the item's URL in a new tab.
- Style consistently with the existing dark glassmorphism theme.

**Signal cards become clickable** — In the signals list (right column of the dashboard):
- Make each signal card clickable.
- On click, call `GET /signals/{id}/items?mode=semantic&limit=8`.
- Show the related items in an expandable section below the signal card, or in a modal similar to the report viewer.
- Each item should show: source icon/badge, title (linked to URL), truncated summary, relevance score pill.
- Include a small toggle to switch between `evidence` and `semantic` mode so the user can compare.

## Files to Modify

| File | Changes |
|------|---------|
| `agent_service/db.py` | Add `search_items_by_embedding()`, `get_items_by_ids()`, `get_signal_by_id()` |
| `agent_service/main.py` | Add `GET /items/search` and `GET /signals/{id}/items` endpoints |
| `dashboard/index.html` | Add search bar UI + signal click-to-expand functionality |

## Important Notes

- Use the existing `compute_embedding()` from `agent_service/ingestion/normalize.py` — don't create a new one.
- The pgvector operator for cosine distance is `<=>`. The index (`ivfflat ... vector_cosine_ops`) already supports this.
- Keep the existing code style: `get_connection()` pattern, `psycopg2.extras.RealDictCursor`, type hints.
- The dashboard is pure static HTML + vanilla JS — no frameworks. Match the existing glassmorphism dark theme.
- CORS middleware is already configured on the FastAPI app.
- Preserve all existing functionality — these are additive changes only.
