import asyncio
import httpx

import config
import db

# Uses Reddit's public JSON API — no OAuth needed for read-only public posts
REDDIT_BASE = "https://www.reddit.com"
HEADERS = {"User-Agent": config.REDDIT_USER_AGENT}


async def fetch_subreddit(client: httpx.AsyncClient, sub: str) -> list[dict]:
    url = f"{REDDIT_BASE}/r/{sub}/hot.json?limit=10"
    try:
        resp = await client.get(url, timeout=15, headers=HEADERS)
        data = resp.json()
        posts = data.get("data", {}).get("children", [])
    except Exception as exc:
        print(f"[Reddit] Failed r/{sub}: {exc}")
        return []

    articles = []
    for post in posts:
        p = post.get("data", {})
        if p.get("is_self") and not p.get("selftext"):
            continue
        link = p.get("url", "")
        title = p.get("title", "").strip()
        if not link or not title:
            continue

        # Map subreddit to category
        cat_map = {
            "worldnews": "world",
            "geopolitics": "geopolitics",
            "india": "india",
            "TamilNadu": "tamil_nadu",
            "technology": "tech",
            "science": "tech",
            "economics": "business",
        }
        category = cat_map.get(sub, "world")

        articles.append({
            "url": link,
            "title": title,
            "source": f"r/{sub}",
            "category": category,
            "published": "",
        })

    return articles


async def fetch_reddit() -> list[dict]:
    async with httpx.AsyncClient() as client:
        tasks = [fetch_subreddit(client, sub) for sub in config.REDDIT_SUBS]
        results = await asyncio.gather(*tasks)

    all_articles: list[dict] = []
    for batch in results:
        all_articles.extend(batch)

    urls = [a["url"] for a in all_articles]
    already_seen = db.seen_urls(urls)
    new_articles = [a for a in all_articles if a["url"] not in already_seen]

    db.save_articles(new_articles)
    print(f"[Reddit] Fetched {len(all_articles)}, {len(new_articles)} new")
    return new_articles
