import httpx
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class WebsiteScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        
    def extract_emails_from_url(self, url: str) -> list:
        try:
            # Ensure url has scheme
            if not url.startswith('http'):
                url = 'https://' + url
                
            response = httpx.get(url, headers=self.headers, timeout=10.0, follow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                text = soup.get_text()
                
                emails = set(self.email_pattern.findall(text))
                
                # Exclude image/asset extensions that might look like emails
                valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
                
                # Optionally check contact page if no emails found
                if not valid_emails:
                    contact_links = []
                    for a in soup.find_all('a', href=True):
                        if 'contact' in a['href'].lower() or 'about' in a['href'].lower():
                            contact_links.append(urljoin(url, a['href']))
                            
                    for link in list(set(contact_links))[:2]: # Try max 2 contact links
                        try:
                            c_resp = httpx.get(link, headers=self.headers, timeout=5.0, follow_redirects=True)
                            c_soup = BeautifulSoup(c_resp.text, 'html.parser')
                            c_text = c_soup.get_text()
                            c_emails = set(self.email_pattern.findall(c_text))
                            valid_emails.extend([e for e in c_emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))])
                        except Exception:
                            continue
                            
                return list(set(valid_emails))
                
        except Exception as e:
            logger.debug(f"Failed to scrape {url}: {str(e)}")
            return []
            
        return []
