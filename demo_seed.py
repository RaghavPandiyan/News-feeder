"""Demo data injector — seeds the DB with sample articles and a digest for testing."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
from summarizer import _fallback_summary, CATEGORY_LABELS

SAMPLE_ARTICLES = [
    # World
    {"url": "https://bbc.com/1", "title": "UN Security Council Meets Over Gaza Ceasefire Proposals", "source": "BBC World", "category": "world", "published": ""},
    {"url": "https://reuters.com/1", "title": "Ukraine Front Lines Shift as NATO Members Expand Military Aid", "source": "Reuters", "category": "world", "published": ""},
    {"url": "https://aljazeera.com/1", "title": "Sudan Civil War Enters New Phase as RSF Advances on Khartoum", "source": "Al Jazeera", "category": "world", "published": ""},
    {"url": "https://ap.com/1", "title": "G7 Leaders Agree on New Framework to Counter China's Economic Influence", "source": "AP News", "category": "world", "published": ""},
    {"url": "https://bbc.com/2", "title": "Red Sea Shipping Crisis Deepens as Houthi Attacks Intensify", "source": "BBC World", "category": "world", "published": ""},
    # Geopolitics
    {"url": "https://fp.com/1", "title": "[BREAKING] US-China Relations Hit New Low Over Taiwan Strait Incident", "source": "Foreign Policy", "category": "geopolitics", "published": ""},
    {"url": "https://diplomat.com/1", "title": "South China Sea: Philippines and China Clash Over Scarborough Shoal", "source": "The Diplomat", "category": "geopolitics", "published": ""},
    {"url": "https://fp.com/2", "title": "BRICS Expansion: Impact on Dollar Dominance and Global Trade Routes", "source": "Foreign Policy", "category": "geopolitics", "published": ""},
    {"url": "https://diplomat.com/2", "title": "India's Strategic Pivot: Balancing US Alliance and Russia Energy Ties", "source": "The Diplomat", "category": "geopolitics", "published": ""},
    {"url": "https://fp.com/3", "title": "Arctic Race Intensifies as Russia Expands Military Presence", "source": "Foreign Policy", "category": "geopolitics", "published": ""},
    # Tamil Nadu
    {"url": "https://thehindu.com/tn/1", "title": "Chennai Metro Phase 2 Construction Accelerates, Completion by 2027", "source": "The Hindu TN", "category": "tamil_nadu", "published": ""},
    {"url": "https://thehindu.com/tn/2", "title": "Tamil Nadu Government Launches New IT Policy to Attract $10B Investment", "source": "The Hindu TN", "category": "tamil_nadu", "published": ""},
    {"url": "https://ndtv.com/tn/1", "title": "Cyclone Alert: Bay of Bengal Depression to Hit TN Coast, Red Warning Issued", "source": "NDTV Tamil Nadu", "category": "tamil_nadu", "published": ""},
    {"url": "https://toi.com/tn/1", "title": "TN Elections 2026: DMK vs AIADMK Pre-poll Survey Shows Tight Race", "source": "Times of India TN", "category": "tamil_nadu", "published": ""},
    {"url": "https://thehindu.com/tn/3", "title": "Jallikattu Season Opens in Madurai Amid Tight Security", "source": "The Hindu TN", "category": "tamil_nadu", "published": ""},
    # Tech
    {"url": "https://techcrunch.com/1", "title": "OpenAI Releases GPT-5 with Multimodal Reasoning Capabilities", "source": "TechCrunch", "category": "tech", "published": ""},
    {"url": "https://theverge.com/1", "title": "Apple Vision Pro 2: Lighter, Cheaper, Ships Q3 2025", "source": "The Verge", "category": "tech", "published": ""},
    {"url": "https://hn.com/1", "title": "Show HN: I built a local LLM that runs on Raspberry Pi 5", "source": "Hacker News", "category": "tech", "published": ""},
    {"url": "https://wired.com/1", "title": "The AI Energy Crisis: Data Centers Now Consume More Power Than Many Countries", "source": "Wired", "category": "tech", "published": ""},
    {"url": "https://arstechnica.com/1", "title": "Nvidia Blackwell Ultra GPUs: 4x Performance Jump Over H100", "source": "Ars Technica", "category": "tech", "published": ""},
    # India
    {"url": "https://ndtv.com/in/1", "title": "[IMPORTANT] India GDP Growth Hits 8.2% in Q1, Beats All Estimates", "source": "NDTV India", "category": "india", "published": ""},
    {"url": "https://thehindu.com/in/1", "title": "Supreme Court Verdict on Electoral Bonds: Parties Must Disclose Donors", "source": "The Hindu India", "category": "india", "published": ""},
    {"url": "https://ie.com/1", "title": "India Launches New Semiconductor Fab in Pune with $3B Investment", "source": "Indian Express", "category": "india", "published": ""},
    {"url": "https://ndtv.com/in/2", "title": "Heat Wave Grips North India, Temperatures Exceed 48°C in Rajasthan", "source": "NDTV India", "category": "india", "published": ""},
    # Business
    {"url": "https://bbc.com/biz/1", "title": "Federal Reserve Signals Rate Cut Pause Amid Sticky Inflation Data", "source": "BBC Business", "category": "business", "published": ""},
    {"url": "https://bbc.com/biz/2", "title": "Oil Prices Surge 5% on Middle East Supply Disruption Fears", "source": "BBC Business", "category": "business", "published": ""},
    {"url": "https://reddit.com/r/economics/1", "title": "Global Debt Hits Record $315 Trillion — What It Means for Emerging Markets", "source": "r/economics", "category": "business", "published": ""},
]

SAMPLE_DIGEST = """## World News
- [Reuters] Ukraine front lines are shifting as NATO member states significantly expand their military aid packages, with Germany and UK pledging additional Patriot systems.
- [BBC World] The UN Security Council held emergency talks on Gaza ceasefire proposals; the US vetoed the latest draft resolution citing "implementation gaps."
- [Al Jazeera] Sudan's RSF paramilitary forces have advanced to within 10km of Khartoum's city center, displacing an estimated 500,000 civilians this week.
- [BREAKING] Red Sea shipping crisis deepens — over 60% of container traffic has now rerouted around the Cape of Good Hope, adding 12–15 days to Europe-Asia routes.

## Geopolitics & International Relations
- [BREAKING] US-China tensions escalate following a near-collision between naval vessels in the Taiwan Strait; both sides have summoned ambassadors.
- [Foreign Policy] The Philippines and China clashed physically at Scarborough Shoal, with Chinese coast guard water cannons disabling Philippine supply boats — the most serious incident in 2025.
- [The Diplomat] India is navigating a delicate balancing act: deepening the US-India Quad alliance while maintaining Russian energy imports banned by Western nations.
- [Foreign Policy] BRICS+ now represents 45% of global GDP by PPP — new analysis suggests a BRICS payment system could reduce dollar-denominated trade by $2T/year by 2030.

## Tamil Nadu & Local
- [NDTV TN] [IMPORTANT] Cyclone alert issued for Tamil Nadu coast — a Bay of Bengal depression is expected to intensify into a severe cyclonic storm, making landfall near Nagapattinam by Friday.
- [The Hindu TN] Tamil Nadu's new IT policy targets $10 billion in investment over 5 years, offering land subsidies and tax breaks for semiconductor and AI companies.
- [The Hindu TN] Chennai Metro Phase 2 construction is ahead of schedule; 12 new stations connecting Sholinganallur to Siruseri expected by late 2027.
- [ToI TN] Pre-poll survey for TN 2026 elections shows DMK leading with 42% vote share vs AIADMK at 38%, but 20% undecided.

## Technology & Science
- [TechCrunch] OpenAI's GPT-5 launches with native multimodal reasoning — early benchmarks show it outperforms GPT-4o by 40% on complex math and coding tasks.
- [Wired] AI data center power consumption has surpassed that of France — researchers warn the AI energy footprint could double by 2027 without hardware breakthroughs.
- [Hacker News] Standout community project: A developer built a fully local LLM running on Raspberry Pi 5 using quantized Phi-3 Mini — 15 tokens/sec performance.
- [Ars Technica] Nvidia Blackwell Ultra GPU benchmarks leaked — 4x inference performance over H100, targeted at large language model training at scale.

## India
- [IMPORTANT] India's Q1 GDP growth hits 8.2%, beating analyst estimates of 7.6% — driven by manufacturing (12% growth) and services exports.
- [The Hindu] Supreme Court rules electoral bonds scheme unconstitutional; political parties must disclose all donor names within 60 days.
- [Indian Express] India's first domestic semiconductor fab breaks ground in Pune — a ₹25,000 crore joint venture with TATA and international partners.

## Business & Economy
- [BBC Business] The Federal Reserve held rates steady and signaled fewer cuts in 2025 as core PCE inflation remains at 3.1%, above the 2% target.
- [BBC Business] Brent crude jumped 5.2% on fears of supply disruption following the Red Sea crisis and new OPEC+ production discipline.

---
**Big Picture:** The world is navigating converging crises — geopolitical flashpoints in Taiwan, Gaza, and Sudan are reshaping global supply chains, while the AI energy boom is creating new economic pressures. India stands at an inflection point, posting strong growth numbers while managing both the US-China rivalry and a domestic election cycle that will determine its economic policy direction for the next five years."""


async def seed_demo():
    db.init_db()

    # Save articles
    db.save_articles(SAMPLE_ARTICLES)

    # Build categories meta
    from collections import defaultdict
    by_cat = defaultdict(list)
    for a in SAMPLE_ARTICLES:
        by_cat[a["category"]].append(a)

    categories_meta = {
        cat: {"count": len(arts), "label": CATEGORY_LABELS.get(cat, cat.title())}
        for cat, arts in by_cat.items()
    }

    # Save a few digest slots
    slots = ["8:00 AM", "10:00 AM", "12:00 PM"]
    for slot in slots:
        db.save_digest(slot, SAMPLE_DIGEST, categories_meta, len(SAMPLE_ARTICLES))

    print(f"Demo data seeded: {len(SAMPLE_ARTICLES)} articles, {len(slots)} digests")


if __name__ == "__main__":
    asyncio.run(seed_demo())
