import arxiv

from agent_service.ingestion.normalize import normalize_item
from agent_service.models import IngestedItem

CATEGORIES = ["cs.AI", "cs.LG", "cs.CL"]
MAX_RESULTS_PER_CATEGORY = 15


def fetch_arxiv_papers(
    categories: list[str] | None = None,
    max_results: int = MAX_RESULTS_PER_CATEGORY,
) -> list[IngestedItem]:
    """Fetch recent AI/ML papers from arXiv."""
    categories = categories or CATEGORIES
    items: list[IngestedItem] = []

    for category in categories:
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=f"cat:{category}",
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )
            for result in client.results(search):
                item = normalize_item(
                    source="arxiv",
                    unique_key=result.entry_id,
                    title=result.title,
                    summary=result.summary,
                    url=result.entry_id,
                    authors=[a.name for a in result.authors],
                    published_at=result.published,
                    raw_metadata={
                        "categories": [c for c in result.categories],
                        "primary_category": result.primary_category,
                        "pdf_url": result.pdf_url,
                    },
                )
                items.append(item)
        except Exception as e:
            print(f"[arxiv] Error fetching {category}: {e}")

    return items
