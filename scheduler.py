import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from fetchers.rss import fetch_all_rss
from fetchers.hackernews import fetch_hackernews
from fetchers.reddit import fetch_reddit
from fetchers.newsapi import fetch_newsapi
from summarizer import generate_digest

_scheduler: AsyncIOScheduler | None = None


def _slot_label(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    h = hour if hour <= 12 else hour - 12
    h = 12 if h == 0 else h
    return f"{h}:00 {suffix}"


async def run_fetch_and_summarize(hour: int):
    label = _slot_label(hour)
    print(f"\n{'='*50}")
    print(f"[Scheduler] Starting fetch for {label} slot — {datetime.now().isoformat()}")
    print(f"{'='*50}")

    # Run all fetchers concurrently
    results = await asyncio.gather(
        fetch_all_rss(),
        fetch_hackernews(),
        fetch_reddit(),
        fetch_newsapi(),
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, Exception):
            print(f"[Scheduler] Fetcher error: {r}")

    # Summarize everything collected in the last ~3 hours
    await generate_digest(label)
    print(f"[Scheduler] Done for {label} slot.\n")


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

    for hour in config.SCHEDULE_HOURS:
        _scheduler.add_job(
            run_fetch_and_summarize,
            trigger=CronTrigger(hour=hour, minute=0, timezone=config.TIMEZONE),
            args=[hour],
            id=f"digest_{hour:02d}00",
            name=f"News digest at {_slot_label(hour)}",
            replace_existing=True,
            misfire_grace_time=300,  # 5 min grace if server was briefly down
        )

    return _scheduler


async def trigger_now():
    """Manual trigger for on-demand fetch — used by the API."""
    now = datetime.now()
    hour = now.hour
    await run_fetch_and_summarize(hour)
