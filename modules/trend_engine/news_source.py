"""
News Source — Fetch from NewsData.io if API key exists.
Returns empty list safely if no key.
"""

import requests
from datetime import datetime
from config.settings import NEWSDATA_API_KEY

NEWSDATA_URL = "https://newsdata.io/api/1/latest"

QUERIES = [
    {"q": "real estate market growth", "category": "business"},
    {"q": "tourism hospitality booking", "category": "tourism"},
    {"q": "digital transformation AI", "category": "technology"},
    {"q": "healthcare clinic expansion", "category": "health"},
    {"q": "ecommerce online retail", "category": "business"},
]

COUNTRY_MAP = {
    "ae": "UAE", "in": "India", "sa": "Saudi Arabia",
    "gb": "UK", "us": "USA", "au": "Australia",
    "ca": "Canada", "sg": "Singapore", "qa": "Qatar",
}

CITY_LIST = [
    "Dubai", "Riyadh", "Jeddah", "Mumbai", "Delhi", "London",
    "New York", "Sydney", "Toronto", "Singapore", "Doha",
    "Abu Dhabi", "Bengaluru", "Chennai", "Pune",
]


def fetch_news_data() -> list[dict]:
    """Fetch from NewsData.io. Returns empty list if no API key."""
    if not NEWSDATA_API_KEY:
        print("[NewsData] No API key — skipping")
        return []

    signals = []
    seen_urls = set()

    for query in QUERIES:
        try:
            params = {
                "apikey": NEWSDATA_API_KEY,
                "q": query["q"],
                "country": "ae,in,sa,gb,us,au,ca,sg,qa",
                "language": "en",
                "size": 10,
            }
            if query.get("category"):
                params["category"] = query["category"]

            resp = requests.get(NEWSDATA_URL, params=params, timeout=12)
            if resp.status_code == 401:
                print("[NewsData] Invalid API key")
                return []
            if resp.status_code == 429:
                print("[NewsData] Rate limited")
                break
            if resp.status_code != 200:
                continue

            for article in resp.json().get("results", []) or []:
                url = article.get("link", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title = article.get("title", "")
                if not title:
                    continue

                # Determine country
                country = ""
                codes = article.get("country", [])
                if codes:
                    code = codes[0].lower() if isinstance(codes, list) else str(codes).lower()
                    country = COUNTRY_MAP.get(code, code.upper())

                # Detect region
                region = ""
                combined = title + " " + (article.get("description", "") or "")
                for city in CITY_LIST:
                    if city.lower() in combined.lower():
                        region = city
                        break

                # Parse date
                pub = article.get("pubDate", "")
                published_at = ""
                if pub:
                    try:
                        published_at = datetime.strptime(pub, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        published_at = pub

                signals.append({
                    "source_name": "NewsData",
                    "source_type": "news",
                    "title": title,
                    "url": url,
                    "raw_text": (article.get("description") or title)[:1500],
                    "country": country,
                    "region": region,
                    "keyword": query["q"],
                    "published_at": published_at,
                })

        except requests.exceptions.RequestException:
            continue
        except Exception:
            continue

    print(f"[NewsData] Fetched {len(signals)} signals")
    return signals
