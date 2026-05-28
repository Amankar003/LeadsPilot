import requests
import xml.etree.ElementTree as ET
import logging
import urllib.parse
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Rich B2B Trend fallback stories
MOCK_NEWS_STORIES = [
    {
        "title": "Dubai Real Estate Agencies Face Surge in Foreign Investors; Urgently Need CRM Systems",
        "description": "Property brokerages in the UAE are struggling to handle the inflow of prospective buyers. Industry leaders highlight a major gap in automated CRM pipeline follow-ups and lead tracking.",
        "link": "https://example.com/trends/dubai-real-estate-crm",
        "category": "Real Estate",
        "country": "UAE",
        "region": "Dubai",
        "service": "CRM Automation"
    },
    {
        "title": "London Retail Shops Leverage WhatsApp Business Checkouts as Store Rents Surge",
        "description": "With physical storefront costs rising in the UK, boutique retailers are moving their catalogs online, relying on automated WhatsApp ordering funnels and instant auto-responders to capture sales.",
        "link": "https://example.com/trends/london-retail-whatsapp",
        "category": "Retail",
        "country": "UK",
        "region": "London",
        "service": "WhatsApp Automation"
    },
    {
        "title": "Florida Medical Clinics Face Phone Line Congestion; Shift to AI Chatbots for Bookings",
        "description": "Healthcare centers and specialty clinics in the United States are seeing critical staff shortages. Implementing voice and web AI chatbots for appointment bookings is reducing administrative load by 40%.",
        "link": "https://example.com/trends/us-medical-clinics-ai",
        "category": "Healthcare",
        "country": "US",
        "region": "Florida",
        "service": "AI Chatbot"
    },
    {
        "title": "Australian Solar Installers Lag in Organic Search; Local SEO Optimization Becomes Imperative",
        "description": "A new audit reveals that over 70% of Sydney solar contracting businesses lack basic schema markup, page speed compliance, or proper local listing directories, resulting in low organic search rankings.",
        "link": "https://example.com/trends/australia-solar-seo",
        "category": "Contractor Services",
        "country": "Australia",
        "region": "Sydney",
        "service": "SEO"
    },
    {
        "title": "B2B Professional Services in Singapore Migrate to Automated Cold Email Outreach for Client Acquisition",
        "description": "Professional consultancy firms in Singapore are ditching expensive ad platforms for targeted, automated cold email drip campaigns and advanced database lead enrichment to keep sales pipelines full.",
        "link": "https://example.com/trends/singapore-b2b-outreach",
        "category": "Professional Services",
        "country": "Singapore",
        "region": "Singapore",
        "service": "Email Outreach"
    },
    {
        "title": "New York Dental Practices Face Customer Churn; Local Web Audits Show Slow Mobile Performance",
        "description": "Over 50% of dental practitioner websites in NY take more than 5 seconds to load on mobile devices, prompting patients to book appointments elsewhere. Speed optimization and web development are highly requested.",
        "link": "https://example.com/trends/new-york-dental-speed",
        "category": "Healthcare",
        "country": "US",
        "region": "New York",
        "service": "Website Development"
    },
    {
        "title": "Toronto Landscaping Contractors Overwhelmed by Off-Season Quote Requests; Lack Booking Automation",
        "description": "Home service contractors in Ontario are losing thousands of dollars in high-value leads due to manual booking and delayed responses. Implementing simple booking widgets is generating high demand.",
        "link": "https://example.com/trends/toronto-landscaping-widget",
        "category": "Contractor Services",
        "country": "Canada",
        "region": "Toronto",
        "service": "Social Media Automation"
    }
]

class NewsFetcher:
    def __init__(self):
        pass

    def _fetch_from_google_news(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetches live news from Google News RSS feed natively using feedparser.
        """
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        try:
            import feedparser
            import re
            
            feed = feedparser.parse(url)
            items = []
            
            for entry in feed.entries[:limit]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                desc = entry.get("description", "") or entry.get("summary", "")
                
                # Strip HTML tags safely from description
                desc_text = re.sub(r'<[^>]*>', '', desc)
                
                items.append({
                    "title": title,
                    "description": desc_text[:300],
                    "link": link,
                    "source": "google_news_rss"
                })
                
            return items
        except Exception as e:
            logger.warning(f"Failed to fetch Google News RSS for query '{query}': {e}")
            return []

    def fetch_global_news(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch latest global B2B digital transformation news trends.
        """
        query = "digital transformation local business automation OR marketing OR SEO OR CRM"
        live_news = self._fetch_from_google_news(query, limit)
        if live_news:
            return live_news
            
        # Return fallback stories
        return MOCK_NEWS_STORIES[:limit]

    def fetch_country_news(self, country: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch country-specific business digital transformation news.
        """
        query = f"{country} local business automation OR marketing OR CRM OR website"
        live_news = self._fetch_from_google_news(query, limit)
        
        # Merge with matching country fallback items for rich mock context
        matched_fallbacks = [item for item in MOCK_NEWS_STORIES if item["country"].lower() == country.lower()]
        
        if live_news:
            return matched_fallbacks + live_news[:limit - len(matched_fallbacks)]
            
        return matched_fallbacks if matched_fallbacks else MOCK_NEWS_STORIES[:limit]

    def fetch_category_news(self, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch industry-specific business trends news.
        """
        query = f"{category} industry automation OR digital services OR lead generation"
        live_news = self._fetch_from_google_news(query, limit)
        
        matched_fallbacks = [item for item in MOCK_NEWS_STORIES if item["category"].lower() == category.lower()]
        
        if live_news:
            return matched_fallbacks + live_news[:limit - len(matched_fallbacks)]
            
        return matched_fallbacks if matched_fallbacks else MOCK_NEWS_STORIES[:limit]
