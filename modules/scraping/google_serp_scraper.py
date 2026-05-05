import time
import random
import re
import urllib.parse
from modules.scraping.base_scraper import BaseScraper
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# User agents for rotation to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

PHONE_REGEX = re.compile(
    r"(?:(?:\+44\s?|0044\s?|0)(?:[123789]\d\s?\d{3,4}\s?\d{4}|\d{2}\s?\d{4}\s?\d{4}))",
    re.IGNORECASE
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

class GoogleSERPScraper(BaseScraper):
    def __init__(
        self,
        max_pages=3,
        results_per_page=10,
        delay_min=60.0,
        delay_max=90.0,
        headless=True,
        country="UK",
        proxy=None,
        captcha_api_key=None,
    ):
        self.max_pages = max_pages
        self.results_per_page = results_per_page
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.headless = headless
        self.country = country
        self.proxy = proxy
        self.captcha_api_key = captcha_api_key
        self._driver = None
        self.pages_scraped = 0
        self.browser_restart_interval = 3  # Restart browser every 3 pages

    def _apply_stealth(self, driver):
        try:
            from selenium_stealth import stealth
            stealth(
                driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
        except Exception as e:
            logger.warning(f"selenium-stealth not applied: {e}")
        return driver

    def _create_driver(self):
        try:
            import undetected_chromedriver as uc
            opts = uc.ChromeOptions()
            if self.headless:
                opts.add_argument("--headless")
            
            # Anti-detection arguments
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--window-size=1280,900")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("--disable-web-resources")
            opts.add_argument("--disable-client-side-phishing-detection")
            
            # User agent rotation
            user_agent = random.choice(USER_AGENTS)
            opts.add_argument(f"user-agent={user_agent}")
            
            if self.proxy:
                opts.add_argument(f"--proxy-server={self.proxy}")
            
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_settings.popups": 0,
            }
            opts.add_experimental_option("prefs", prefs)
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)

            driver = uc.Chrome(options=opts, version_main=None)
            driver.set_page_load_timeout(45)
            driver = self._apply_stealth(driver)
            
            # Add extra headers
            driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": user_agent
            })
            
            return driver
        except Exception as e:
            error_msg = str(e)
            if "Current browser version is" in error_msg:
                try:
                    import re
                    match = re.search(r"Current browser version is (\d+)", error_msg)
                    if match:
                        version = int(match.group(1))
                        logger.info(f"Retrying undetected-chromedriver with version_main={version}")
                        
                        # Create NEW options for retry
                        import undetected_chromedriver as uc
                        retry_opts = uc.ChromeOptions()
                        if self.headless:
                            retry_opts.add_argument("--headless")
                        retry_opts.add_argument("--no-sandbox")
                        retry_opts.add_argument("--disable-dev-shm-usage")
                        retry_opts.add_argument("--window-size=1280,900")
                        retry_opts.add_argument("--disable-blink-features=AutomationControlled")
                        
                        user_agent = random.choice(USER_AGENTS)
                        retry_opts.add_argument(f"user-agent={user_agent}")
                        
                        if self.proxy:
                            retry_opts.add_argument(f"--proxy-server={self.proxy}")
                        prefs = {"profile.managed_default_content_settings.images": 2}
                        retry_opts.add_experimental_option("prefs", prefs)
                        retry_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
                        retry_opts.add_experimental_option("useAutomationExtension", False)

                        driver = uc.Chrome(options=retry_opts, version_main=version)
                        driver.set_page_load_timeout(45)
                        driver = self._apply_stealth(driver)
                        return driver
                except Exception as retry_e:
                    logger.error(f"Retry with version_main failed: retry_e={retry_e}")

            logger.error(f"Failed to create undetected-chromedriver: {e}")

            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service
                
                opts = Options()

                if self.headless:
                    opts.add_argument("--headless=new")

                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.add_argument("--window-size=1280,900")
                opts.add_argument("--disable-blink-features=AutomationControlled")
                
                user_agent = random.choice(USER_AGENTS)
                opts.add_argument(f"user-agent={user_agent}")
                
                if self.proxy:
                    opts.add_argument(f"--proxy-server={self.proxy}")

                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=opts)
                driver.set_page_load_timeout(45)

                driver = self._apply_stealth(driver)

                return driver

            except Exception as e:
                logger.error(f"Failed to create standard selenium driver: {e}")
                return None

    def _google_url(self, query, page):
        start = page * self.results_per_page
        encoded_query = urllib.parse.quote_plus(query)
        # Adding gl=uk for UK location if needed, based on country
        if self.country == "UK":
            return f"https://www.google.com/search?q={encoded_query}&start={start}&gl=uk"
        return f"https://www.google.com/search?q={encoded_query}&start={start}"

    def _is_captcha_page(self, page_source: str, current_url="") -> bool:
        if current_url and ("google.com/sorry" in current_url or "/sorry/index" in current_url):
            return True
        indicators = [
            "Our systems have detected unusual traffic",
            "recaptcha",
            "g-recaptcha",
            "captcha",
        ]
        lower = page_source.lower()
        return any(ind.lower() in lower for ind in indicators)


    def _has_next_page(self) -> bool:
        from selenium.webdriver.common.by import By
        try:
            nexts = self._driver.find_elements(By.ID, "pnnext")
            if nexts:
                return True
            nexts = self._driver.find_elements(By.CSS_SELECTOR, "a[aria-label='Next page']")
            return bool(nexts)
        except:
            return False

    def _clean_email(self, raw: str) -> str | None:
        email = raw.strip().lower().rstrip(".,;:\"'")
        if email in EMAIL_BLACKLIST:
            return None
        prefixes_to_skip = ["noreply", "no-reply", "donotreply", "privacy", "abuse"]
        if any(email.startswith(p) for p in prefixes_to_skip):
            return None
        try:
            domain = email.split("@")[-1]
            if domain in BLACKLIST_DOMAINS:
                return None
            if "." not in domain:
                return None
            if len(email) < 6 or len(email) > 254:
                return None
            return email
        except:
            return None

    def _clean_phone(self, raw: str) -> str | None:
        if not raw:
            return None
        import phonenumbers
        try:
            for region in ["GB", "US", "IN", "AU", "CA"]:
                for match in phonenumbers.PhoneNumberMatcher(raw, region):
                    try:
                        formatted = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                        if self.country == "UK" and not formatted.startswith("+44"):
                            continue
                        return formatted
                    except:
                        pass
        except Exception:
            pass
        return None

    def _clean_name(self, raw: str) -> str | None:
        if not raw:
            return None
        name = raw.strip()
        if len(name) < 3:
            return None
        return name

    def extract_contacts(self, text: str):
        emails = set()
        phones = set()
        if not text:
            return emails, phones

        raw_emails = EMAIL_REGEX.findall(text)
        for e in raw_emails:
            c = self._clean_email(e)
            if c:
                emails.add(c)
                
        try:
            import phonenumbers
            for region in ["GB", "US", "IN", "AU", "CA"]:
                for match in phonenumbers.PhoneNumberMatcher(text, region):
                    try:
                        formatted = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                        if self.country == "UK" and not formatted.startswith("+44"):
                            continue
                        phones.add(formatted)
                    except:
                        pass
        except Exception:
            pass
            
        if emails or phones:
            logger.debug(f"Extracted from snippet: Emails={list(emails)}, Phones={list(phones)}")
            
        return emails, phones

    def _is_invalid_source_url(self, url: str) -> bool:
        if not url:
            return True
        url = url.lower()
        invalid_patterns = [
            "google.com/search",
            "bing.com/search",
            "duckduckgo.com",
            "search?q="
        ]
        return any(pattern in url for pattern in invalid_patterns)

    def _is_fake_business_name(self, name: str, query: str) -> bool:
        if not name:
            return True
        name_lower = name.lower().strip()
        query_lower = query.lower().strip()
        fake_keywords = [
            "phone lead",
            "email lead",
            "search result",
            "google search",
            "site:facebook.com",
            "site:instagram.com",
            "site:linkedin.com"
        ]
        if any(keyword in name_lower for keyword in fake_keywords):
            return True
        if query_lower and query_lower == name_lower:
            return True
        return False

    def _parse_serp_cards(self, query: str, search_query: str, page_num: int, google_url: str):
        from selenium.webdriver.common.by import By
        cards = []
        try:
            # Multiple selectors for robustness
            selectors = ["div.g", "div.tF2Cxc", "div.yuRUbf", "div.v7W49e > div"]
            snippets = []
            for sel in selectors:
                found = self._driver.find_elements(By.CSS_SELECTOR, sel)
                if found:
                    snippets = found
                    logger.debug(f"Found {len(snippets)} snippets using selector: {sel}")
                    break
            
            if not snippets:
                logger.warning("No Google snippets found on the page. Selectors might be outdated.")
                # Fallback: try to find anything that looks like a result
                snippets = self._driver.find_elements(By.XPATH, "//div[@data-hveid]")

            for snippet in snippets:
                try:
                    # Look for h3 inside the snippet
                    try:
                        title_elem = snippet.find_element(By.TAG_NAME, "h3")
                        result_title = title_elem.text.strip()
                    except:
                        result_title = ""
                    
                    try:
                        link_elem = snippet.find_element(By.CSS_SELECTOR, "a[href]")
                        result_url = link_elem.get_attribute("href")
                    except:
                        result_url = ""
                    
                    if not result_title and not result_url:
                        continue

                    card_text = snippet.text
                    card_html = snippet.get_attribute("innerHTML")
                    
                    cards.append({
                        "result_title": result_title,
                        "result_url": result_url,
                        "card_text": card_text,
                        "card_html": card_html
                    })
                except Exception as snippet_e:
                    continue
        except Exception as e:
            logger.debug(f"Error parsing SERP cards: {e}")
            
        logger.info(f"Parsed {len(cards)} valid result cards from SERP.")
        return cards

    def scrape(self, query: str, limit: int = None, location: str = None, should_stop=None):
        if not self._driver:
            self._driver = self._create_driver()
            if not self._driver:
                return []

        search_query = f"{query} in {location}" if location else query
        found_contacts = set()
        yielded_count = 0
        page_idx = 0
        captcha_retries = 0
        max_captcha_retries = 1  # Only retry once, then skip
        self.pages_scraped = 0
        
        try:
            while True:
                if should_stop and should_stop():
                    logger.info("Scrape stopped by user.")
                    break

                if limit and limit > 0 and yielded_count >= limit:
                    break

                if page_idx >= self.max_pages:
                    break

                # Browser restart every N pages for freshness
                if self.pages_scraped > 0 and self.pages_scraped % self.browser_restart_interval == 0:
                    logger.info(f"Restarting browser after {self.pages_scraped} pages to avoid detection...")
                    self.close()
                    time.sleep(15)  # Wait before restart
                    self._driver = self._create_driver()
                    if not self._driver:
                        logger.error("Failed to restart browser")
                        break

                google_url = self._google_url(search_query, page_idx)
                logger.info(f"Scraping SERP Page {page_idx + 1}... ({google_url})")

                try:
                    self._driver.get(google_url)
                    time.sleep(5)  # Initial wait
    
                    current_url = self._driver.current_url
                    if self._is_captcha_page(self._driver.page_source, current_url):
                        captcha_retries += 1
                        if captcha_retries > max_captcha_retries:
                            logger.warning(f"[!] Too many CAPTCHAs. Skipping remaining pages...")
                            break
                        
                        logger.warning(f"[!] CAPTCHA detected on Page {page_idx + 1}. Waiting 180 seconds and skipping this page...")
                        
                        # Long wait and skip
                        time.sleep(180)
                        
                        # Skip this page and move to next
                        page_idx += 1
                        time.sleep(random.uniform(self.delay_min, self.delay_max))
                        continue
                    
                    # Reset captcha retries on success
                    captcha_retries = 0
                    self.pages_scraped += 1
                    
                    cards = self._parse_serp_cards(query, search_query, page_idx, google_url)
                    logger.info(f"Found {len(cards)} cards on page {page_idx + 1}")
                    
                    for card in cards:
                        if should_stop and should_stop():
                            break
                        if limit and limit > 0 and yielded_count >= limit:
                            break
                            
                        result_title = card["result_title"]
                        result_url = card["result_url"]
                        card_text = card["card_text"]
                        
                        emails, phones = self.extract_contacts(card_text)
                        
                        domain_name = ""
                        if result_url and not self._is_invalid_source_url(result_url):
                            domain_name = urllib.parse.urlparse(result_url).netloc.replace('www.', '')
                        
                        b_name = result_title
                        if not b_name:
                            b_name = domain_name
                            
                        if self._is_fake_business_name(b_name, search_query):
                            continue
                            
                        if self._is_invalid_source_url(result_url):
                            continue
                            
                        for email in emails:
                            unique_key = email + result_url + b_name
                            if unique_key not in found_contacts:
                                found_contacts.add(unique_key)
                                yield {
                                    "business_name": b_name,
                                    "category": query,
                                    "email": email,
                                    "phone": None,
                                    "source": "google_serp_search",
                                    "google_maps_url": result_url,
                                    "email_source": "google_serp_result",
                                    "email_confidence": "medium",
                                    "lead_hash": str(hash(unique_key)),
                                    "raw_data": {
                                        "name": b_name,
                                        "source_url": result_url,
                                        "google_search_url": google_url,
                                        "result_title": result_title,
                                        "result_url": result_url,
                                        "serp_page": page_idx + 1,
                                        "search_term": search_query,
                                        "createdOn": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                        "extraction_type": "serp_snippet"
                                    }
                                }
                                yielded_count += 1
                                
                        for phone in phones:
                            unique_key = phone + result_url + b_name
                            if unique_key not in found_contacts:
                                found_contacts.add(unique_key)
                                yield {
                                    "business_name": b_name,
                                    "category": query,
                                    "email": None,
                                    "phone": phone,
                                    "source": "google_serp_search",
                                    "google_maps_url": result_url,
                                    "email_source": None,
                                    "email_confidence": None,
                                    "lead_hash": str(hash(unique_key)),
                                    "raw_data": {
                                        "name": b_name,
                                        "source_url": result_url,
                                        "google_search_url": google_url,
                                        "result_title": result_title,
                                        "result_url": result_url,
                                        "serp_page": page_idx + 1,
                                        "search_term": search_query,
                                        "createdOn": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                        "extraction_type": "serp_snippet"
                                    }
                                }
                                yielded_count += 1
    
                    if not self._has_next_page():
                        logger.info(f"No more pages found after page {page_idx + 1}. Scraping complete.")
                        break
                    
                    page_idx += 1
                    logger.info(f"Moving to Google Page {page_idx + 1}. Total leads found so far: {yielded_count}")
                    time.sleep(random.uniform(self.delay_min, self.delay_max))
    
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
