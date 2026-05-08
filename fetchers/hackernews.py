import asyncio
import httpx

import config
import db

HN_BASE = "https://hacker-news.firebaseio.com/v0"


async def fetch_story(client: httpx.AsyncClient, story_id: int) -> dict | None:
    try:
        resp = await client.get(f"{HN_BASE}/item/{story_id}.json", timeout=10)
        data = resp.json()
        if not data or data.get("type") != "story":
            return None
        url = data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        title = data.get("title", "").strip()
        if not title:
            return None
        return {
            "url": url,
            "title": title,
            "source": "Hacker News",
            "category": "tech",
            "published": "",
        }
    except Exception:
        return None


async def fetch_hackernews() -> list[dict]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{HN_BASE}/topstories.json", timeout=10)
            ids = resp.json()[: config.HN_STORIES_COUNT]
        except Exception as exc:
            print(f"[HN] Failed to fetch top stories: {exc}")
            return []

        tasks = [fetch_story(client, sid) for sid in ids]
        results = await asyncio.gather(*tasks)

    articles = [r for r in results if r]
    urls = [a["url"] for a in articles]
    already_seen = db.seen_urls(urls)
    new_articles = [a for a in articles if a["url"] not in already_seen]

    db.save_articles(new_articles)
    print(f"[HN] Fetched {len(articles)}, {len(new_articles)} new")
    return new_articles
