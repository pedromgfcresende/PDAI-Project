# Prompt: Improve Agent Prompts for Better Report Quality

## Context

The AI Trends Explorer has four agent prompts in `agent_service/prompts/`. After reviewing them, several improvements would reduce hallucinations, stabilize scoring, and produce sharper reports. The changes below are additive — don't remove existing content, only add or refine.

## Changes by File

### 1. `agent_service/prompts/filter.txt`

**Add date context.** Insert at the top, before the first sentence:

```
Today's date is {date}.
```

Then update `agent_service/agents/filter.py` so the filter prompt is formatted with the current date before being sent. Currently the prompt is loaded raw via `load_filter_prompt()` — change it to call `.format(date=date.today().isoformat())` or pass the date in the user message.

**Add few-shot calibration examples.** Append after the final line ("Only genuinely important developments should score above 0.7."):

```
## Examples

Example 1 (high relevance):
Title: "GPT-5 Released with Native Tool Use and 10M Token Context"
→ relevance_score: 0.92, novelty_score: 0.85, topics: ["LLMs", "industry"]
→ reasoning: "Major frontier model release with two genuinely new capabilities — immediate strategic impact for every AI-dependent product."

Example 2 (low relevance):
Title: "A Survey of Transformer Architectures for NLP Tasks"
→ relevance_score: 0.15, novelty_score: 0.05, topics: ["research", "LLMs"]
→ reasoning: "Survey paper with no new results — rehashes known architectures."

Example 3 (medium relevance):
Title: "LoRA Fine-Tuning Reduces Cost 40% on Domain-Specific Tasks"
→ relevance_score: 0.55, novelty_score: 0.35, topics: ["efficiency", "applications"]
→ reasoning: "Useful efficiency gain but LoRA is well-established; the 40% figure is notable but not paradigm-shifting."
```

---

### 2. `agent_service/prompts/weekly_synthesis.txt`

**Replace the first line** with a more grounded persona:

```
You are an expert AI analyst at a consulting firm's internal intelligence team. You write weekly briefings that help technology leaders and business strategists advise their clients on AI strategy. Your audience is informed but time-constrained — they want signal, not noise.
```

**Add anti-hallucination guardrail.** Insert as the first guideline (before "Lead with insight"):

```
- CRITICAL: Only reference developments from the source items provided below. Do not introduce facts, companies, metrics, funding amounts, or benchmark scores from your own knowledge. Every claim in the report must be traceable to a specific source item. If you don't have enough items for a section, omit that section entirely rather than padding with generic commentary.
```

**Improve citation instructions.** Replace the existing citation line with:

```
- Cite sources inline where you reference specific facts or claims, formatted as: [Title](URL). Do not batch citations at section ends — the critic needs to trace each claim to its source.
```

---

### 3. `agent_service/prompts/monthly_report.txt`

**Add the same anti-hallucination guardrail.** Insert as the first guideline (before "This is a deep report"):

```
- CRITICAL: Only reference developments from the source items provided below. Do not introduce facts, companies, metrics, funding amounts, or benchmark scores from your own knowledge. Every claim must be traceable to a specific source item. If a section has insufficient material, merge it with a related section or omit it.
```

**Add citation instructions** (currently missing entirely). Add after the anti-hallucination line:

```
- Cite sources inline where you reference specific facts, formatted as: [Title](URL).
```

---

### 4. `agent_service/prompts/critic.txt`

**Strengthen the grounding evaluation.** Replace the current grounding line:

```
1. **Grounding** — Are claims supported by the provided source items? Are there fabricated details or unsupported extrapolations?
```

With:

```
1. **Grounding** — Are claims supported by the provided source items? To evaluate this: identify at least 3 specific factual claims in the report (company names, metrics, funding amounts, benchmark scores, product features) and verify whether each one appears in the source items. In your feedback, list any claims you cannot trace back to a source item — these are potential hallucinations.
```

**Make feedback actionable.** Replace the feedback field description:

```
"feedback": "<specific, constructive feedback for improvement — be direct about what's wrong and how to fix it>"
```

With:

```
"feedback": "<specific, actionable feedback. You MUST include: (1) at least one exact sentence or claim from the report that should be changed, and (2) a concrete rewrite suggestion. Vague feedback like 'could be more actionable' is not acceptable.>"
```

---

## Files to Modify

| File | Change |
|------|--------|
| `agent_service/prompts/filter.txt` | Add date placeholder, append few-shot examples |
| `agent_service/agents/filter.py` | Format the prompt with current date |
| `agent_service/prompts/weekly_synthesis.txt` | Stronger persona, anti-hallucination rule, inline citations |
| `agent_service/prompts/monthly_report.txt` | Anti-hallucination rule, add citation instructions |
| `agent_service/prompts/critic.txt` | Stronger grounding check with specific claim verification, actionable feedback requirement |

## Important Notes

- The filter prompt uses `{date}` as a placeholder — since `filter.py` doesn't currently `.format()` the prompt, you need to add that. Be careful: the JSON example in the prompt uses `{ }` braces which will conflict with `.format()`. Either switch to a template engine, use `{date}` only and handle the JSON braces by doubling them `{{ }}`, or inject the date via string concatenation instead of `.format()`.
- The weekly/monthly prompts already use `.format()` for `{period_start}`, `{period_end}`, `{items}`, `{signals}` — so any new `{placeholders}` need to be actual format variables, and any literal braces in added text must be doubled.
- The critic prompt uses `{{` double braces for its JSON example because it IS format-interpolated. Keep that convention.
- Don't change the JSON response schema for any prompt — only the instructions and guidelines.
