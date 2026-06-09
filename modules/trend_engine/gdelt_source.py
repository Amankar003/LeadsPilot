"""
GDELT Source — Fetch global news signals from GDELT DOC 2.0 API.
Free, no API key needed.
"""

import random
import requests
from urllib.parse import quote
from datetime import datetime

from modules.trend_engine.constants import TARGET_COUNTRIES, SECTOR_KEYWORDS

GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"

CITY_LIST = [
    "Dubai", "Riyadh", "Jeddah", "Mumbai", "Delhi", "London",
    "New York", "Sydney", "Toronto", "Singapore", "Doha",
    "Abu Dhabi", "Bengaluru", "Chennai", "Pune", "Jaipur",
    "Noida", "Gurugram", "Melbourne", "Vancouver",
]


def fetch_gdelt_data() -> list[dict]:
    """Fetch latest signals from GDELT. Returns list of source dicts."""
    signals = []
    seen_urls = set()

    # Sample to avoid hammering API
    countries = random.sample(TARGET_COUNTRIES, min(4, len(TARGET_COUNTRIES)))
    sectors = list(SECTOR_KEYWORDS.items())
    random.shuffle(sectors)

    for sector_name, keywords in sectors[:4]:
        keyword = random.choice(keywords)
        for country in countries[:3]:
            try:
                query = f'"{keyword}" "{country}"'
                url = f"{GDELT_API}?query={quote(query)}&mode=ArtList&maxrecords=8&timespan=3d&format=json&sort=DateDesc"
                resp = requests.get(url, timeout=12)
                if resp.status_code != 200:
                    continue

                articles = resp.json().get("articles", [])
                for art in articles[:5]:
                    art_url = art.get("url", "")
                    if art_url in seen_urls:
                        continue
                    seen_urls.add(art_url)

                    title = art.get("title", "")
                    if not title:
                        continue

                    # Parse GDELT date
                    pub_date = art.get("seendate", "")
                    published_at = ""
                    if pub_date:
                        try:
                            published_at = datetime.strptime(pub_date[:15], "%Y%m%dT%H%M%S").strftime("%Y-%m-%d")
                        except (ValueError, IndexError):
                            published_at = pub_date

                    # Detect region from title
                    region = ""
                    for city in CITY_LIST:
                        if city.lower() in title.lower():
                            region = city
                            break

                    signals.append({
                        "source_name": "GDELT",
                        "source_type": "news",
                        "title": title,
                        "url": art_url,
                        "raw_text": title,
                        "country": country,
                        "region": region,
                        "keyword": keyword,
                        "published_at": published_at,
                    })

            except requests.exceptions.RequestException:
                continue
            except Exception:
                continue

    print(f"[GDELT] Fetched {len(signals)} signals")
    return signals
