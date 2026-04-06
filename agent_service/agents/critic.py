import json
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from agent_service.config import settings
from agent_service.models import CriticResult, CriticScores

load_dotenv()

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "critic.txt"


def get_groq_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key,
        max_tokens=1024,
        temperature=0,
    )


def get_gemini_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.google_ai_api_key,
        max_output_tokens=1024,
        temperature=0,
    )


def _format_items_for_critic(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. [{item.get('source', '?')}] {item['title']}: {item.get('summary', '')[:200]}")
    return "\n".join(lines)


def _parse_critic_response(text: str) -> CriticResult:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    data = json.loads(text)
    scores = CriticScores(**data["scores"])
    return CriticResult(
        scores=scores,
        overall_score=data.get("overall_score", sum(scores.model_dump().values()) / 4),
        feedback=data.get("feedback", ""),
        approved=data.get("approved", False),
    )


def critique(
    title: str,
    report_type: str,
    period_start: str,
    period_end: str,
    content: str,
    items: list[dict],
) -> CriticResult:
    """Review a report. Tries Groq Llama first, falls back to Gemini Flash on rate limit."""
    template = PROMPT_PATH.read_text()
    prompt = template.format(
        title=title,
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        content=content,
        items=_format_items_for_critic(items),
    )
    messages = [{"role": "user", "content": prompt}]

    # Try Groq first
    try:
        response = get_groq_llm().invoke(messages)
        return _parse_critic_response(response.content)
    except Exception as e:
        if "429" in str(e) or "rate" in str(e).lower():
            print("[critic] Groq rate limited, falling back to Gemini Flash...")
        else:
            print(f"[critic] Groq error: {e}, falling back to Gemini Flash...")

    # Fallback to Gemini
    try:
        response = get_gemini_llm().invoke(messages)
        return _parse_critic_response(response.content)
    except Exception as e:
        print(f"[critic] Gemini fallback also failed: {e}")
        return CriticResult(
            scores=CriticScores(grounding=5, coherence=5, completeness=5, actionability=5),
            overall_score=5.0,
            feedback=f"Both Groq and Gemini failed. Manual review recommended.",
            approved=False,
        )
