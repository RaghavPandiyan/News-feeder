import httpx
import config
import db

NEWSAPI_BASE = "https://newsapi.org/v2"

QUERIES = [
    ("Tamil Nadu", "tamil_nadu"),
    ("India politics", "india"),
    ("geopolitics war diplomacy", "geopolitics"),
    ("technology AI", "tech"),
    ("economy markets", "business"),
]


async def fetch_newsapi() -> list[dict]:
    if not config.NEWS_API_KEY:
        return []

    all_articles = []
    async with httpx.AsyncClient() as client:
        for query, category in QUERIES:
            try:
                resp = await client.get(
                    f"{NEWSAPI_BASE}/everything",
                    params={
                        "q": query,
                        "sortBy": "publishedAt",
                        "pageSize": 10,
                        "apiKey": config.NEWS_API_KEY,
                        "language": "en",
                    },
                    timeout=15,
                )
                data = resp.json()
                for art in data.get("articles", []):
                    url = art.get("url", "")
                    title = art.get("title", "").strip()
                    if not url or not title or title == "[Removed]":
                        continue
                    all_articles.append({
                        "url": url,
                        "title": title,
                        "source": art.get("source", {}).get("name", "NewsAPI"),
                        "category": category,
                        "published": art.get("publishedAt", ""),
                    })
            except Exception as exc:
                print(f"[NewsAPI] Failed '{query}': {exc}")

    urls = [a["url"] for a in all_articles]
    already_seen = db.seen_urls(urls)
    new_articles = [a for a in all_articles if a["url"] not in already_seen]
    db.save_articles(new_articles)
    print(f"[NewsAPI] Fetched {len(all_articles)}, {len(new_articles)} new")
    return new_articles
