import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)

def scrape_contact_info(url: str) -> dict:
    """
    Visits a website and extracts contact details (emails, phones, socials).
    """
    result = {
        "emails": [],
        "phones": [],
        "whatsapp_links": [],
        "social_links": [],
        "contact_page": "",
        "website_status": "active",
        "scraped_text_snippet": ""
    }

    if not url or not url.startswith("http"):
        result["website_status"] = "invalid_url"
        return result

    from modules.scraping.lead_cleaner import should_scrape_website, is_social_url, is_directory_url, is_informational_url
    
    if not should_scrape_website(url):
        if is_social_url(url):
            result["website_status"] = "skipped_social_url"
        elif is_directory_url(url):
            result["website_status"] = "skipped_directory_url"
        elif is_informational_url(url):
            result["website_status"] = "skipped_informational_url"
        else:
            result["website_status"] = "skipped_non_business_domain"
        return result

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        # Task 7: Use verify=True (default)
        response = requests.get(url, headers=headers, timeout=15, verify=True)
        
        # Task 6: Handle 403 Forbidden
        if response.status_code in [403, 401, 400]:
            logger.info(f"Skipped website: blocked_{response.status_code} - {url}")
            result["website_status"] = f"blocked_{response.status_code}"
            return result
            
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. Basic cleaning of HTML
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # 2. Extract info from homepage
        info = _extract_from_html(html, soup, url)
        result.update(info)

        # 3. Look for subpages
        subpages = _find_subpages(soup, url)
        if subpages:
            result["contact_page"] = subpages[0]  # For legacy compatibility
            
            import concurrent.futures
            
            def fetch_subpage(sub_url):
                try:
                    if should_scrape_website(sub_url):
                        c_resp = requests.get(sub_url, headers=headers, timeout=15, verify=True)
                        if c_resp.status_code == 200:
                            c_soup = BeautifulSoup(c_resp.text, "html.parser")
                            return _extract_from_html(c_resp.text, c_soup, sub_url)
                except Exception:
                    pass
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(subpages))) as executor:
                future_to_url = {executor.submit(fetch_subpage, u): u for u in subpages}
                for future in concurrent.futures.as_completed(future_to_url):
                    c_info = future.result()
                    if c_info:
                        result["emails"] = list(set(result["emails"] + c_info["emails"]))
                        result["phones"] = list(set(result["phones"] + c_info["phones"]))
                        result["social_links"] = list(set(result["social_links"] + c_info["social_links"]))
                        result["whatsapp_links"] = list(set(result["whatsapp_links"] + c_info["whatsapp_links"]))

        # 4. Final cleaning
        result["scraped_text_snippet"] = soup.get_text()[:500].strip().replace("\n", " ")
        
        return result

    except requests.exceptions.SSLError:
        # Task 7: Handle SSL errors
        logger.warning(f"Skipped website: ssl_error - {url}")
        result["website_status"] = "ssl_error"
    except requests.exceptions.ConnectionError:
        logger.warning(f"Skipped website: connection_error - {url}")
        result["website_status"] = "connection_error"
    except requests.exceptions.Timeout:
        logger.warning(f"Skipped website: timeout - {url}")
        result["website_status"] = "timeout"
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            logger.info(f"Skipped website: blocked_403 - {url}")
            result["website_status"] = "blocked_403"
        else:
            logger.warning(f"Failed to scrape {url}: {str(e)}")
            result["website_status"] = f"error_{e.response.status_code}"
    except requests.exceptions.RequestException as e:
        # Task 9: Cleaner scraping output
        logger.warning(f"Failed to scrape {url}: {str(e)}")
        result["website_status"] = "error"
    except Exception as e:
        logger.error(f"Unexpected error scraping {url}: {str(e)}")
        result["website_status"] = "error"

    return result

def _extract_from_html(html: str, soup: BeautifulSoup, base_url: str) -> dict:
    """Internal helper to extract emails, phones, socials, and WhatsApp links."""

    # -------------------------------
    # 1. Extract Emails
    # -------------------------------
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, html)

    # Filter common garbage emails/images
    emails = [
        e.lower().strip()
        for e in emails
        if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))
    ]

    # Extract emails from mailto links
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.lower().startswith('mailto:'):
            email_part = href[7:].split('?')[0].strip()
            if email_part and not email_part.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
                emails.append(email_part.lower())

    # -------------------------------
    # 2. Extract Phone Numbers
    # -------------------------------
    # Broad international phone regex
    # Supports:
    # +91 9876543210
    # 98765 43210
    # +1 (555) 123-4567
    # +44 20 7946 0958
    # 0120-1234567
    # +971 50 123 4567
    # 1800-123-456
    phone_pattern = r'''
    (?<![\w])
    (?:
        (?:\+|00)?\d{1,4}[\s().-]*
    )?
    (?:
        \(?\d{1,6}\)?[\s().-]*
    )?
    \d{2,5}[\s().-]*\d{2,5}[\s().-]*\d{2,6}
    (?![\w])
    '''

    raw_phones = re.findall(phone_pattern, html, re.VERBOSE)

    clean_phones = []

    for phone in raw_phones:
        phone = phone.strip()

        if not phone:
            continue

        digits = re.sub(r'\D', '', phone)

        # International phone numbers are usually 7 to 15 digits
        if not (7 <= len(digits) <= 15):
            continue

        # Remove dummy numbers like 0000000000, 1111111111
        if len(set(digits)) <= 2:
            continue

        # Avoid common date/year-like junk
        if re.fullmatch(r'(19|20)\d{2}', digits):
            continue

        clean_phones.append(phone)

    # -------------------------------
    # 3. Extract Social & WhatsApp Links
    # -------------------------------
    social_links = []
    whatsapp_links = []

    for a in soup.find_all('a', href=True):
        href_original = a['href'].strip()
        href = href_original.lower()

        if any(s in href for s in [
            'facebook.com',
            'instagram.com',
            'linkedin.com',
            'twitter.com',
            'x.com',
            'youtube.com'
        ]):
            social_links.append(href_original)

        if (
            'wa.me' in href
            or 'api.whatsapp.com' in href
            or 'web.whatsapp.com' in href
            or 'whatsapp:' in href
        ):
            whatsapp_links.append(href_original)

    # -------------------------------
    # 4. Extract Phone Numbers from WhatsApp Links
    # -------------------------------
    for link in whatsapp_links:
        digits = re.sub(r'\D', '', link)

        if 7 <= len(digits) <= 15 and len(set(digits)) > 2:
            clean_phones.append(digits)

    # -------------------------------
    # 5. Remove Duplicates
    # -------------------------------
    emails = list(set(emails))
    clean_phones = list(set(clean_phones))
    social_links = list(set(social_links))
    whatsapp_links = list(set(whatsapp_links))

    return {
        "emails": emails,
        "phones": clean_phones,
        "social_links": social_links,
        "whatsapp_links": whatsapp_links
    }

def _find_subpages(soup: BeautifulSoup, base_url: str, max_pages: int = 5) -> list[str]:
    """Finds potential subpages like contact, about, team, privacy, etc."""
    keywords = ['contact', 'about', 'get in touch', 'reach us', 'support', 'team', 'company', 'privacy']
    found_urls = set()
    
    for a in soup.find_all('a', href=True):
        text = a.get_text().lower()
        href = a['href'].lower()
        if any(kw in text for kw in keywords) or any(kw in href for kw in keywords):
            full_url = urljoin(base_url, a['href'])
            # Basic normalization to avoid anchors like #contact
            full_url = full_url.split('#')[0]
            if full_url != base_url and full_url.startswith("http"):
                found_urls.add(full_url)
                
        if len(found_urls) >= max_pages:
            break
            
    return list(found_urls)
