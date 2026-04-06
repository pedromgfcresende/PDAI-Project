import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from agent_service.config import settings
from agent_service.models import SynthesisRequest, SynthesisResult

load_dotenv()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def get_synthesis_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
        temperature=0.3,
    )


def _load_prompt(report_type: str) -> str:
    if report_type == "weekly":
        return (PROMPTS_DIR / "weekly_synthesis.txt").read_text()
    return (PROMPTS_DIR / "monthly_report.txt").read_text()


def _format_items(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. [{item.get('source', '?')}] {item['title']}\n"
            f"   Topics: {', '.join(item.get('topics', []))}\n"
            f"   URL: {item.get('url', 'N/A')}\n"
            f"   {item.get('summary', '')[:300]}\n"
        )
    return "\n".join(lines)


def _format_signals(signals: list[dict]) -> str:
    if not signals:
        return "No active signals detected yet."
    lines = []
    for s in signals:
        lines.append(f"- [{s.get('signal_type', '?')}] {s['topic']}: {s['description']} (strength: {s.get('strength', '?')})")
    return "\n".join(lines)


def synthesize(request: SynthesisRequest) -> SynthesisResult:
    """Generate a report using Claude Sonnet."""
    llm = get_synthesis_llm()
    template = _load_prompt(request.report_type.value)

    prompt = template.format(
        period_start=request.period_start.isoformat(),
        period_end=request.period_end.isoformat(),
        items=_format_items(request.items),
        signals=_format_signals(request.signals),
    )

    # Add revision feedback if this is a retry
    if request.feedback:
        prompt += (
            f"\n\n## Critic Feedback (from previous draft)\n\n"
            f"Please address the following issues:\n{request.feedback}"
        )

    response = llm.invoke([
        {"role": "user", "content": prompt},
    ])

    content = response.content

    # Extract item IDs referenced
    item_ids = [item.get("id", 0) for item in request.items if item.get("id")]

    # Try to extract title from first line
    title = f"{'Weekly' if request.report_type == 'weekly' else 'Monthly'} AI Trends Report"
    lines = content.strip().split("\n")
    if lines and lines[0].startswith("#"):
        title = lines[0].lstrip("# ").strip()

    return SynthesisResult(
        title=title,
        content_md=content,
        item_ids=item_ids,
    )
