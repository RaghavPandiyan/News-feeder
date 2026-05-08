import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "news_feeder.db"


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
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT UNIQUE,
                title       TEXT,
                source      TEXT,
                category    TEXT,
                published   TEXT,
                fetched_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS digests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT DEFAULT (datetime('now')),
                slot_label  TEXT,
                summary     TEXT,
                categories  TEXT,
                article_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_articles_fetched ON articles(fetched_at);
            CREATE INDEX IF NOT EXISTS idx_digests_created ON digests(created_at);
        """)


def seen_urls(urls: list[str]) -> set[str]:
    if not urls:
        return set()
    with get_conn() as conn:
        placeholders = ",".join("?" * len(urls))
        rows = conn.execute(
            f"SELECT url FROM articles WHERE url IN ({placeholders})", urls
        ).fetchall()
    return {r["url"] for r in rows}


def save_articles(articles: list[dict]):
    if not articles:
        return
    with get_conn() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO articles (url, title, source, category, published)
               VALUES (:url, :title, :source, :category, :published)""",
            articles,
        )


def save_digest(slot_label: str, summary: str, categories: dict, article_count: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO digests (slot_label, summary, categories, article_count)
               VALUES (?, ?, ?, ?)""",
            (slot_label, summary, json.dumps(categories), article_count),
        )


def get_latest_digest() -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM digests ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["categories"] = json.loads(d["categories"] or "{}")
    return d


def get_digest_history(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM digests ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["categories"] = json.loads(d["categories"] or "{}")
        result.append(d)
    return result


def get_recent_articles(hours: int = 2, limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE fetched_at >= datetime('now', ?)
               ORDER BY fetched_at DESC LIMIT ?""",
            (f"-{hours} hours", limit),
        ).fetchall()
    return [dict(r) for r in rows]
