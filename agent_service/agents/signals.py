import json
import re
from collections import Counter

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from agent_service.config import settings
from agent_service.models import TrendSignal

load_dotenv()

SIGNAL_PROMPT = """Analyze the following batch of AI/ML items and identify trend signals.
A signal is a pattern across multiple items that suggests an emerging, accelerating, or disruptive trend.

Signal types:
- **emergence**: A new topic/approach appearing for the first time across multiple sources
- **acceleration**: An existing trend gaining significantly more attention/papers/tools
- **disruption**: Something that challenges or replaces an established approach

For each signal, provide:
- signal_type: one of emergence, acceleration, disruption
- topic: short label (2-4 words)
- description: one sentence explaining the signal
- strength: 0.0-1.0 (how confident you are this is a real trend, not noise)
- evidence_ids: list of item indices (from the numbered list) supporting this signal

Return a JSON array of signals. Return an empty array if no clear signals are found.

## Items

{items}
"""


def get_signal_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        api_key=settings.anthropic_api_key,
        max_tokens=1024,
        temperature=0.1,
    )


def _format_items(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. [id={item.get('id', '?')}] [{item.get('source', '?')}] "
            f"{item['title']} | Topics: {', '.join(item.get('topics', []))}"
        )
    return "\n".join(lines)


def detect_signals(items: list[dict]) -> list[TrendSignal]:
    """Detect trend signals from a batch of scored items."""
    if len(items) < 5:
        return []

    llm = get_signal_llm()
    prompt = SIGNAL_PROMPT.format(items=_format_items(items))

    response = llm.invoke([{"role": "user", "content": prompt}])

    try:
        import re
        raw = re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", response.content).strip()
        signals_data = json.loads(raw)
        signals = []
        for s in signals_data:
            # Map evidence indices to actual item IDs
            evidence_ids = []
            for idx in s.get("evidence_ids", []):
                if 1 <= idx <= len(items) and items[idx - 1].get("id"):
                    evidence_ids.append(items[idx - 1]["id"])

            signals.append(TrendSignal(
                signal_type=s["signal_type"],
                topic=s["topic"],
                description=s["description"],
                strength=s.get("strength", 0.5),
                evidence_ids=evidence_ids,
            ))
        return signals
    except (json.JSONDecodeError, KeyError, Exception) as e:
        print(f"[signals] Error parsing signals: {e}")
        return []


def detect_signals_simple(items: list[dict]) -> list[TrendSignal]:
    """Heuristic-based signal detection (no LLM, used as fallback)."""
    topic_counter = Counter()
    for item in items:
        for topic in item.get("topics", []):
            topic_counter[topic] += 1

    signals = []
    for topic, count in topic_counter.most_common(5):
        if count >= 3:
            signals.append(TrendSignal(
                signal_type="acceleration",
                topic=topic,
                description=f"Topic '{topic}' appeared in {count} items this period.",
                strength=min(count / 20, 1.0),
                evidence_ids=[
                    item["id"] for item in items
                    if topic in item.get("topics", []) and item.get("id")
                ][:10],
            ))
    return signals
