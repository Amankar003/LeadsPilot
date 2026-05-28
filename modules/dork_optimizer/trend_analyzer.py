import logging
from typing import List, Dict, Any
from modules.dork_optimizer.constants import TARGET_SERVICES

logger = logging.getLogger(__name__)

# Categories list for keyword matching
CATEGORIES_MAP = {
    "Real Estate": ["real estate", "broker", "realtor", "property", "apartment", "agency", "agencies"],
    "Healthcare": ["clinic", "medical", "doctor", "dental", "dentist", "practitioner", "hospital", "patient"],
    "Retail": ["retail", "shop", "boutique", "store", "commerce", "sales", "merchant"],
    "Contractor Services": ["solar", "contractor", "hvac", "plumber", "electrician", "builder", "landscaping", "roofing"],
    "Professional Services": ["consultancy", "consulting", "lawyer", "accountant", "agency", "b2b", "professional"],
    "Hospitality": ["hotel", "restaurant", "cafe", "resort", "food", "dining", "hospitality"]
}

# Country and region mappings for keyword matching
GEOGRAPHIES = {
    "US": {"country": "US", "state": "Florida", "region": "Miami"},
    "United States": {"country": "US", "state": "New York", "region": "New York"},
    "UK": {"country": "UK", "state": "England", "region": "London"},
    "United Kingdom": {"country": "UK", "state": "England", "region": "London"},
    "UAE": {"country": "UAE", "state": "Dubai", "region": "Dubai"},
    "Dubai": {"country": "UAE", "state": "Dubai", "region": "Dubai"},
    "Australia": {"country": "Australia", "state": "New South Wales", "region": "Sydney"},
    "Sydney": {"country": "Australia", "state": "New South Wales", "region": "Sydney"},
    "Canada": {"country": "Canada", "state": "Ontario", "region": "Toronto"},
    "Toronto": {"country": "Canada", "state": "Ontario", "region": "Toronto"},
    "Singapore": {"country": "Singapore", "state": "Singapore", "region": "Singapore"}
}

class TrendAnalyzer:
    def __init__(self):
        pass

    def analyze_trends(self, news_items: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parses news items to extract structured digital transformation trend signals.
        Uses rule-based algorithmic matching with predefined B2B category-service maps.
        """
        logger.info(f"Analyzing {len(news_items)} news items for B2B opportunity signals...")
        trends = []
        
        target_service_filter = config.get("target_service")
        
        for idx, item in enumerate(news_items):
            title = item.get("title", "")
            desc = item.get("description", "")
            text_pool = f"{title} {desc}".lower()
            
            # 1. Match Category
            matched_category = "General Business"
            for category, keywords in CATEGORIES_MAP.items():
                if any(keyword in text_pool for keyword in keywords):
                    matched_category = category
                    break
            
            # 2. Match Geography
            matched_geo = {"country": "Global", "state": None, "region": None}
            for keyword, geo_data in GEOGRAPHIES.items():
                if keyword.lower() in text_pool:
                    matched_geo = geo_data.copy()
                    break
            
            # Allow manual config overrides
            if config.get("country"): matched_geo["country"] = config["country"]
            if config.get("state"): matched_geo["state"] = config["state"]
            if config.get("region"): matched_geo["region"] = config["region"]
            
            # 3. Match Target Service
            matched_service = None
            for service in TARGET_SERVICES:
                # Look for exact service substring or partial tokens
                tokens = service.lower().split(" ")
                if any(t in text_pool for t in tokens if len(t) > 3):
                    matched_service = service
                    break
            
            if not matched_service:
                # Round-robin selection based on index to keep fallback diverse
                matched_service = TARGET_SERVICES[idx % len(TARGET_SERVICES)]
                
            # If user selected a specific target service, enforce it
            if target_service_filter and target_service_filter != matched_service:
                matched_service = target_service_filter
                
            # 4. Construct demand description
            demand_signals = []
            if "crm" in text_pool or "pipeline" in text_pool:
                demand_signals.append("Inflow tracking problems")
            if "phone" in text_pool or "call" in text_pool or "chat" in text_pool:
                demand_signals.append("High phone call volume and staff shortages")
            if "seo" in text_pool or "search" in text_pool or "organic" in text_pool:
                demand_signals.append("Low organic web search visibility")
            if "speed" in text_pool or "load" in text_pool or "mobile" in text_pool:
                demand_signals.append("Slow mobile page speeds causing patient/customer churn")
                
            if not demand_signals:
                demand_signals.append("Increasing customer acquisition costs and labor overheads")
                
            # 5. Build structured B2B trend signal
            trend_signal = {
                "category": matched_category,
                "country": matched_geo["country"],
                "state": matched_geo["state"],
                "region": matched_geo["region"] or matched_geo["state"] or "Metropolitan Areas",
                "target_service": matched_service,
                "demand_signal": ", ".join(demand_signals),
                "trend_reason": desc[:250] if len(desc) > 10 else f"Local B2B businesses in {matched_geo['country']} are actively migrating manual services to digital systems to optimize operational costs.",
                "title": title,
                "link": item.get("link", "https://news.google.com")
            }
            trends.append(trend_signal)
            
        return trends
