from modules.scraping.google_maps_scraper import GoogleMapsScraper
from modules.scraping.google_email_scraper import GoogleEmailScraper

from utils.constants import (
    PLATFORM_GOOGLE_MAPS,
    PLATFORM_GOOGLE_EMAIL,
    PLATFORM_SERPER_BULK,
)
from utils.logging_utils import get_logger

logger = get_logger(__name__)


def get_scraper(platform: str):
    if platform == PLATFORM_GOOGLE_MAPS:
        logger.info("Using GoogleMapsScraper")
        return GoogleMapsScraper()

    elif platform == PLATFORM_GOOGLE_EMAIL:
        logger.info("Using GoogleEmailScraper")
        return GoogleEmailScraper()

    elif platform == PLATFORM_SERPER_BULK:
        # Handled manually in ScrapingPlanner
        return None

    else:
        raise ValueError(f"Scraper for platform '{platform}' is not implemented")