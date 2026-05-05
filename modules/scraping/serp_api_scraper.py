import os
import re
import time
import math
import hashlib
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from modules.scraping.base_scraper import BaseScraper
from utils.logging_utils import get_logger

load_dotenv()

logger = get_logger(__name__)


class SerpAPIScraper(BaseScraper):
    """
    SERP API based scraper with pagination.

    Goal:
    - 1 query se 60+ records collect karna
    - Google browser/Selenium use nahi karna
    - CAPTCHA screen avoid karna
    - SerpApi JSON results se websites collect karna
    """

    def __init__(self, max_results: int = 120, max_pages: int = 12, target_leads: int = 60):
        self.api_key = os.getenv("SERP_API_KEY")
        self.max_results = max_results
        self.max_pages = max_pages
        self.target_leads = target_leads

        if not self.api_key:
            logger.error("SERP_API_KEY missing in .env file")

    def _generate_lead_hash(self, title: str, url: str, query: str) -> str:
        raw = f"{title}|{url}|{query}".lower().strip()
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _search_serpapi_page(
        self,
        query: str,
        location: str = None,
        page: int = 1,
        results_per_page: int = 10,
    ):
        """
        SerpApi se ek specific Google result page fetch karta hai.

        page=1 -> start=0
        page=2 -> start=10
        page=3 -> start=20
        """
        if not self.api_key:
            logger.error("SERP_API_KEY missing. Please add SERP_API_KEY in .env file.")
            return []

        start = (page - 1) * results_per_page

        params = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": results_per_page,
            "start": start,
            "hl": "en",
            "gl": "in",
        }

        if location:
            params["location"] = location

        try:
            logger.info(
                f"SerpApi request | query='{query}' | page={page} | start={start}"
            )

            response = requests.get(
                "https://serpapi.com/search.json",
                params=params,
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(
                    f"SerpApi request failed | "
                    f"Status={response.status_code} | Response={response.text[:500]}"
                )
                return []

            data = response.json()

            if data.get("error"):
                logger.error(f"SerpApi error on page {page}: {data.get('error')}")
                return []

            organic_results = data.get("organic_results", [])

            logger.info(
                f"SerpApi returned {len(organic_results)} results | "
                f"query='{query}' | page={page}"
            )

            return organic_results

        except requests.exceptions.Timeout:
            logger.error(f"SerpApi request timed out on page {page}.")
            return []

        except Exception as e:
            logger.error(f"SerpApi search failed on page {page}: {e}")
            return []

    def _search_serpapi(
        self,
        query: str,
        location: str = None,
        limit: int = 120,
        pages: int = 12,
        should_stop=None,
    ):
        """
        Multiple SERP pages fetch karta hai.
        """
        all_results = []
        results_per_page = 10

        limit = limit or self.max_results
        pages = pages or self.max_pages

        pages_needed_by_limit = math.ceil(limit / results_per_page)
        total_pages_to_fetch = min(pages, pages_needed_by_limit)

        logger.info(
            f"SERP pagination started | query='{query}' | "
            f"pages={total_pages_to_fetch} | raw_limit={limit}"
        )

        for page in range(1, total_pages_to_fetch + 1):
            if should_stop and should_stop():
                logger.info("SERP API pagination stopped by user.")
                break

            page_results = self._search_serpapi_page(
                query=query,
                location=location,
                page=page,
                results_per_page=results_per_page,
            )

            if not page_results:
                logger.warning(f"No results found on SERP page {page}. Continuing next page.")
                continue

            for item in page_results:
                item["_serp_page"] = page

            all_results.extend(page_results)

            if len(all_results) >= limit:
                break

            time.sleep(0.7)

        logger.info(f"Total raw SERP results fetched: {len(all_results)}")
        return all_results[:limit]

    def _clean_url(self, url: str):
        """
        URL clean karta hai.

        Important:
        - Google internal URLs block kar rahe hain.
        - Facebook/Instagram/LinkedIn ko block nahi kar rahe,
          kyunki agar user site:facebook.com query dega to records save ho sakein.
        """
        if not url:
            return None

        url = url.strip()

        blocked_domains = [
            "google.com",
            "youtube.com",
            "pinterest.com",
        ]

        try:
            parsed_domain = url.split("/")[2].lower()
            for blocked in blocked_domains:
                if blocked in parsed_domain:
                    return None
        except Exception:
            return None

        return url

    def _extract_email_phone_from_text(self, text: str):
        if not text:
            return None, None

        email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        phone_pattern = r"(?:\+?\d[\d\s().-]{8,}\d)"

        emails = re.findall(email_pattern, text)
        phones = re.findall(phone_pattern, text)

        email = None
        phone = None

        if emails:
            filtered_emails = []
            for e in emails:
                e_lower = e.lower()

                bad_email_words = [
                    "example.com",
                    "domain.com",
                    "email.com",
                    "yourname",
                    "name@example",
                    "test@",
                ]

                if not any(bad in e_lower for bad in bad_email_words):
                    filtered_emails.append(e)

            if filtered_emails:
                email = filtered_emails[0]

        if phones:
            for p in phones:
                cleaned = re.sub(r"\s+", " ", p).strip()
                digits = re.sub(r"\D", "", cleaned)

                if 8 <= len(digits) <= 15:
                    phone = cleaned
                    break

        return email, phone

    def _fetch_page_text(self, url: str):
        """
        Website ka visible text fetch karta hai.
        403/404 aana normal hai; us case me empty string return karega.
        """
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            response = requests.get(
                url,
                headers=headers,
                timeout=12,
                allow_redirects=True,
            )

            if response.status_code >= 400:
                logger.warning(f"Website fetch failed {url}: Status={response.status_code}")
                return ""

            content_type = response.headers.get("Content-Type", "").lower()

            if "text/html" not in content_type:
                return ""

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()

            return soup.get_text(" ", strip=True)

        except Exception as e:
            logger.warning(f"Failed to fetch website text from {url}: {e}")
            return ""

    def _extract_contact_from_website(self, url: str):
        """
        Homepage + common contact pages se email/phone nikalne ki koshish karta hai.

        Note:
        - Email/phone na mile tab bhi record save hoga.
        """
        if not url:
            return None, None, None

        from modules.scraping.lead_cleaner import should_scrape_website
        
        if not should_scrape_website(url):
            logger.info(f"Skipping contact scraping for non-business domain: {url}")
            return None, None, url

        # Special handling for Facebook to avoid 400 errors
        if "facebook.com" in url.lower():
            return None, None, url

        homepage_text = self._fetch_page_text(url)
        email, phone = self._extract_email_phone_from_text(homepage_text)

        if email or phone:
            return email, phone, url

        contact_paths = [
            "/contact",
            "/contact-us",
            "/contacts",
            "/about",
            "/about-us",
            "/enquiry",
            "/reach-us",
            "/get-in-touch",
        ]

        try:
            parts = url.split("/")
            base_url = parts[0] + "//" + parts[2]
        except Exception:
            base_url = url.rstrip("/")

        for path in contact_paths:
            contact_url = base_url + path
            text = self._fetch_page_text(contact_url)
            
            # If homepage was blocked (empty text) and this path is also blocked, stop spamming
            if not text and not homepage_text:
                break
                
            email, phone = self._extract_email_phone_from_text(text)

            if email or phone:
                return email, phone, contact_url

            time.sleep(0.2)

        return None, None, None

    def scrape(
        self,
        query: str,
        limit: int = None,
        location: str = None,
        pages: int = None,
        should_stop=None,
    ):
        """
        Main scrape method.

        Important:
        - List return karega, generator/yield nahi.
        - Empty case me [] return karega.
        - Target 60 records collect karne ki koshish karega.
        """

        target_leads = self.target_leads

        raw_limit = limit or self.max_results
        if raw_limit < self.max_results:
            raw_limit = self.max_results

        pages = pages or self.max_pages
        if pages < self.max_pages:
            pages = self.max_pages

        logger.info(
            f"Starting SERP API scraper | query='{query}' | location='{location}' | "
            f"raw_limit={raw_limit} | pages={pages} | target_leads={target_leads}"
        )

        organic_results = self._search_serpapi(
            query=query,
            location=location,
            limit=raw_limit,
            pages=pages,
            should_stop=should_stop,
        )

        if not organic_results:
            logger.warning(f"No SERP API results found for query: {query}")
            return []

        leads = []
        seen_urls = set()

        for index, item in enumerate(organic_results, start=1):
            if should_stop and should_stop():
                logger.info("SERP API scraping stopped by user.")
                break

            if len(leads) >= target_leads:
                break

            title = (item.get("title") or "").strip()
            link = (item.get("link") or "").strip()
            snippet = (item.get("snippet") or "").strip()
            serp_page = item.get("_serp_page", 1)

            link = self._clean_url(link)

            if not title or not link:
                continue

            if link in seen_urls:
                continue

            seen_urls.add(link)

            email, phone, contact_source_url = self._extract_contact_from_website(link)

            lead_hash = self._generate_lead_hash(
                title=title,
                url=link,
                query=query,
            )

            lead = {
                "business_name": title,
                "category": query,
                "phone": phone,
                "email": email,
                "website": link,
                "address": None,

                "has_email": bool(email),
                "has_phone": bool(phone),
                "has_website": bool(link),

                "email_source": contact_source_url if email else None,
                "email_confidence": "medium" if email else None,

                "lead_hash": lead_hash,
                "source": "serp_api",

                # Existing DB/process compatibility
                "google_maps_url": link,

                "rating": None,
                "reviews_count": None,

                "raw_data": {
                    "name": title,
                    "business_name": title,
                    "source_url": link,
                    "result_title": title,
                    "result_url": link,
                    "snippet": snippet,
                    "serp_page": serp_page,
                    "serp_position": index,
                    "search_term": query,
                    "location": location,
                    "provider": "serpapi",
                    "contact_source_url": contact_source_url,
                },
            }

            leads.append(lead)

            time.sleep(0.3)

        logger.info(
            f"SERP API scraping completed | target={target_leads} | collected={len(leads)}"
        )

        return leads