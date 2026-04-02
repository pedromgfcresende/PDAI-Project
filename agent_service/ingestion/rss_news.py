import re
from datetime import datetime, timezone

import feedparser
from dotenv import load_dotenv

from agent_service.ingestion.normalize import normalize_item
from agent_service.models import IngestedItem

load_dotenv()

RSS_FEEDS: dict[str, str] = {
    # AI news outlets
    "techcrunch_ai": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "venturebeat_ai": "https://venturebeat.com/category/ai/feed/",
    "ars_ai": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "mit_tech_review": "https://www.technologyreview.com/feed/",
    # Company blogs
    "google_ai": "https://blog.google/technology/ai/rss/",
    "openai_blog": "https://openai.com/blog/rss.xml",
    "anthropic_blog": "https://www.anthropic.com/rss.xml",
    "meta_ai": "https://ai.meta.com/blog/rss/",
    # HuggingFace
    "huggingface_blog": "https://huggingface.co/blog/feed.xml",
}


def _parse_date(entry: dict) -> datetime | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        from time import mktime
        return datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
    return None


def fetch_rss_news(
    feeds: dict[str, str] | None = None,
    max_per_feed: int = 20,
) -> list[IngestedItem]:
    """Fetch articles from RSS feeds."""
    feeds = feeds or RSS_FEEDS
    items: list[IngestedItem] = []

    for feed_name, feed_url in feeds.items():
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:max_per_feed]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                if not title:
                    continue

                summary = entry.get("summary", "") or entry.get("description", "")
                # Strip HTML tags from summary
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 500:
                    summary = summary[:500] + "..."

                item = normalize_item(
                    source="rss",
                    unique_key=link or f"{feed_name}:{title}",
                    title=title,
                    summary=summary,
                    url=link,
                    authors=[entry.get("author", feed_name)],
                    published_at=_parse_date(entry),
                    raw_metadata={"feed_name": feed_name, "feed_url": feed_url},
                )
                items.append(item)
        except Exception as e:
            print(f"[rss] Error fetching {feed_name}: {e}")

    return items
