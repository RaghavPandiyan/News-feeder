import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

import db
import config
from scheduler import get_scheduler, trigger_now


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    scheduler = get_scheduler()
    scheduler.start()
    print(f"[Main] News Feeder started. Scheduler running with timezone: {config.TIMEZONE}")
    print(f"[Main] Scheduled slots: {config.SCHEDULE_HOURS}")
    yield
    scheduler.shutdown(wait=False)
    print("[Main] Scheduler stopped.")


app = FastAPI(title="News Feeder", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")


@app.get("/api/latest")
async def api_latest():
    digest = db.get_latest_digest()
    if not digest:
        return {"digest": None, "message": "No digest yet. Click 'Fetch Now' or wait for the next scheduled slot."}
    return {"digest": digest}


@app.get("/api/history")
async def api_history(limit: int = 20):
    return {"history": db.get_digest_history(limit)}


@app.get("/api/articles")
async def api_articles(hours: int = 3, limit: int = 100):
    return {"articles": db.get_recent_articles(hours=hours, limit=limit)}


@app.post("/api/fetch-now")
async def api_fetch_now():
    """Manually trigger a fetch + summarize cycle."""
    try:
        now = datetime.now()
        label = f"Manual {now.strftime('%I:%M %p')}"

        from fetchers.rss import fetch_all_rss
        from fetchers.hackernews import fetch_hackernews
        from fetchers.reddit import fetch_reddit
        from fetchers.newsapi import fetch_newsapi
        from summarizer import generate_digest

        results = await asyncio.gather(
            fetch_all_rss(),
            fetch_hackernews(),
            fetch_reddit(),
            fetch_newsapi(),
            return_exceptions=True,
        )
        digest = await generate_digest(label)
        return {"status": "ok", "digest": digest}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/schedule")
async def api_schedule():
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
        })
    return {"timezone": config.TIMEZONE, "jobs": jobs}


@app.get("/api/status")
async def api_status():
    scheduler = get_scheduler()
    digest = db.get_latest_digest()
    return {
        "running": scheduler.running,
        "timezone": config.TIMEZONE,
        "schedule_hours": config.SCHEDULE_HOURS,
        "ai_enabled": bool(config.ANTHROPIC_API_KEY),
        "last_digest_at": digest["created_at"] if digest else None,
        "sources": {
            "rss": True,
            "hackernews": True,
            "reddit": True,
            "newsapi": bool(config.NEWS_API_KEY),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
