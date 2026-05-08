import anthropic
from datetime import datetime
from collections import defaultdict

import config
import db

CATEGORY_LABELS = {
    "world": "World News",
    "geopolitics": "Geopolitics & International Relations",
    "india": "India",
    "tamil_nadu": "Tamil Nadu & Local",
    "tech": "Technology & Science",
    "business": "Business & Economy",
}

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _build_prompt(articles_by_category: dict[str, list[dict]], slot_label: str) -> str:
    lines = [
        f"You are a sharp, concise news analyst. Summarize the following news headlines for the {slot_label} digest.",
        "For EACH category, write 3-6 bullet points. Each bullet should:",
        "- Capture the key fact/event in one clear sentence",
        "- Include any important context (who, what, where, why it matters)",
        "- Group related stories together if they cover the same event",
        "- Flag any breaking or high-importance items with [BREAKING] or [IMPORTANT]",
        "",
        "Be specific, not vague. Prefer facts over generalizations.",
        "At the end, add a brief 2-3 sentence 'Big Picture' paragraph connecting the day's major themes.",
        "",
        "NEWS HEADLINES BY CATEGORY:",
        "=" * 60,
    ]

    for cat, articles in articles_by_category.items():
        label = CATEGORY_LABELS.get(cat, cat.title())
        lines.append(f"\n## {label}")
        for art in articles[:20]:
            lines.append(f"- [{art['source']}] {art['title']}")

    lines.append("\n" + "=" * 60)
    lines.append("Now write the digest:")

    return "\n".join(lines)


async def generate_digest(slot_label: str) -> dict:
    # Pull articles from the last 2.5 hours (catches any slight timing drift)
    articles = db.get_recent_articles(hours=3)

    if not articles:
        print("[Summarizer] No new articles found for this slot")
        fallback = "No new articles were available for this digest slot."
        db.save_digest(slot_label, fallback, {}, 0)
        return {"summary": fallback, "categories": {}, "article_count": 0}

    # Group by category
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for art in articles:
        by_cat[art["category"]].append(art)

    prompt = _build_prompt(dict(by_cat), slot_label)

    print(f"[Summarizer] Generating digest for {slot_label} with {len(articles)} articles...")

    if not config.ANTHROPIC_API_KEY:
        # Fallback: plain headline list when no API key
        summary = _fallback_summary(dict(by_cat))
    else:
        client = _get_client()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = message.content[0].text

    categories_meta = {
        cat: {"count": len(arts), "label": CATEGORY_LABELS.get(cat, cat.title())}
        for cat, arts in by_cat.items()
    }

    db.save_digest(slot_label, summary, categories_meta, len(articles))
    print(f"[Summarizer] Digest saved for {slot_label}")

    return {
        "summary": summary,
        "categories": categories_meta,
        "article_count": len(articles),
    }


def _fallback_summary(by_cat: dict[str, list[dict]]) -> str:
    lines = ["**News Digest** (AI summarization disabled — set ANTHROPIC_API_KEY)\n"]
    for cat, articles in by_cat.items():
        label = CATEGORY_LABELS.get(cat, cat.title())
        lines.append(f"\n### {label}")
        for art in articles[:8]:
            lines.append(f"- [{art['source']}] {art['title']}")
    return "\n".join(lines)
