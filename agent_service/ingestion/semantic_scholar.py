from datetime import datetime

import httpx

from agent_service.ingestion.normalize import normalize_item
from agent_service.models import IngestedItem

BASE_URL = "https://api.semanticscholar.org/graph/v1"
SEARCH_QUERIES = [
    "artificial intelligence",
    "large language models",
    "machine learning",
    "neural networks",
]
MAX_RESULTS = 10


def fetch_semantic_scholar(
    queries: list[str] | None = None,
    max_results: int = MAX_RESULTS,
) -> list[IngestedItem]:
    """Fetch recent papers from Semantic Scholar."""
    queries = queries or SEARCH_QUERIES
    items: list[IngestedItem] = []
    seen_ids: set[str] = set()

    for query in queries:
        try:
            resp = httpx.get(
                f"{BASE_URL}/paper/search",
                params={
                    "query": query,
                    "limit": max_results,
                    "fields": "title,abstract,url,authors,year,citationCount,publicationDate",
                    "sort": "publicationDate:desc",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            for paper in data.get("data", []):
                paper_id = paper.get("paperId", "")
                if not paper_id or paper_id in seen_ids:
                    continue
                seen_ids.add(paper_id)

                pub_date = None
                if paper.get("publicationDate"):
                    try:
                        pub_date = datetime.fromisoformat(paper["publicationDate"])
                    except ValueError:
                        pass

                item = normalize_item(
                    source="semantic_scholar",
                    unique_key=paper_id,
                    title=paper.get("title", ""),
                    summary=paper.get("abstract") or "",
                    url=paper.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}",
                    authors=[a.get("name", "") for a in paper.get("authors", [])],
                    published_at=pub_date,
                    raw_metadata={
                        "citation_count": paper.get("citationCount"),
                        "year": paper.get("year"),
                    },
                )
                items.append(item)
        except Exception as e:
            print(f"[semantic_scholar] Error searching '{query}': {e}")

    return items
