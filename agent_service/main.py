from datetime import date, timedelta
from pathlib import Path

import markdown
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langsmith import traceable
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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

TEMPLATES_DIR = Path(__file__).parent / "templates"

load_dotenv()

app = FastAPI(
    title="AI Trends Explorer",
    description="Multi-agent system for AI research and news intelligence",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def render_md_to_html(md_text: str) -> str:
    """Convert Markdown to HTML with common extensions."""
    return markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "codehilite", "toc", "nl2br"],
    )


# ─── Health ──────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        items_count = db.get_item_count()
        scored_count = db.get_scored_item_count()
        reports_count = db.get_report_count()
        signal_count = db.get_signal_count()
        return {
            "status": "ok",
            "db_connected": True,
            "items_count": items_count,
            "scored_count": scored_count,
            "reports_count": reports_count,
            "signal_count": signal_count,
        }
    except Exception:
        return {"status": "degraded", "db_connected": False, "items_count": 0, "scored_count": 0, "reports_count": 0, "signal_count": 0}


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
@traceable(name="filter_unscored")
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
@traceable(name="detect_signals")
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
@traceable(name="generate_report")
def generate_report(
    report_type: str = "weekly",
    period_start: str | None = None,
    period_end: str | None = None,
):
    """Run the full writer-critic pipeline to generate a report."""
    if report_type not in ("weekly", "monthly"):
        raise HTTPException(status_code=400, detail="report_type must be 'weekly' or 'monthly'")

    end = date.fromisoformat(period_end) if period_end else date.today()
    start = date.fromisoformat(period_start) if period_start else end - timedelta(days=7 if report_type == "weekly" else 30)

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

    # Render Markdown → HTML
    content_html = render_md_to_html(result["final_content"])

    # Store the report
    report_id = db.insert_report(
        report_type=report_type,
        title=result["final_title"],
        content_md=result["final_content"],
        content_html=content_html,
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
        content_html=content_html,
        quality_score=result.get("quality_score"),
        revision_count=result.get("retry_count", 0),
        published=False,
        period_start=start,
        period_end=end,
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
            content_html=r.get("content_html"),
            quality_score=r.get("quality_score"),
            revision_count=r.get("revision_count", 0),
            published=r.get("published", False),
            period_start=r.get("period_start"),
            period_end=r.get("period_end"),
            created_at=r.get("created_at"),
        )
        for r in rows
    ]


# ─── Download / Export ────────────────────────────────────

@app.get("/reports/{report_id}/download", response_class=HTMLResponse)
def download_report(report_id: int):
    """Download a report as a self-contained styled HTML file."""
    report = db.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    content_html = report.get("content_html") or render_md_to_html(report["content_md"])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{report['title']}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; background: #f8fafc; color: #1e293b; line-height: 1.7; }}
  h1 {{ color: #0f172a; border-bottom: 3px solid #3b82f6; padding-bottom: 0.5rem; }}
  h2 {{ color: #1e40af; margin-top: 2rem; }}
  h3 {{ color: #334155; }}
  code {{ background: #e2e8f0; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.9em; }}
  pre {{ background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 8px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 0.5rem 0.75rem; text-align: left; }}
  th {{ background: #f1f5f9; font-weight: 600; }}
  blockquote {{ border-left: 4px solid #3b82f6; margin: 1rem 0; padding: 0.5rem 1rem; background: #eff6ff; }}
  ul, ol {{ padding-left: 1.5rem; }}
  li {{ margin-bottom: 0.25rem; }}
  .meta {{ color: #64748b; font-size: 0.875rem; margin-bottom: 2rem; }}
  .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 0.8rem; }}
  .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }}
  .badge.quality {{ background: #dcfce7; color: #166534; }}
</style>
</head>
<body>
<h1>{report['title']}</h1>
<div class="meta">
  <span class="badge quality">Quality: {report.get('quality_score', 'N/A')}</span> &middot;
  {report['report_type'].title()} Report &middot;
  {report['period_start']} to {report['period_end']} &middot;
  Revisions: {report.get('revision_count', 0)}
</div>
{content_html}
<div class="footer">
  Generated by AI Trends Explorer &middot; ESADE PDAI Project &middot; Pedro Resende
</div>
</body>
</html>"""
    return HTMLResponse(content=html, headers={
        "Content-Disposition": f'attachment; filename="report-{report_id}.html"',
    })


@app.get("/reports/{report_id}/qmd")
def export_report_qmd(report_id: int):
    """Export a report as a Quarto (.qmd) document."""
    report = db.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    template_path = TEMPLATES_DIR / "report.qmd"
    if template_path.exists():
        template = template_path.read_text()
    else:
        template = """---
title: "{title}"
subtitle: "AI Trends Explorer | {report_type} Report"
author: "AI Trends Explorer"
date: "{date}"
format:
  html:
    theme: cosmo
    toc: true
    toc-depth: 3
    toc-location: left
    embed-resources: true
    smooth-scroll: true
---

{content}
"""

    qmd = template.format(
        title=report["title"],
        report_type=report["report_type"].title(),
        date=str(report.get("created_at", ""))[:10],
        period_start=report["period_start"],
        period_end=report["period_end"],
        quality_score=report.get("quality_score", "N/A"),
        revision_count=report.get("revision_count", 0),
        items_analyzed=len(report.get("item_ids") or []),
        content=report["content_md"],
    )

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=qmd,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.qmd"'},
    )


# ─── Full Pipeline ───────────────────────────────────────

@app.post("/pipeline/daily")
@traceable(name="daily_pipeline")
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
@traceable(name="weekly_pipeline")
def run_weekly_pipeline():
    """Full weekly pipeline: daily pipeline + generate weekly report."""
    daily = run_daily_pipeline()
    report = generate_report(report_type="weekly")
    return {"daily_pipeline": daily, "report": report.model_dump()}


@app.post("/pipeline/monthly")
@traceable(name="monthly_pipeline")
def run_monthly_pipeline():
    """Full monthly pipeline: daily pipeline + generate monthly report."""
    daily = run_daily_pipeline()
    report = generate_report(report_type="monthly")
    return {"daily_pipeline": daily, "report": report.model_dump()}
