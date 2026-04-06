from datetime import datetime, timedelta, timezone

import httpx

from agent_service.config import settings
from agent_service.ingestion.normalize import normalize_item
from agent_service.models import IngestedItem

AI_TOPICS = [
    "machine-learning",
    "deep-learning",
    "large-language-models",
    "artificial-intelligence",
    "transformers",
    "generative-ai",
]


def fetch_github_trending(
    topics: list[str] | None = None,
    max_per_topic: int = 5,
) -> list[IngestedItem]:
    """Fetch trending AI repos from GitHub via the search API."""
    topics = topics or AI_TOPICS
    items: list[IngestedItem] = []
    seen_repos: set[str] = set()

    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    # Search for recently created/updated repos with AI topics
    for topic in topics:
        try:
            resp = httpx.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"topic:{topic} pushed:>={_week_ago()} stars:>10",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": max_per_topic,
                },
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            for repo in data.get("items", []):
                full_name = repo["full_name"]
                if full_name in seen_repos:
                    continue
                seen_repos.add(full_name)

                pushed_at = None
                if repo.get("pushed_at"):
                    pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))

                item = normalize_item(
                    source="github",
                    unique_key=full_name,
                    title=f"{full_name}: {repo.get('description', '')}",
                    summary=repo.get("description") or "",
                    url=repo["html_url"],
                    authors=[repo["owner"]["login"]],
                    published_at=pushed_at,
                    raw_metadata={
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                        "language": repo.get("language"),
                        "topics": repo.get("topics", []),
                    },
                )
                items.append(item)
        except Exception as e:
            print(f"[github] Error fetching topic '{topic}': {e}")

    return items


def _week_ago() -> str:
    d = datetime.now(timezone.utc) - timedelta(days=7)
    return d.strftime("%Y-%m-%d")
