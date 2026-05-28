import re
import time
import random
import logging
import urllib.parse
from datetime import datetime
from utils.logging_utils import get_logger
from utils.hash_utils import generate_lead_hash
from selenium.webdriver.common.by import By

logger = get_logger(__name__)

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

EMAIL_BLACKLIST = {
    "example@example.com", "user@example.com",
    "email@email.com", "name@domain.com",
    "your@email.com", "info@example.com",
    "test@test.com", "noreply@example.com",
    "no-reply@example.com", "donotreply@example.com",
    "privacy@google.com", "abuse@google.com",
}

BLACKLIST_DOMAINS = {
    "sentry.io", "wixpress.com", "example.com",
    "yoursite.com", "domain.com", "google.com"
}

class GoogleEmailScraper:
    """
    Scraper that harvests leads (emails/phones) from Google Search Results.
    Note: Direct Google SERP scraping is unstable for high-volume production.
    Consider using SerpAPI, ScraperAPI, or ZenRows for better reliability.
    """
    
    def __init__(
        self,
        max_pages=2,  # Default to 1 to reduce blocking risk
        results_per_page=10,
        max_retries=2,
        delay_min=6.0,   # Minimum wait after page load
        delay_max=12.0,  # Maximum wait after page load
        headless=False   # Always run visible for manual CAPTCHA solving
    ):
        self.max_pages = max_pages
        self.results_per_page = results_per_page
        self.max_retries = max_retries
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.headless = False  # Force False for manual CAPTCHA
        self._driver = None

    def _normalize_search_query(self, query: str) -> str:
        """
        Convert complex queries into natural-looking search terms.
        E.g. '"London" Plumbers site:facebook.com' -> 'London Plumbers Facebook'
        """
        # Remove site: searches and replace with names
        query = query.replace("site:facebook.com", "Facebook")
        query = query.replace("site:instagram.com", "Instagram")
        query = query.replace("site:linkedin.com", "LinkedIn")
        query = query.replace("site:twitter.com", "Twitter")
        
        # Remove quotes
        query = query.replace('"', '').replace("'", "")
        
        # Remove extra spaces
        query = " ".join(query.split())
        return query

    def _create_driver(self):
        """Create a fresh undetected-chromedriver instance with stable options."""
        try:
            import undetected_chromedriver as uc
            
            opts = uc.ChromeOptions()
            
            # Google SERP scraping MUST be visible for manual CAPTCHA resolution
            if self.headless:
                # We log a warning if someone tried to set headless=True
                logger.warning("Headless mode disabled for Google SERP scraping to allow manual CAPTCHA solving.")
            
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--window-size=1280,900")
            opts.add_argument("--start-maximized")
            opts.add_argument("--lang=en-US,en")
            
            # NOTE: Images are ENABLED (we do not add preference 2) 
            # to ensure ReCAPTCHA image challenges load properly.
            
            driver = uc.Chrome(options=opts)
            driver.set_page_load_timeout(60)
            
            return driver

        except Exception as e:
            error_msg = str(e)
            # Handle Chrome version mismatch if detected in logs
            if "Current browser version is" in error_msg:
                match = re.search(r"Current browser version is (\d+)", error_msg)
                if match:
                    version = int(match.group(1))
                    logger.info(f"Retrying undetected-chromedriver with version_main={version}")
                    import undetected_chromedriver as uc
                    retry_opts = uc.ChromeOptions()
                    retry_opts.add_argument("--no-sandbox")
                    retry_opts.add_argument("--disable-dev-shm-usage")
                    retry_opts.add_argument("--window-size=1280,900")
                    retry_opts.add_argument("--start-maximized")
                    retry_opts.add_argument("--lang=en-US,en")
                    
                    return uc.Chrome(options=retry_opts, version_main=version)
            
            logger.error(f"Failed to initialize driver: {e}")
            return None

    def _is_captcha_page(self, page_source: str, current_url: str = "") -> bool:
        """Detect if Google is showing a CAPTCHA or 'Unusual Traffic' page."""
        if "google.com/sorry" in current_url or "/sorry/index" in current_url:
            return True
            
        indicators = [
            "Our systems have detected unusual traffic",
            "recaptcha",
            "g-recaptcha",
            "captcha",
            "I'm not a robot",
            "detected unusual traffic from your computer network"
        ]
        lower_source = page_source.lower()
        return any(ind.lower() in lower_source for ind in indicators)

    def extract_emails_from_text(self, text: str) -> set:
        if not text:
            return set()
        found = set(EMAIL_REGEX.findall(text))
        return {e for e in found if e.lower() not in EMAIL_BLACKLIST and not any(d in e.lower() for d in BLACKLIST_DOMAINS)}

    def extract_phones_from_text(self, text: str) -> set:
        """Extract UK phone numbers using regex."""
        PHONE_REGEX = re.compile(
            r"(?:(?:\+44\s?|0044\s?|0)(?:[123789]\d\s?\d{3,4}\s?\d{4}|\d{2}\s?\d{4}\s?\d{4}))",
            re.IGNORECASE
        )
        if not text:
            return set()
        return set(PHONE_REGEX.findall(text))

    def _google_url(self, query: str, page: int) -> str:
        start = page * self.results_per_page
        encoded_query = urllib.parse.quote_plus(query)
        return f"https://www.google.com/search?q={encoded_query}&start={start}&hl=en"

    def _has_next_page(self) -> bool:
        try:
            nexts = self._driver.find_elements(By.ID, "pnnext")
            if nexts:
                return True
            nexts = self._driver.find_elements(By.CSS_SELECTOR, "a[aria-label='Next page']")
            return bool(nexts)
        except:
            return False

    def scrape(self, query: str, location: str = "", limit: int = 0, should_stop=None):
        """
        Main scraping generator. Yields lead objects.
        """
        # 1. Normalize Search Query
        original_query = f"{query} in {location}" if location else query
        search_query = self._normalize_search_query(original_query)
        
        found_contacts = set()
        yielded_count = 0
        page_idx = 0

        self._driver = self._create_driver()
        if not self._driver:
            logger.error("Could not start browser driver.")
            return

        try:
            while page_idx < self.max_pages:
                if should_stop and should_stop():
                    logger.info("Scrape stopped by user.")
                    break

                if limit and limit > 0 and yielded_count >= limit:
                    break

                google_url = self._google_url(search_query, page_idx)
                logger.info(f"Scraping Google Page {page_idx + 1}... ({google_url})")

                try:
                    self._driver.get(google_url)
                    # 4. Cooldown after page load
                    time.sleep(random.uniform(self.delay_min, self.delay_max))

                    # 2. Manual CAPTCHA Handling
                    if self._is_captcha_page(self._driver.page_source, self._driver.current_url):
                        logger.warning("CAPTCHA detected. Please solve it manually in the opened Chrome browser!")
                        
                        start_wait = time.time()
                        solved = False
                        while time.time() - start_wait < 180: # Wait up to 180 seconds
                            if should_stop and should_stop():
                                break
                            
                            time.sleep(3)
                            if not self._is_captcha_page(self._driver.page_source, self._driver.current_url):
                                logger.info("CAPTCHA solved! Continuing scrape...")
                                solved = True
                                break
                        
                        if not solved:
                            logger.error("CAPTCHA not solved within 180 seconds. Stopping scraper gracefully.")
                            return # Graceful exit from generator

                    # Parse snippets first
                    try:
                        snippets = self._driver.find_elements(By.CSS_SELECTOR, "div.g")
                        if not snippets:
                            logger.warning(f"No result snippets found on Google Page {page_idx + 1}.")
                        
                        new_serp_leads = 0
                        for snippet in snippets:
                            try:
                                title_element = snippet.find_element(By.TAG_NAME, "h3")
                                title = title_element.text.strip()
                                if not title: continue
                                
                                snippet_text = snippet.text
                                snippet_emails = self.extract_emails_from_text(snippet_text)
                                snippet_phones = self.extract_phones_from_text(snippet_text)
                                
                                try:
                                    link_element = snippet.find_element(By.CSS_SELECTOR, "a[href]")
                                    source_url = link_element.get_attribute("href")
                                except:
                                    source_url = google_url

                                # Yield snippet leads
                                for email in snippet_emails:
                                    if email not in found_contacts:
                                        found_contacts.add(email)
                                        yield {
                                            "business_name": title, "category": query,
                                            "email": email, "phone": None, "source": "google_email_search",
                                            "google_maps_url": source_url, "email_source": "serp_snippet",
                                            "email_confidence": "medium", "lead_hash": generate_lead_hash(
                                                business_name=title, email=email, website=source_url, location=query
                                            ),
                                            "raw_data": { "name": title, "source_url": source_url, "serp_page": page_idx + 1, "search_term": search_query }
                                        }
                                        yielded_count += 1
                                        new_serp_leads += 1

                                for phone in snippet_phones:
                                    if phone not in found_contacts:
                                        found_contacts.add(phone)
                                        yield {
                                            "business_name": title, "category": query,
                                            "email": None, "phone": phone, "source": "google_email_search",
                                            "google_maps_url": source_url, "email_source": None,
                                            "email_confidence": None, "lead_hash": generate_lead_hash(
                                                business_name=title, phone=phone, website=source_url, location=query
                                            ),
                                            "raw_data": { "name": title, "source_url": source_url, "serp_page": page_idx + 1, "search_term": search_query }
                                        }
                                        yielded_count += 1
                                        new_serp_leads += 1
                            except:
                                continue
                        
                        if new_serp_leads:
                            logger.info(f"Found {new_serp_leads} contacts in Google snippets on page {page_idx + 1}")
                    except Exception as e:
                        logger.debug(f"Snippet parsing error: {e}")

                    # Optionally visit links for deeper extraction
                    urls_to_visit = []
                    try:
                        links = self._driver.find_elements(By.CSS_SELECTOR, "div.g a[href]")
                        for link in links:
                            href = link.get_attribute("href")
                            if href and "google.com" not in href and "youtube.com" not in href:
                                if href not in urls_to_visit: urls_to_visit.append(href)
                    except: pass

                    for target_url in urls_to_visit:
                        if should_stop and should_stop(): break
                        if limit and limit > 0 and yielded_count >= limit: break

                        try:
                            logger.info(f"Visiting result for deep extraction: {target_url}")
                            self._driver.get(target_url)
                            time.sleep(3) # Small wait for site load
                            
                            page_source = self._driver.page_source
                            page_emails = self.extract_emails_from_text(page_source)
                            page_phones = self.extract_phones_from_text(page_source)

                            if page_emails or page_phones:
                                try:
                                    raw_title = self._driver.title
                                    b_name = raw_title.split('-')[0].split('|')[0].strip()
                                    if not b_name: b_name = urllib.parse.urlparse(target_url).netloc.replace('www.', '')
                                except:
                                    b_name = urllib.parse.urlparse(target_url).netloc.replace('www.', '')

                                for email in page_emails:
                                    if email not in found_contacts:
                                        found_contacts.add(email)
                                        yield {
                                            "business_name": b_name, "category": query,
                                            "email": email, "phone": None, "source": "google_email_search",
                                            "google_maps_url": target_url, "email_source": "site_visit",
                                            "email_confidence": "high", "lead_hash": generate_lead_hash(
                                                business_name=b_name, email=email, website=target_url, location=query
                                            ),
                                            "raw_data": { "name": b_name, "source_url": target_url, "serp_page": page_idx + 1, "search_term": search_query }
                                        }
                                        yielded_count += 1
                                        
                                for phone in page_phones:
                                    if phone not in found_contacts:
                                        found_contacts.add(phone)
                                        yield {
                                            "business_name": b_name, "category": query,
                                            "email": None, "phone": phone, "source": "google_email_search",
                                            "google_maps_url": target_url, "email_source": None,
                                            "email_confidence": None, "lead_hash": generate_lead_hash(
                                                business_name=b_name, phone=phone, website=target_url, location=query
                                            ),
                                            "raw_data": { "name": b_name, "source_url": target_url, "serp_page": page_idx + 1, "search_term": search_query }
                                        }
                                        yielded_count += 1
                        except:
                            continue

                    # Move to next page
                    if not self._has_next_page():
                        logger.info("No more pages found.")
                        break
                    
                    page_idx += 1
                    # 4. Long Cooldown between pages
                    page_wait = random.uniform(45, 90)
                    logger.info(f"Waiting {int(page_wait)}s before next page to avoid blocking...")
                    time.sleep(page_wait)

                except Exception as e:
                    logger.error(f"Error on Google Page {page_idx + 1}: {e}")
                    break
        finally:
            self.close()

    def close(self):
        if self._driver:
            try:
                self._driver.quit()
            except:
                pass
            self._driver = None