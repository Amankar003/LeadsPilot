"""
RSS Source — Fetch from curated RSS feeds using feedparser.
No API key required.
"""

import time
from datetime import datetime

RSS_FEEDS = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "sector": "ai digital transformation"},
    {"name": "Skift Travel", "url": "https://skift.com/feed/", "sector": "tourism"},
    {"name": "Healthcare IT News", "url": "https://www.healthcareitnews.com/feed", "sector": "healthcare"},
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "sector": "b2b services"},
    {"name": "Economic Times", "url": "https://economictimes.indiatimes.com/rssfeedsdefault.cms", "sector": "b2b services"},
    {"name": "Gulf News Business", "url": "https://gulfnews.com/business/rss", "sector": "b2b services"},
    {"name": "Practical Ecommerce", "url": "https://www.practicalecommerce.com/feed", "sector": "ecommerce"},
    {"name": "Industry Week", "url": "https://www.industryweek.com/rss.xml", "sector": "manufacturing"},
]

COUNTRY_KEYWORDS = {
    "UAE": ["uae", "dubai", "abu dhabi", "sharjah", "emirates"],
    "India": ["india", "mumbai", "delhi", "bengaluru", "chennai", "pune", "jaipur", "ayodhya", "noida", "gurugram"],
    "Saudi Arabia": ["saudi", "riyadh", "jeddah", "neom", "vision 2030"],
    "UK": ["uk", "britain", "london", "manchester"],
    "USA": ["us", "usa", "america", "new york", "california"],
    "Australia": ["australia", "sydney", "melbourne", "brisbane"],
    "Canada": ["canada", "toronto", "vancouver"],
    "Singapore": ["singapore"],
    "Qatar": ["qatar", "doha"],
}

CITY_LIST = [
    "Dubai", "Abu Dhabi", "Riyadh", "Jeddah", "Mumbai", "Delhi",
    "Bengaluru", "Chennai", "Pune", "Jaipur", "London", "New York",
    "Sydney", "Melbourne", "Toronto", "Vancouver", "Singapore", "Doha",
]


def _detect_country(text: str) -> str:
    t = text.lower()
    for country, keywords in COUNTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                return country
    return ""


def _detect_region(text: str) -> str:
    t = text.lower()
    for city in CITY_LIST:
        if city.lower() in t:
            return city
    return ""


def fetch_rss_data() -> list[dict]:
    """Fetch from curated RSS feeds."""
    try:
        import feedparser
    except ImportError:
        print("[RSS] feedparser not installed — skipping")
        return []

    signals = []
    seen_urls = set()

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            if feed.bozo and not feed.entries:
                continue

            for entry in feed.entries[:6]:
                url = entry.get("link", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title = entry.get("title", "")
                if not title:
                    continue

                summary = entry.get("summary", "") or entry.get("description", "") or ""
                combined = f"{title} {summary}"

                # Parse date
                published_at = ""
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published_at = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
                    except (TypeError, ValueError):
                        pass

                signals.append({
                    "source_name": f"RSS:{feed_info['name']}",
                    "source_type": "rss",
                    "title": title,
                    "url": url,
                    "raw_text": summary[:1500] if summary else title,
                    "country": _detect_country(combined),
                    "region": _detect_region(combined),
                    "keyword": feed_info.get("sector", ""),
                    "published_at": published_at,
                })

        except Exception:
            continue

        time.sleep(0.3)

    print(f"[RSS] Fetched {len(signals)} signals from {len(RSS_FEEDS)} feeds")
    return signals
