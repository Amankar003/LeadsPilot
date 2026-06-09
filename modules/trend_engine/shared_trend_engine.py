import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from modules.trend_engine.gdelt_source import fetch_gdelt_data
from modules.trend_engine.news_source import fetch_news_data
from modules.trend_engine.rss_source import fetch_rss_data
from modules.trend_engine.pytrends_source import fetch_pytrends_data
from modules.trend_engine.seed_source import fetch_seed_data

logger = logging.getLogger(__name__)

class SharedTrendEngine:
    _cache: List[Dict[str, Any]] = []
    _last_fetched: datetime = None
    _CACHE_DURATION = timedelta(hours=6)

    @classmethod
    def get_trends(cls, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetches trends from all sources, using a shared cache to avoid duplicate API calls.
        """
        if not force_refresh and cls._cache and cls._last_fetched:
            if datetime.now() - cls._last_fetched < cls._CACHE_DURATION:
                logger.info(f"Using cached trends. {len(cls._cache)} items available.")
                return cls._cache

        logger.info("Fetching fresh trends from all sources...")
        all_items = []
        
        try:
            gdelt_items = fetch_gdelt_data()
            all_items.extend(gdelt_items)
            logger.info(f"Fetched {len(gdelt_items)} from GDELT.")
        except Exception as e:
            logger.error(f"GDELT fetch failed: {e}")

        try:
            news_items = fetch_news_data()
            all_items.extend(news_items)
            logger.info(f"Fetched {len(news_items)} from NewsData.")
        except Exception as e:
            logger.error(f"NewsData fetch failed: {e}")

        try:
            rss_items = fetch_rss_data()
            all_items.extend(rss_items)
            logger.info(f"Fetched {len(rss_items)} from RSS.")
        except Exception as e:
            logger.error(f"RSS fetch failed: {e}")

        try:
            pytrends_items = fetch_pytrends_data()
            all_items.extend(pytrends_items)
            logger.info(f"Fetched {len(pytrends_items)} from PyTrends.")
        except Exception as e:
            logger.error(f"PyTrends fetch failed: {e}")

        # Fallback to seed data if live fetch totally fails or returns 0
        if not all_items:
            logger.warning("No live trends found from APIs! Using fallback seed data.")
            all_items = fetch_seed_data()
        
        # Deduplicate
        seen_urls = set()
        deduped_items = []
        for item in all_items:
            url = item.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped_items.append(item)
            elif not url:
                # Keep items without URLs
                deduped_items.append(item)
                
        cls._cache = deduped_items
        cls._last_fetched = datetime.now()
        
        logger.info(f"SharedTrendEngine fetched {len(cls._cache)} deduplicated trends total.")
        return cls._cache
