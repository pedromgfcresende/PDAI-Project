import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from agent_service.config import settings
from agent_service.models import CriticResult, CriticScores

load_dotenv()

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "critic.txt"


def get_critic_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key,
        max_tokens=1024,
        temperature=0,
    )


def _format_items_for_critic(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. [{item.get('source', '?')}] {item['title']}: {item.get('summary', '')[:200]}")
    return "\n".join(lines)


def critique(
    title: str,
    report_type: str,
    period_start: str,
    period_end: str,
    content: str,
    items: list[dict],
) -> CriticResult:
    """Review a report using Groq Llama (different model family for cross-validation)."""
    llm = get_critic_llm()
    template = PROMPT_PATH.read_text()

    prompt = template.format(
        title=title,
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        content=content,
        items=_format_items_for_critic(items),
    )

    response = llm.invoke([
        {"role": "user", "content": prompt},
    ])

    try:
        data = json.loads(response.content)
        scores = CriticScores(**data["scores"])
        return CriticResult(
            scores=scores,
            overall_score=data.get("overall_score", sum(scores.model_dump().values()) / 4),
            feedback=data.get("feedback", ""),
            approved=data.get("approved", False),
        )
    except (json.JSONDecodeError, KeyError, Exception) as e:
        # On parse failure, return a conservative "needs revision" result
        return CriticResult(
            scores=CriticScores(grounding=5, coherence=5, completeness=5, actionability=5),
            overall_score=5.0,
            feedback=f"Critic response could not be parsed: {e}. Manual review recommended.",
            approved=False,
        )
