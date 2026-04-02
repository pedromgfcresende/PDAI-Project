from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────

class SourceType(str, Enum):
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    RSS = "rss"
    GITHUB = "github"
    HUGGINGFACE = "huggingface"


class ReportType(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SignalType(str, Enum):
    EMERGENCE = "emergence"
    ACCELERATION = "acceleration"
    DISRUPTION = "disruption"


# ─── Ingestion ───────────────────────────────────────────

class IngestedItem(BaseModel):
    """Normalized item coming out of any ingestion source."""
    source: SourceType
    source_id: str
    title: str
    summary: str = ""
    url: str = ""
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    raw_metadata: dict = Field(default_factory=dict)


# ─── Filter Agent ────────────────────────────────────────

class FilterResult(BaseModel):
    """Output of the Filter Agent for a single item."""
    source_id: str
    relevance_score: float = Field(ge=0, le=1)
    novelty_score: float = Field(ge=0, le=1)
    topics: list[str] = Field(default_factory=list)
    reasoning: str = ""


# ─── Synthesis Agent ─────────────────────────────────────

class SynthesisRequest(BaseModel):
    """Request to the Synthesis Agent."""
    report_type: ReportType
    period_start: date
    period_end: date
    items: list[dict]  # Simplified item dicts for the LLM context
    signals: list[dict] = Field(default_factory=list)
    feedback: str = ""  # Critic feedback for revision rounds


class SynthesisResult(BaseModel):
    """Output of the Synthesis Agent."""
    title: str
    content_md: str
    item_ids: list[int] = Field(default_factory=list)


# ─── Critic Agent ────────────────────────────────────────

class CriticScores(BaseModel):
    """Individual dimension scores from the Critic Agent."""
    grounding: float = Field(ge=0, le=10, description="Are claims supported by the source items?")
    coherence: float = Field(ge=0, le=10, description="Is the report logically structured?")
    completeness: float = Field(ge=0, le=10, description="Does it cover the key developments?")
    actionability: float = Field(ge=0, le=10, description="Can a reader act on the insights?")


class CriticResult(BaseModel):
    """Output of the Critic Agent."""
    scores: CriticScores
    overall_score: float = Field(ge=0, le=10)
    feedback: str
    approved: bool


# ─── Signals ─────────────────────────────────────────────

class TrendSignal(BaseModel):
    """A detected trend signal."""
    signal_type: SignalType
    topic: str
    description: str
    strength: float = Field(ge=0, le=1)
    evidence_ids: list[int] = Field(default_factory=list)


# ─── API Responses ───────────────────────────────────────

class IngestResponse(BaseModel):
    """Response from the ingestion endpoint."""
    source: str
    items_ingested: int
    items_filtered: int


class ReportResponse(BaseModel):
    """Response containing a generated report."""
    id: int
    report_type: ReportType
    title: str
    content_md: str
    quality_score: float | None
    revision_count: int
    published: bool


class HealthResponse(BaseModel):
    status: str = "ok"
    db_connected: bool
    items_count: int = 0
    reports_count: int = 0
