from playwright.sync_api import sync_playwright
import time
from modules.scraping.base_scraper import BaseScraper
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class GoogleMapsScraper(BaseScraper):
    def scrape(self, query: str, limit: int, location: str = None):
        """
        Scrapes Google Maps for the given query.
        Returns a list of dictionaries with lead data.
        """
        leads = []
        search_query = f"{query} in {location}" if location else query
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                import urllib.parse
                encoded_query = urllib.parse.quote_plus(search_query)
                page.goto(f"https://www.google.com/maps/search/{encoded_query}")
                
                # Wait for results to load
                page.wait_for_selector('div[role="feed"]', timeout=15000)
                
                # Scroll to load results
                scrollable_div = page.locator('div[role="feed"]')
                previous_count = 0
                
                while len(leads) < limit:
                    # Get current cards
                    cards = page.locator('a[href*="https://www.google.com/maps/place/"]').all()
                    
                    if len(cards) == previous_count:
                        # Try to scroll down to load more
                        scrollable_div.hover()
                        page.mouse.wheel(0, 1000)
                        time.sleep(2)
                        cards = page.locator('a[href*="https://www.google.com/maps/place/"]').all()
                        if len(cards) == previous_count:
                            break # No more results
                            
                    previous_count = len(cards)
                    
                    for card in cards[len(leads):]:
                        if len(leads) >= limit:
                            break
                            
                        try:
                            # Click the card to load details
                            card.click()
                            time.sleep(2) # Wait for details to load
                            
                            business_name = ""
                            try:
                                business_name = page.locator('h1.DUwDvf').inner_text(timeout=2000)
                            except:
                                continue # Skip if no name
                                
                            address = ""
                            try:
                                address_button = page.locator('button[data-item-id="address"]')
                                if address_button.count() > 0:
                                    address = address_button.inner_text().split("\n")[1] if "\n" in address_button.inner_text() else address_button.inner_text()
                            except:
                                pass
                                
                            phone = ""
                            try:
                                phone_button = page.locator('button[data-item-id*="phone:tel:"]')
                                if phone_button.count() > 0:
                                    phone = phone_button.inner_text().split("\n")[1] if "\n" in phone_button.inner_text() else phone_button.inner_text()
                            except:
                                pass
                                
                            website = ""
                            try:
                                website_a = page.locator('a[data-item-id="authority"]')
                                if website_a.count() > 0:
                                    website = website_a.get_attribute('href')
                            except:
                                pass
                                
                            rating = ""
                            reviews_count = ""
                            try:
                                rating_div = page.locator('div.F7nice').first
                                if rating_div.count() > 0:
                                    rating_text = rating_div.inner_text()
                                    parts = rating_text.split("\n")
                                    if len(parts) > 0:
                                        rating = parts[0]
                                    if len(parts) > 1:
                                        reviews_count = parts[1].replace('(', '').replace(')', '')
                            except:
                                pass
                                
                            lead_data = {
                                "business_name": business_name,
                                "category": query,
                                "phone": phone,
                                "email": None, # Will be filled by website scraper
                                "website": website,
                                "address": address,
                                "rating": rating,
                                "reviews_count": reviews_count,
                                "source": "google_maps",
                                "google_maps_url": page.url,
                                "raw_data": {}
                            }
                            leads.append(lead_data)
                            logger.info(f"Scraped: {business_name}")
                            
                        except Exception as e:
                            logger.error(f"Error extracting card details: {str(e)}")
                            
                browser.close()
        except Exception as e:
            logger.error(f"Google Maps scraper failed: {str(e)}")
            
        return leads
