"""
PyTrends Source — Fetch Google Trends demand signals.
Returns empty list safely if pytrends fails or is rate-limited.
"""

import random
import time
from datetime import datetime

from modules.trend_engine.constants import TARGET_COUNTRIES, SECTOR_KEYWORDS

COUNTRY_GEO = {
    "India": "IN", "UAE": "AE", "Saudi Arabia": "SA", "UK": "GB",
    "USA": "US", "Australia": "AU", "Canada": "CA", "Singapore": "SG", "Qatar": "QA",
}


def fetch_pytrends_data() -> list[dict]:
    """Fetch trending topics from Google Trends. Returns empty list on failure."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("[pytrends] Not installed — skipping")
        return []

    signals = []

    try:
        pytrends = TrendReq(hl="en-US", tz=330, timeout=(10, 25))
    except Exception as e:
        print(f"[pytrends] Init failed: {e}")
        return []

    # Sample to avoid rate limiting
    sectors = list(SECTOR_KEYWORDS.items())
    random.shuffle(sectors)
    countries = list(COUNTRY_GEO.items())
    random.shuffle(countries)

    for sector_name, keywords in sectors[:2]:
        for country_name, geo in countries[:2]:
            try:
                kw_list = keywords[:2]
                pytrends.build_payload(kw_list=kw_list, timeframe="now 7-d", geo=geo)
                df = pytrends.interest_over_time()

                if df is not None and not df.empty:
                    for kw in kw_list:
                        if kw in df.columns:
                            avg = int(df[kw].mean())
                            if avg >= 20:
                                signals.append({
                                    "source_name": "Google Trends",
                                    "source_type": "trends",
                                    "title": f"Trending: '{kw}' in {country_name} (interest: {avg}/100)",
                                    "url": f"https://trends.google.com/trends/explore?q={kw}&geo={geo}",
                                    "raw_text": f"Google Trends shows '{kw}' has {avg}/100 average interest in {country_name} over 7 days.",
                                    "country": country_name,
                                    "region": "",
                                    "keyword": kw,
                                    "published_at": datetime.utcnow().strftime("%Y-%m-%d"),
                                })

                time.sleep(random.uniform(2, 4))

            except Exception as e:
                if "429" in str(e).lower() or "rate" in str(e).lower():
                    print(f"[pytrends] Rate limited — stopping")
                    return signals
                time.sleep(random.uniform(3, 6))

    print(f"[pytrends] Fetched {len(signals)} signals")
    return signals
