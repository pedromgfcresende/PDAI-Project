from datetime import date, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from agent_service import db
from agent_service.agents.filter import filter_batch
from agent_service.agents.pipeline import report_pipeline
from agent_service.agents.signals import detect_signals, detect_signals_simple
from agent_service.ingestion.arxiv_source import fetch_arxiv_papers
from agent_service.ingestion.github_trending import fetch_github_trending
from agent_service.ingestion.normalize import compute_embedding
from agent_service.ingestion.rss_news import fetch_rss_news
from agent_service.ingestion.semantic_scholar import fetch_semantic_scholar
from agent_service.models import HealthResponse, IngestResponse, ReportResponse, ReportType

load_dotenv()

app = FastAPI(
    title="AI Trends Explorer",
    description="Multi-agent system for AI research and news intelligence",
    version="0.1.0",
)


# ─── Health ──────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    try:
        items_count = db.get_item_count()
        reports_count = db.get_report_count()
        return HealthResponse(status="ok", db_connected=True, items_count=items_count, reports_count=reports_count)
    except Exception:
        return HealthResponse(status="degraded", db_connected=False)


# ─── Ingestion ───────────────────────────────────────────

@app.post("/ingest/{source}", response_model=IngestResponse)
def ingest(source: str):
    """Ingest items from a specific source, compute embeddings, and store in DB."""
    fetchers = {
        "arxiv": fetch_arxiv_papers,
        "semantic_scholar": fetch_semantic_scholar,
        "rss": fetch_rss_news,
        "github": fetch_github_trending,
    }
    if source not in fetchers:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}. Options: {list(fetchers.keys())}")

    items = fetchers[source]()
    ingested = 0

    for item in items:
        text = f"{item.title} {item.summary}"
        embedding = compute_embedding(text)
        result = db.insert_item(
            source=item.source.value,
            source_id=item.source_id,
            title=item.title,
            summary=item.summary,
            url=item.url,
            authors=item.authors,
            published_at=item.published_at,
            embedding=embedding,
            raw_metadata=item.raw_metadata,
        )
        if result is not None:
            ingested += 1

    return IngestResponse(source=source, items_ingested=ingested, items_filtered=0)


@app.post("/ingest", response_model=list[IngestResponse])
def ingest_all():
    """Ingest from all sources."""
    results = []
    for source in ["arxiv", "semantic_scholar", "rss", "github"]:
        result = ingest(source)
        results.append(result)
    return results


# ─── Filtering ───────────────────────────────────────────

@app.post("/filter")
def filter_unscored(limit: int = 100):
    """Score unscored items using the Filter Agent (Haiku)."""
    items = db.get_unscored_items(limit=limit)
    if not items:
        return {"message": "No unscored items found", "scored": 0}

    results = filter_batch(items)

    for result in results:
        db.update_item_scores(
            source_id=result.source_id,
            relevance_score=result.relevance_score,
            novelty_score=result.novelty_score,
            topics=result.topics,
        )

    return {
        "scored": len(results),
        "avg_relevance": sum(r.relevance_score for r in results) / len(results),
        "avg_novelty": sum(r.novelty_score for r in results) / len(results),
    }


# ─── Signals ─────────────────────────────────────────────

@app.post("/signals/detect")
def detect_trend_signals(days: int = 7, use_llm: bool = True):
    """Detect trend signals from recent scored items."""
    end = date.today()
    start = end - timedelta(days=days)
    items = db.get_items_for_period(start, end, min_relevance=0.4)

    if use_llm:
        signals = detect_signals(items)
    else:
        signals = detect_signals_simple(items)

    # Store signals
    for signal in signals:
        db.insert_signal(
            signal_type=signal.signal_type.value,
            topic=signal.topic,
            description=signal.description,
            strength=signal.strength,
            evidence_ids=signal.evidence_ids,
        )

    return {"signals_detected": len(signals), "signals": [s.model_dump() for s in signals]}


@app.get("/signals")
def get_signals():
    """Get all active trend signals."""
    return db.get_active_signals()


# ─── Report Generation ───────────────────────────────────

@app.post("/reports/generate", response_model=ReportResponse)
def generate_report(report_type: str = "weekly"):
    """Run the full writer-critic pipeline to generate a report."""
    if report_type not in ("weekly", "monthly"):
        raise HTTPException(status_code=400, detail="report_type must be 'weekly' or 'monthly'")

    end = date.today()
    start = end - timedelta(days=7 if report_type == "weekly" else 30)
    items = db.get_items_for_period(start, end, min_relevance=0.5)
    signals = db.get_active_signals()

    if not items:
        raise HTTPException(status_code=404, detail="No scored items found for this period. Run /ingest and /filter first.")

    # Run the LangGraph writer-critic pipeline
    result = report_pipeline.invoke({
        "report_type": report_type,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "items": items,
        "signals": signals,
        "draft_title": "",
        "draft_content": "",
        "item_ids": [],
        "feedback": "",
        "retry_count": 0,
        "final_title": "",
        "final_content": "",
        "quality_score": 0.0,
        "critic_feedback": {},
        "approved": False,
    })

    # Store the report
    report_id = db.insert_report(
        report_type=report_type,
        title=result["final_title"],
        content_md=result["final_content"],
        period_start=start,
        period_end=end,
        quality_score=result.get("quality_score"),
        critic_feedback=result.get("critic_feedback"),
        revision_count=result.get("retry_count", 0),
        item_ids=result.get("item_ids", []),
    )

    return ReportResponse(
        id=report_id,
        report_type=ReportType(report_type),
        title=result["final_title"],
        content_md=result["final_content"],
        quality_score=result.get("quality_score"),
        revision_count=result.get("retry_count", 0),
        published=False,
    )


@app.get("/reports", response_model=list[ReportResponse])
def list_reports(report_type: str = "weekly", limit: int = 10):
    """List recent reports."""
    rows = db.get_latest_reports(report_type, limit)
    return [
        ReportResponse(
            id=r["id"],
            report_type=ReportType(r["report_type"]),
            title=r["title"],
            content_md=r["content_md"],
            quality_score=r.get("quality_score"),
            revision_count=r.get("revision_count", 0),
            published=r.get("published", False),
        )
        for r in rows
    ]


# ─── Full Pipeline ───────────────────────────────────────

@app.post("/pipeline/daily")
def run_daily_pipeline():
    """Full daily pipeline: ingest all → filter → detect signals."""
    ingest_results = ingest_all()
    filter_result = filter_unscored(limit=200)
    signal_result = detect_trend_signals(days=7, use_llm=True)
    return {
        "ingestion": [r.model_dump() for r in ingest_results],
        "filtering": filter_result,
        "signals": signal_result,
    }


@app.post("/pipeline/weekly")
def run_weekly_pipeline():
    """Full weekly pipeline: daily pipeline + generate weekly report."""
    daily = run_daily_pipeline()
    report = generate_report(report_type="weekly")
    return {"daily_pipeline": daily, "report": report.model_dump()}


@app.post("/pipeline/monthly")
def run_monthly_pipeline():
    """Full monthly pipeline: daily pipeline + generate monthly report."""
    daily = run_daily_pipeline()
    report = generate_report(report_type="monthly")
    return {"daily_pipeline": daily, "report": report.model_dump()}
