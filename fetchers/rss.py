import asyncio
import feedparser
import httpx
from datetime import datetime
from email.utils import parsedate_to_datetime

import config
import db


async def fetch_feed(client: httpx.AsyncClient, name: str, url: str, category: str) -> list[dict]:
    try:
        resp = await client.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as exc:
        print(f"[RSS] Failed {name}: {exc}")
        return []

    articles = []
    for entry in feed.entries[:15]:
        link = entry.get("link", "")
        title = entry.get("title", "").strip()
        if not link or not title:
            continue

        published = ""
        if entry.get("published"):
            try:
                published = parsedate_to_datetime(entry.published).isoformat()
            except Exception:
                published = entry.published

        articles.append({
            "url": link,
            "title": title,
            "source": name,
            "category": category,
            "published": published,
        })

    return articles


async def fetch_all_rss() -> list[dict]:
    tasks = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; NewsFeeder/1.0; +https://github.com/NewsFeeder)"
        )
    }
    async with httpx.AsyncClient(headers=headers) as client:
        for category, feeds in config.RSS_FEEDS.items():
            for name, url in feeds:
                tasks.append(fetch_feed(client, name, url, category))
        results = await asyncio.gather(*tasks)

    all_articles: list[dict] = []
    for batch in results:
        all_articles.extend(batch)

    # Deduplicate against DB
    urls = [a["url"] for a in all_articles]
    already_seen = db.seen_urls(urls)
    new_articles = [a for a in all_articles if a["url"] not in already_seen]

    db.save_articles(new_articles)
    print(f"[RSS] Fetched {len(all_articles)} items, {len(new_articles)} new")
    return new_articles
