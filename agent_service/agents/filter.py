import json
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from agent_service.config import settings
from agent_service.models import FilterResult

load_dotenv()

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "filter.txt"


def get_filter_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        api_key=settings.anthropic_api_key,
        max_tokens=300,
        temperature=0,
    )


def load_filter_prompt() -> str:
    return PROMPT_PATH.read_text()


def filter_item(item: dict) -> FilterResult:
    """Score a single item for relevance and novelty using Haiku."""
    llm = get_filter_llm()
    system_prompt = load_filter_prompt()

    user_message = (
        f"Source ID: {item['source_id']}\n"
        f"Title: {item['title']}\n"
        f"Summary: {item.get('summary', 'N/A')}\n"
        f"Source: {item.get('source', 'unknown')}\n"
        f"Authors: {', '.join(item.get('authors', []))}\n"
    )

    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ])

    try:
        raw = re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", response.content).strip()
        data = json.loads(raw)
        return FilterResult(**data)
    except (json.JSONDecodeError, Exception) as e:
        # Graceful fallback: assign low scores so item doesn't get lost
        return FilterResult(
            source_id=item["source_id"],
            relevance_score=0.3,
            novelty_score=0.3,
            topics=[],
            reasoning=f"Filter parse error: {e}",
        )


def filter_batch(items: list[dict]) -> list[FilterResult]:
    """Score a batch of items. Processes sequentially with rate limit handling."""
    results = []
    for i, item in enumerate(items):
        for attempt in range(3):
            try:
                result = filter_item(item)
                results.append(result)
                break
            except Exception as e:
                if "rate" in str(e).lower() or "429" in str(e):
                    wait = 2 ** attempt * 5
                    print(f"[filter] Rate limited on item {i+1}, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        # 1.5s delay = ~40 req/min, safely under Haiku's 50 req/min limit
        if i < len(items) - 1:
            time.sleep(1.5)
    return results
