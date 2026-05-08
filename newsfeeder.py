"""
News Feeder — single file, drop anywhere and run.

Install deps once:
    pip install fastapi uvicorn apscheduler feedparser httpx anthropic python-dotenv

Run:
    python newsfeeder.py

Open: http://localhost:8000

Set your Anthropic API key (for AI summaries):
    Windows:  set ANTHROPIC_API_KEY=sk-ant-...
    Mac/Linux: export ANTHROPIC_API_KEY=sk-ant-...
Or create a .env file next to this script with:
    ANTHROPIC_API_KEY=sk-ant-...
"""

import asyncio
import json
import os
import sqlite3
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime

# ── Load .env if present ──────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TIMEZONE          = os.getenv("TIMEZONE", "Asia/Kolkata")
PORT              = int(os.getenv("PORT", 8000))
HOST              = os.getenv("HOST", "0.0.0.0")

SCHEDULE_HOURS = [8, 10, 12, 14, 16, 18, 20, 22, 0, 2]

RSS_FEEDS = {
    "world": [
        ("BBC World",         "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Al Jazeera",        "https://www.aljazeera.com/xml/rss/all.xml"),
        ("Google News World", "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en"),
    ],
    "geopolitics": [
        ("Foreign Policy",    "https://foreignpolicy.com/feed/"),
        ("The Diplomat",      "https://thediplomat.com/feed/"),
        ("Google News Geo",   "https://news.google.com/rss/search?q=geopolitics+international+relations&hl=en-US&gl=US&ceid=US:en"),
    ],
    "tamil_nadu": [
        ("The Hindu TN",      "https://www.thehindu.com/news/national/tamil-nadu/feeder/default.rss"),
        ("Google News TN",    "https://news.google.com/rss/search?q=Tamil+Nadu&hl=en-IN&gl=IN&ceid=IN:en"),
        ("Times of India TN", "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms"),
    ],
    "tech": [
        ("TechCrunch",        "https://techcrunch.com/feed/"),
        ("The Verge",         "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica",      "https://feeds.arstechnica.com/arstechnica/index"),
        ("Wired",             "https://www.wired.com/feed/rss"),
        ("MIT Tech Review",   "https://www.technologyreview.com/feed/"),
    ],
    "india": [
        ("The Hindu India",   "https://www.thehindu.com/news/national/feeder/default.rss"),
        ("Indian Express",    "https://indianexpress.com/feed/"),
        ("NDTV India",        "https://feeds.feedburner.com/ndtvnews-india-news"),
        ("Google News India", "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGx1YlY4U0FtVnVLQUFQAQ?hl=en-IN&gl=IN&ceid=IN:en"),
    ],
    "business": [
        ("BBC Business",      "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("Google News Biz",   "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6Y0dFU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en"),
    ],
}

REDDIT_SUBS = ["worldnews", "geopolitics", "india", "TamilNadu", "technology", "economics"]
HN_COUNT    = 20

CATEGORY_LABELS = {
    "world":       "World News",
    "geopolitics": "Geopolitics & International Relations",
    "india":       "India",
    "tamil_nadu":  "Tamil Nadu & Local",
    "tech":        "Technology & Science",
    "business":    "Business & Economy",
}

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_feeder.db")

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                url        TEXT UNIQUE,
                title      TEXT,
                source     TEXT,
                category   TEXT,
                published  TEXT,
                fetched_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS digests (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at    TEXT DEFAULT (datetime('now')),
                slot_label    TEXT,
                summary       TEXT,
                categories    TEXT,
                article_count INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_articles_fetched ON articles(fetched_at);
            CREATE INDEX IF NOT EXISTS idx_digests_created  ON digests(created_at);
        """)

def seen_urls(urls):
    if not urls:
        return set()
    with get_conn() as conn:
        ph   = ",".join("?" * len(urls))
        rows = conn.execute(f"SELECT url FROM articles WHERE url IN ({ph})", urls).fetchall()
    return {r["url"] for r in rows}

def save_articles(articles):
    if not articles:
        return
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO articles (url,title,source,category,published) VALUES (:url,:title,:source,:category,:published)",
            articles,
        )

def save_digest(slot_label, summary, categories, article_count):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO digests (slot_label,summary,categories,article_count) VALUES (?,?,?,?)",
            (slot_label, summary, json.dumps(categories), article_count),
        )

def get_latest_digest():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM digests ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    d = dict(row)
    d["categories"] = json.loads(d["categories"] or "{}")
    return d

def get_digest_history(limit=20):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM digests ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["categories"] = json.loads(d["categories"] or "{}")
        result.append(d)
    return result

def get_recent_articles(hours=3, limit=300):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE fetched_at >= datetime('now',?) ORDER BY fetched_at DESC LIMIT ?",
            (f"-{hours} hours", limit),
        ).fetchall()
    return [dict(r) for r in rows]

# ── Fetchers ──────────────────────────────────────────────────────────────────
BROWSER_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control":   "no-cache",
}

async def _fetch_feed(client, name, url, category):
    import feedparser
    from email.utils import parsedate_to_datetime
    try:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"  [RSS] {name}: {e}")
        return []
    articles = []
    for entry in feed.entries[:15]:
        link  = entry.get("link", "")
        title = entry.get("title", "").strip()
        if not link or not title:
            continue
        published = ""
        try:
            published = parsedate_to_datetime(entry.published).isoformat()
        except Exception:
            published = entry.get("published", "")
        articles.append({"url": link, "title": title, "source": name, "category": category, "published": published})
    return articles

async def fetch_rss():
    import httpx
    tasks = []
    async with httpx.AsyncClient(headers=BROWSER_HEADERS, follow_redirects=True) as client:
        for cat, feeds in RSS_FEEDS.items():
            for name, url in feeds:
                tasks.append(_fetch_feed(client, name, url, cat))
        batches = await asyncio.gather(*tasks)
    all_a = [a for b in batches for a in b]
    new_a = [a for a in all_a if a["url"] not in seen_urls([a["url"] for a in all_a])]
    save_articles(new_a)
    print(f"  [RSS] {len(all_a)} fetched, {len(new_a)} new")
    return new_a

async def fetch_hackernews():
    import httpx
    BASE = "https://hacker-news.firebaseio.com/v0"
    async with httpx.AsyncClient() as client:
        try:
            ids = (await client.get(f"{BASE}/topstories.json", timeout=10)).json()[:HN_COUNT]
        except Exception as e:
            print(f"  [HN] {e}")
            return []
        async def get_story(sid):
            try:
                d = (await client.get(f"{BASE}/item/{sid}.json", timeout=8)).json()
                if not d or d.get("type") != "story":
                    return None
                return {"url": d.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                        "title": d.get("title","").strip(), "source": "Hacker News",
                        "category": "tech", "published": ""}
            except Exception:
                return None
        results = await asyncio.gather(*[get_story(i) for i in ids])
    articles = [r for r in results if r and r["title"]]
    new_a    = [a for a in articles if a["url"] not in seen_urls([a["url"] for a in articles])]
    save_articles(new_a)
    print(f"  [HN] {len(articles)} fetched, {len(new_a)} new")
    return new_a

async def fetch_reddit():
    import httpx
    CAT_MAP = {"worldnews":"world","geopolitics":"geopolitics","india":"india",
               "TamilNadu":"tamil_nadu","technology":"tech","economics":"business"}
    headers = {"User-Agent": "NewsFeeder/1.0 (personal aggregator)", "Accept": "application/json"}
    all_a = []
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for sub in REDDIT_SUBS:
            try:
                data  = (await client.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=10", timeout=12)).json()
                posts = data.get("data", {}).get("children", [])
                for p in posts:
                    pd = p.get("data", {})
                    url   = pd.get("url","")
                    title = pd.get("title","").strip()
                    if url and title:
                        all_a.append({"url":url,"title":title,"source":f"r/{sub}",
                                      "category":CAT_MAP.get(sub,"world"),"published":""})
            except Exception as e:
                print(f"  [Reddit] r/{sub}: {e}")
    new_a = [a for a in all_a if a["url"] not in seen_urls([a["url"] for a in all_a])]
    save_articles(new_a)
    print(f"  [Reddit] {len(all_a)} fetched, {len(new_a)} new")
    return new_a

# ── Summariser ────────────────────────────────────────────────────────────────
def _build_prompt(by_cat, slot_label):
    lines = [
        f"You are a sharp, concise news analyst. Summarise the following headlines for the {slot_label} digest.",
        "For EACH category write 3-6 bullet points. Each bullet should:",
        "- State the key fact in one clear sentence with context (who/what/where/why it matters)",
        "- Group related stories on the same event",
        "- Prefix truly breaking or high-importance items with [BREAKING] or [IMPORTANT]",
        "Be specific, not vague. End with a 2-3 sentence 'Big Picture' paragraph.",
        "", "HEADLINES BY CATEGORY:", "="*60,
    ]
    for cat, arts in by_cat.items():
        lines.append(f"\n## {CATEGORY_LABELS.get(cat, cat.title())}")
        for a in arts[:20]:
            lines.append(f"- [{a['source']}] {a['title']}")
    lines += ["", "="*60, "Write the digest now:"]
    return "\n".join(lines)

async def generate_digest(slot_label):
    articles = get_recent_articles(hours=3)
    if not articles:
        summary = "No new articles were available for this digest slot."
        save_digest(slot_label, summary, {}, 0)
        return {"summary": summary, "categories": {}, "article_count": 0}

    by_cat = defaultdict(list)
    for a in articles:
        by_cat[a["category"]].append(a)

    if ANTHROPIC_API_KEY:
        import anthropic
        client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt  = _build_prompt(dict(by_cat), slot_label)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = message.content[0].text
    else:
        lines = [f"**{slot_label} Digest** — set ANTHROPIC_API_KEY for AI summaries\n"]
        for cat, arts in by_cat.items():
            lines.append(f"\n### {CATEGORY_LABELS.get(cat, cat.title())}")
            for a in arts[:8]:
                lines.append(f"- [{a['source']}] {a['title']}")
        summary = "\n".join(lines)

    cats_meta = {c: {"count": len(a), "label": CATEGORY_LABELS.get(c, c.title())} for c, a in by_cat.items()}
    save_digest(slot_label, summary, cats_meta, len(articles))
    print(f"  [Digest] Saved for {slot_label} ({len(articles)} articles)")
    return {"summary": summary, "categories": cats_meta, "article_count": len(articles)}

# ── Scheduler ─────────────────────────────────────────────────────────────────
def _slot_label(hour):
    s = "AM" if hour < 12 else "PM"
    h = hour if hour <= 12 else hour - 12
    h = 12 if h == 0 else h
    return f"{h}:00 {s}"

async def run_slot(hour):
    label = _slot_label(hour)
    print(f"\n{'='*50}\n[Scheduler] {label} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*50}")
    await asyncio.gather(fetch_rss(), fetch_hackernews(), fetch_reddit(), return_exceptions=True)
    await generate_digest(label)

def build_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    sched = AsyncIOScheduler(timezone=TIMEZONE)
    for h in SCHEDULE_HOURS:
        sched.add_job(run_slot, CronTrigger(hour=h, minute=0, timezone=TIMEZONE),
                      args=[h], id=f"slot_{h:02d}", name=f"Digest {_slot_label(h)}",
                      replace_existing=True, misfire_grace_time=300)
    return sched

# ── FastAPI app ───────────────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

_scheduler = None

@asynccontextmanager
async def lifespan(app):
    global _scheduler
    init_db()
    _scheduler = build_scheduler()
    _scheduler.start()
    print(f"\n✅ News Feeder running → http://localhost:{PORT}")
    print(f"   Timezone : {TIMEZONE}")
    print(f"   AI summaries : {'ON ✓' if ANTHROPIC_API_KEY else 'OFF (no ANTHROPIC_API_KEY)'}")
    print(f"   Schedule : {[_slot_label(h) for h in SCHEDULE_HOURS]}\n")
    yield
    _scheduler.shutdown(wait=False)

app = FastAPI(title="News Feeder", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(DASHBOARD_HTML)

@app.get("/api/status")
async def api_status():
    d = get_latest_digest()
    return {
        "running": _scheduler.running if _scheduler else False,
        "timezone": TIMEZONE,
        "schedule_hours": SCHEDULE_HOURS,
        "ai_enabled": bool(ANTHROPIC_API_KEY),
        "last_digest_at": d["created_at"] if d else None,
        "sources": {"rss": True, "hackernews": True, "reddit": True},
    }

@app.get("/api/latest")
async def api_latest():
    d = get_latest_digest()
    if not d:
        return {"digest": None, "message": "No digest yet — click ⚡ Fetch Now"}
    return {"digest": d}

@app.get("/api/history")
async def api_history(limit: int = 30):
    return {"history": get_digest_history(limit)}

@app.get("/api/articles")
async def api_articles(hours: int = 3, limit: int = 200):
    return {"articles": get_recent_articles(hours, limit)}

@app.post("/api/fetch-now")
async def api_fetch_now():
    try:
        label = f"Manual {datetime.now().strftime('%I:%M %p')}"
        await asyncio.gather(fetch_rss(), fetch_hackernews(), fetch_reddit(), return_exceptions=True)
        result = await generate_digest(label)
        return {"status": "ok", "digest": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/schedule")
async def api_schedule():
    if not _scheduler:
        return {"timezone": TIMEZONE, "jobs": []}
    jobs = []
    for job in _scheduler.get_jobs():
        nrt = job.next_run_time
        jobs.append({"id": job.id, "name": job.name, "next_run": nrt.isoformat() if nrt else None})
    return {"timezone": TIMEZONE, "jobs": jobs}

# ── Dashboard HTML ────────────────────────────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>News Feeder</title>
<style>
:root{--bg:#0f1117;--surface:#1a1d27;--surface2:#22263a;--border:#2d3148;--accent:#4f8ef7;--accent2:#7c5cbf;--green:#34d399;--yellow:#fbbf24;--red:#f87171;--text:#e2e8f0;--muted:#8892a4;--radius:12px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;min-height:100vh;line-height:1.6}
header{background:var(--surface);border-bottom:1px solid var(--border);padding:16px 24px;display:flex;align-items:center;justify-content:space-between;gap:12px;position:sticky;top:0;z-index:100}
.logo{display:flex;align-items:center;gap:10px;font-size:1.2rem;font-weight:700}
.logo-icon{width:32px;height:32px;background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px}
.header-right{display:flex;align-items:center;gap:12px}
.status-badge{display:flex;align-items:center;gap:6px;font-size:.8rem;color:var(--muted);background:var(--surface2);padding:6px 12px;border-radius:20px;border:1px solid var(--border)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.btn{padding:8px 16px;border-radius:8px;border:none;cursor:pointer;font-size:.85rem;font-weight:600;transition:all .15s}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{background:#3a7be8}.btn-primary:disabled{opacity:.5;cursor:not-allowed}
.btn-ghost{background:var(--surface2);color:var(--text);border:1px solid var(--border)}.btn-ghost:hover{background:var(--border)}
.container{max-width:1100px;margin:0 auto;padding:24px 16px}
.tabs{display:flex;gap:4px;margin-bottom:24px;background:var(--surface);padding:4px;border-radius:10px;border:1px solid var(--border);width:fit-content}
.tab{padding:8px 18px;border-radius:7px;cursor:pointer;font-size:.85rem;font-weight:500;color:var(--muted);transition:all .15s;border:none;background:none}
.tab.active{background:var(--accent);color:#fff}.tab:hover:not(.active){color:var(--text)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin-bottom:20px}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.card-title{font-size:1rem;font-weight:700;display:flex;align-items:center;gap:8px}
.tag{font-size:.7rem;padding:3px 8px;border-radius:20px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.tag-blue{background:rgba(79,142,247,.15);color:var(--accent)}.tag-purple{background:rgba(124,92,191,.15);color:#a78bfa}
.tag-green{background:rgba(52,211,153,.15);color:var(--green)}.tag-yellow{background:rgba(251,191,36,.15);color:var(--yellow)}
.tag-red{background:rgba(248,113,113,.15);color:var(--red)}
.digest-meta{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;font-size:.82rem;color:var(--muted)}
.digest-body{font-size:.93rem;line-height:1.8}
.digest-body h2,.digest-body h3{color:var(--accent);margin:20px 0 8px;font-size:.95rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.digest-body ul{padding-left:0;list-style:none}.digest-body li{padding:5px 0 5px 16px;border-left:2px solid var(--border);margin-bottom:4px;transition:border-color .15s}
.digest-body li:hover{border-left-color:var(--accent)}
.stats-bar{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;text-align:center}
.stat-value{font-size:1.8rem;font-weight:800;color:var(--accent)}.stat-label{font-size:.78rem;color:var(--muted);margin-top:2px}
.history-item{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-radius:8px;border:1px solid var(--border);margin-bottom:8px;cursor:pointer;transition:all .15s}
.history-item:hover{background:var(--surface2);border-color:var(--accent)}
.history-slot{font-weight:700;font-size:.95rem}.history-meta{font-size:.8rem;color:var(--muted);margin-top:2px}
.history-count{font-size:.8rem;color:var(--muted);background:var(--surface2);padding:3px 10px;border-radius:12px}
.schedule-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px}
.slot-card{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:14px;text-align:center}
.slot-card.next{border-color:var(--accent);background:rgba(79,142,247,.08)}
.slot-time{font-size:1.1rem;font-weight:700;margin-bottom:4px}.slot-next{font-size:.72rem;color:var(--accent);margin-top:4px}
.source-list{display:flex;flex-direction:column;gap:6px}
.source-row{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--surface2);border-radius:8px;font-size:.85rem}
.source-name{font-weight:500}.source-cat{color:var(--muted);font-size:.78rem}
.empty{text-align:center;padding:60px 20px;color:var(--muted)}.empty-icon{font-size:3rem;margin-bottom:12px}.empty h3{color:var(--text);margin-bottom:8px}
.spinner{width:20px;height:20px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite;display:inline-block}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-overlay{display:flex;align-items:center;justify-content:center;gap:10px;padding:40px;color:var(--muted)}
#toast{position:fixed;bottom:24px;right:24px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 20px;font-size:.85rem;z-index:999;opacity:0;transition:opacity .3s;pointer-events:none}
#toast.show{opacity:1}#toast.error{border-color:var(--red);color:var(--red)}#toast.success{border-color:var(--green);color:var(--green)}
.panel{display:none}.panel.active{display:block}
@media(max-width:600px){header{flex-wrap:wrap}.tabs{width:100%}.tab{flex:1;text-align:center}}
</style>
</head>
<body>
<header>
  <div class="logo"><div class="logo-icon">📡</div>News Feeder</div>
  <div class="header-right">
    <div class="status-badge"><span class="dot"></span><span id="status-text">Loading...</span></div>
    <button class="btn btn-primary" id="fetch-btn" onclick="fetchNow()">⚡ Fetch Now</button>
  </div>
</header>
<div class="container">
  <div class="stats-bar">
    <div class="stat-card"><div class="stat-value" id="stat-digests">—</div><div class="stat-label">Total Digests</div></div>
    <div class="stat-card"><div class="stat-value" id="stat-articles">—</div><div class="stat-label">Articles (3h)</div></div>
    <div class="stat-card"><div class="stat-value" id="stat-next">—</div><div class="stat-label">Next Digest</div></div>
    <div class="stat-card"><div class="stat-value" id="stat-ai">—</div><div class="stat-label">AI Summary</div></div>
  </div>
  <div class="tabs">
    <button class="tab active" onclick="showTab('latest',this)">Latest Digest</button>
    <button class="tab" onclick="showTab('history',this)">History</button>
    <button class="tab" onclick="showTab('schedule',this)">Schedule</button>
    <button class="tab" onclick="showTab('sources',this)">Sources</button>
  </div>
  <div class="panel active" id="panel-latest"><div id="latest-content"><div class="loading-overlay"><span class="spinner"></span> Loading...</div></div></div>
  <div class="panel" id="panel-history"><div id="history-content"><div class="loading-overlay"><span class="spinner"></span> Loading...</div></div></div>
  <div class="panel" id="panel-schedule">
    <div class="card">
      <div class="card-header"><div class="card-title">📅 Schedule</div><span class="tag tag-blue" id="tz-tag">—</span></div>
      <div class="schedule-grid" id="schedule-grid"><div class="loading-overlay"><span class="spinner"></span></div></div>
    </div>
  </div>
  <div class="panel" id="panel-sources">
    <div class="card">
      <div class="card-header"><div class="card-title">📰 RSS Sources</div><span class="tag tag-green">Free</span></div>
      <div class="source-list" id="rss-sources"></div>
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">🔥 More Sources</div></div>
      <div class="source-list">
        <div class="source-row"><div><div class="source-name">Hacker News</div><div class="source-cat">Top 20 stories</div></div><span class="tag tag-green">Free</span></div>
        <div class="source-row"><div><div class="source-name">Reddit</div><div class="source-cat">worldnews · geopolitics · india · TamilNadu · technology · economics</div></div><span class="tag tag-green">Free</span></div>
      </div>
    </div>
  </div>
</div>
<div id="toast"></div>
<script>
async function init(){
  await Promise.all([loadStatus(),loadLatest(),loadHistory(),loadSchedule()]);
  loadSources();
  setInterval(loadLatest,60000);
  setInterval(loadStatus,30000);
}
async function loadStatus(){
  try{
    const d=await(await fetch('/api/status')).json();
    document.getElementById('status-text').textContent=d.running?`Live · ${d.timezone}`:'Paused';
    document.getElementById('stat-ai').textContent=d.ai_enabled?'ON':'OFF';
  }catch(e){document.getElementById('status-text').textContent='Offline';}
}
async function loadLatest(){
  const d=await(await fetch('/api/latest')).json();
  try{const a=await(await fetch('/api/articles?hours=3&limit=500')).json();document.getElementById('stat-articles').textContent=a.articles.length;}catch(e){}
  const el=document.getElementById('latest-content');
  if(!d.digest){
    el.innerHTML=`<div class="empty"><div class="empty-icon">📭</div><h3>No digest yet</h3><p>${d.message||''}</p><br><button class="btn btn-primary" onclick="fetchNow()">⚡ Fetch Now</button></div>`;
    return;
  }
  const r=d.digest;
  const cats=Object.entries(r.categories||{}).map(([k,v])=>`<span class="tag tag-blue">${v.label} (${v.count})</span>`).join(' ');
  el.innerHTML=`<div class="card"><div class="card-header"><div class="card-title">📋 ${r.slot_label} Digest</div><span class="tag tag-purple">${r.article_count} articles</span></div><div class="digest-meta"><span>🕐 ${fmtDate(r.created_at)}</span></div><div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px">${cats}</div><div class="digest-body">${md(r.summary)}</div></div>`;
}
async function loadHistory(){
  const d=await(await fetch('/api/history?limit=30')).json();
  document.getElementById('stat-digests').textContent=d.history.length;
  const el=document.getElementById('history-content');
  if(!d.history.length){el.innerHTML='<div class="empty"><div class="empty-icon">📂</div><h3>No history yet</h3></div>';return;}
  el.innerHTML=d.history.map(r=>`<div class="history-item" onclick='showDigest(${JSON.stringify(JSON.stringify(r))})'><div><div class="history-slot">${r.slot_label}</div><div class="history-meta">${fmtDate(r.created_at)}</div></div><span class="history-count">${r.article_count} articles</span></div>`).join('');
}
function showDigest(js){
  const r=JSON.parse(js);
  const cats=Object.entries(r.categories||{}).map(([k,v])=>`<span class="tag tag-blue">${v.label}</span>`).join(' ');
  document.getElementById('history-content').innerHTML=`<button class="btn btn-ghost" onclick="loadHistory()" style="margin-bottom:16px">← Back</button><div class="card"><div class="card-header"><div class="card-title">📋 ${r.slot_label}</div><span class="tag tag-purple">${r.article_count} articles</span></div><div class="digest-meta"><span>🕐 ${fmtDate(r.created_at)}</span></div><div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px">${cats}</div><div class="digest-body">${md(r.summary)}</div></div>`;
}
async function loadSchedule(){
  const d=await(await fetch('/api/schedule')).json();
  document.getElementById('tz-tag').textContent=d.timezone;
  const now=new Date();let nextJob=null,nextTime=null;
  for(const j of d.jobs){if(j.next_run){const t=new Date(j.next_run);if(!nextTime||t<nextTime){nextTime=t;nextJob=j;}}}
  if(nextTime){const diff=Math.round((nextTime-now)/60000);document.getElementById('stat-next').textContent=diff>60?`${Math.floor(diff/60)}h ${diff%60}m`:`${diff}m`;}
  document.getElementById('schedule-grid').innerHTML=d.jobs.map(j=>{
    const isNext=j.id===nextJob?.id;
    const nr=j.next_run?new Date(j.next_run).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):'';
    return `<div class="slot-card ${isNext?'next':''}"><div class="slot-time">${j.name.replace('Digest ','')}</div>${isNext?'<div class="slot-next">⏰ Up next</div>':''}${nr?`<div style="font-size:.72rem;color:var(--muted);margin-top:4px">${nr}</div>`:''}</div>`;
  }).join('');
}
function loadSources(){
  const feeds=[
    ["BBC World","World","tag-blue"],["Al Jazeera","World","tag-blue"],["Google News World","World","tag-blue"],
    ["Foreign Policy","Geopolitics","tag-purple"],["The Diplomat","Geopolitics","tag-purple"],
    ["The Hindu TN","Tamil Nadu","tag-yellow"],["Google News TN","Tamil Nadu","tag-yellow"],["Times of India TN","Tamil Nadu","tag-yellow"],
    ["TechCrunch","Tech","tag-green"],["The Verge","Tech","tag-green"],["Ars Technica","Tech","tag-green"],["Wired","Tech","tag-green"],["MIT Tech Review","Tech","tag-green"],
    ["The Hindu India","India","tag-green"],["Indian Express","India","tag-green"],["NDTV India","India","tag-green"],["Google News India","India","tag-green"],
    ["BBC Business","Business","tag-blue"],["Google News Biz","Business","tag-blue"],
  ];
  document.getElementById('rss-sources').innerHTML=feeds.map(([n,c,t])=>`<div class="source-row"><div><div class="source-name">${n}</div><div class="source-cat">${c}</div></div><span class="tag ${t}">${c}</span></div>`).join('');
}
async function fetchNow(){
  const btn=document.getElementById('fetch-btn');
  btn.disabled=true;btn.innerHTML='<span class="spinner"></span> Fetching...';
  showToast('Fetching all sources…');
  try{
    const r=await(await fetch('/api/fetch-now',{method:'POST'})).json();
    if(r.status==='ok'){showToast('Digest ready!','success');await Promise.all([loadLatest(),loadHistory(),loadSchedule()]);}
    else showToast('Error: '+(r.detail||'unknown'),'error');
  }catch(e){showToast('Cannot reach server','error');}
  finally{btn.disabled=false;btn.innerHTML='⚡ Fetch Now';}
}
function showTab(n,b){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-'+n).classList.add('active');b.classList.add('active');
}
function fmtDate(iso){if(!iso)return'—';const d=new Date(iso+(iso.endsWith('Z')?'':'Z'));return d.toLocaleString([],{dateStyle:'medium',timeStyle:'short'});}
function md(t){
  if(!t)return'';
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>').replace(/^## (.+)$/gm,'<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\[BREAKING\]/g,'<span class="tag tag-red">[BREAKING]</span>')
    .replace(/\[IMPORTANT\]/g,'<span class="tag tag-yellow">[IMPORTANT]</span>')
    .replace(/^- (.+)$/gm,'<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>\n?)+/g,m=>'<ul>'+m+'</ul>');
}
function showToast(msg,type='info'){
  const el=document.getElementById('toast');el.textContent=msg;
  el.className='show '+(type==='error'?'error':type==='success'?'success':'');
  setTimeout(()=>el.className='',3500);
}
init();
</script>
</body>
</html>"""

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("newsfeeder:app", host=HOST, port=PORT, reload=False)
