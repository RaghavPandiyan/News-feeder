import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "NewsFeeder/1.0")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# Schedule hours (24h format) — every 2 hours from 8am to 2am next day
SCHEDULE_HOURS = [8, 10, 12, 14, 16, 18, 20, 22, 0, 2]

# RSS feed sources — all free, no API key needed
RSS_FEEDS = {
    "world": [
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
        ("Google News World", "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en"),
    ],
    "geopolitics": [
        ("Foreign Policy", "https://foreignpolicy.com/feed/"),
        ("The Diplomat", "https://thediplomat.com/feed/"),
        ("Google News Geopolitics", "https://news.google.com/rss/search?q=geopolitics+international+relations&hl=en-US&gl=US&ceid=US:en"),
        ("NDTV World", "https://feeds.feedburner.com/ndtvnews-world-news"),
    ],
    "tamil_nadu": [
        ("The Hindu TN", "https://www.thehindu.com/news/national/tamil-nadu/feeder/default.rss"),
        ("Google News Tamil Nadu", "https://news.google.com/rss/search?q=Tamil+Nadu&hl=en-IN&gl=IN&ceid=IN:en"),
        ("NDTV Tamil Nadu", "https://feeds.feedburner.com/ndtv/state-Tamil-Nadu-news"),
        ("Times of India TN", "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms"),
    ],
    "tech": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("Wired", "https://www.wired.com/feed/rss"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ],
    "business": [
        ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("Google News Business", "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6Y0dFU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en"),
    ],
    "india": [
        ("The Hindu India", "https://www.thehindu.com/news/national/feeder/default.rss"),
        ("NDTV India", "https://feeds.feedburner.com/ndtvnews-india-news"),
        ("Indian Express", "https://indianexpress.com/feed/"),
        ("Google News India", "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGx1YlY4U0FtVnVLQUFQAQ?hl=en-IN&gl=IN&ceid=IN:en"),
    ],
}

# Reddit subreddits (read-only, no key needed with PRAW public access)
REDDIT_SUBS = [
    "worldnews",
    "geopolitics",
    "india",
    "technology",
    "science",
    "economics",
    "TamilNadu",
]

# HackerNews: top stories count
HN_STORIES_COUNT = 20
