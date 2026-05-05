from playwright.sync_api import sync_playwright
import time
from modules.scraping.base_scraper import BaseScraper
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class GoogleMapsScraper(BaseScraper):
    def scrape(self, query: str, limit: int = None, location: str = None, should_stop=None):
        """
        Scrapes Google Maps for the given query.
        If limit is None, scrapes all available results.
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
                
                # Phase 1: Loading results
                logger.info(f"Phase 1: Loading results for '{search_query}'...")
                scrollable_div = page.locator('div[role="feed"]')
                previous_count = 0
                no_new_results_count = 0
                max_retries = 3  # Stop after 3 consecutive scroll attempts with no new results
                
                while True:
                    if should_stop and should_stop():
                        logger.info("Scrape stopped by user.")
                        break
                        
                    # Get current cards
                    cards = page.locator('a[href*="https://www.google.com/maps/place/"]').all()
                    current_count = len(cards)
                    
                    # Log scroll progress occasionally
                    if current_count % 20 == 0 and current_count != previous_count:
                        logger.info(f"Loaded {current_count} businesses...")

                    # Check if we've reached the limit (if specified)
                    if limit is not None and current_count >= limit:
                        logger.info(f"Reached specified limit of {limit} results")
                        break
                    
                    if current_count == previous_count:
                        # No new results loaded
                        no_new_results_count += 1
                        if no_new_results_count >= max_retries:
                            logger.info(f"No more results available. Total loaded: {current_count}")
                            break
                        
                        # Try to scroll down to load more
                        scrollable_div.hover()
                        page.mouse.wheel(0, 1000)
                        time.sleep(2)
                    else:
                        # New results loaded, reset retry counter
                        no_new_results_count = 0
                        previous_count = current_count
                        
                        # Continue scrolling to load more
                        scrollable_div.hover()
                        page.mouse.wheel(0, 1000)
                        time.sleep(1.5)
                
                # Phase 2: Extracting data from all loaded cards
                cards = page.locator('a[href*="https://www.google.com/maps/place/"]').all()
                cards_to_process = cards[:limit] if limit is not None else cards
                total_to_process = len(cards_to_process)
                
                logger.info(f"Phase 2: Extracting data from {total_to_process} businesses...")
                
                for idx, card in enumerate(cards_to_process, 1):
                    if should_stop and should_stop():
                        logger.info("Scrape stopped by user during details extraction.")
                        break
                        
                    try:
                        # Click the card to load details
                        card.click()
                        time.sleep(2)  # Wait for details to load
                        
                        business_name = ""
                        try:
                            # Use multiple selectors for business name as Google Maps UI varies
                            name_selectors = ['h1.DUwDvf', 'h1.fontHeadlineLarge']
                            for selector in name_selectors:
                                try:
                                    business_name = page.locator(selector).inner_text(timeout=2000)
                                    if business_name: break
                                except: continue
                        except:
                            logger.warning(f"Card {idx}/{total_to_process}: No business name found, skipping")
                            continue  # Skip if no name
                            
                        address = ""
                        try:
                            address_button = page.locator('button[data-item-id="address"]')
                            if address_button.count() > 0:
                                address = address_button.inner_text().split("\n")[-1]
                        except:
                            pass
                            
                        phone = ""
                        try:
                            phone_button = page.locator('button[data-item-id*="phone:tel:"]')
                            if phone_button.count() > 0:
                                phone = phone_button.inner_text().split("\n")[-1]
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
                                # Format: "4.5\n(1,234)"
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
                            "email": None,  # Will be filled by website scraper
                            "website": website,
                            "address": address,
                            "rating": rating,
                            "reviews_count": reviews_count,
                            "source": "google_maps",
                            "google_maps_url": page.url,
                            "raw_data": {
                                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                        }
                        leads.append(lead_data)
                        logger.info(f"Scraped ({idx}/{total_to_process}): {business_name}")
                        
                    except Exception as e:
                        logger.error(f"Error extracting card {idx} details: {str(e)}")
                        
                browser.close()
                logger.info(f"Scraping completed. Total leads extracted: {len(leads)}")
                
        except Exception as e:
            logger.error(f"Google Maps scraper failed: {str(e)}")
            
        return leads