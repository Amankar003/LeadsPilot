from modules.scraping.google_maps_scraper import GoogleMapsScraper

def get_scraper(platform: str):
    if platform == "google_maps":
        return GoogleMapsScraper()
    else:
        raise ValueError(f"Scraper for platform {platform} not implemented")
