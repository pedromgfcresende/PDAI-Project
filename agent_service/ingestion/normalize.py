import hashlib
from datetime import datetime, timezone

from sentence_transformers import SentenceTransformer

from agent_service.models import IngestedItem

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def compute_embedding(text: str) -> list[float]:
    model = get_embedding_model()
    return model.encode(text).tolist()


def make_source_id(source: str, unique_key: str) -> str:
    """Create a deterministic source_id for dedup."""
    return f"{source}:{hashlib.sha256(unique_key.encode()).hexdigest()[:16]}"


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_item(
    source: str,
    unique_key: str,
    title: str,
    summary: str = "",
    url: str = "",
    authors: list[str] | None = None,
    published_at: datetime | None = None,
    raw_metadata: dict | None = None,
) -> IngestedItem:
    return IngestedItem(
        source=source,
        source_id=make_source_id(source, unique_key),
        title=title,
        summary=summary,
        url=url,
        authors=authors or [],
        published_at=ensure_utc(published_at),
        raw_metadata=raw_metadata or {},
    )
