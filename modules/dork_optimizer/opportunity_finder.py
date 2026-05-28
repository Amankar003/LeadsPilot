import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Specialized pitch angles and B2B offers based on target service
OFFER_TEMPLATES = {
    "Website Development": "A high-performance mobile-optimized website audit and redevelopment plan guaranteeing sub-2 second load speeds to stop customer churn.",
    "SEO": "A comprehensive Google Schema and Local SEO map-pack audit to rank in the top 3 spots and drive free high-intent B2B organic traffic.",
    "AI Chatbot": "Implementation of a 24/7 custom booking and customer support AI Chatbot on the website, reducing administrative workload by 40%.",
    "Lead Generation": "An outbound lead acquisition campaign discovering high-value target accounts and automating structured LinkedIn and email pitches.",
    "CRM Automation": "A migration and setup package for an automated CRM funnel, enabling instant lead-responses, calendar syncs, and deal tracking.",
    "WhatsApp Automation": "A WhatsApp Business checkout and automated drip notification setup to convert abandoned carts and send automated reminders.",
    "Email Outreach": "A safe, multi-mailbox outbound cold email engine delivering hyper-personalized copy to decision-makers with automated follow-ups.",
    "Social Media Automation": "An automated content scheduling, lead-capture, and direct message auto-responder pipeline across Instagram, LinkedIn, and Facebook."
}

class OpportunityFinder:
    def __init__(self):
        pass

    def find_opportunities(self, trends: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Processes and converts raw trend signals into structured B2B business opportunities.
        Appends customized B2B offers and computes market feasibility scores out of 100.
        """
        logger.info(f"Mapping B2B opportunities from {len(trends)} trend signals...")
        opportunities = []
        
        limit = config.get("num_opportunities", 5)
        
        # Deduplicate identical category + region combinations to keep results clean
        seen = set()
        
        for trend in trends:
            category = trend["category"]
            region = trend["region"]
            country = trend["country"]
            target_service = trend["target_service"]
            
            dup_key = f"{category}|{region}|{country}"
            if dup_key in seen:
                continue
                
            seen.add(dup_key)
            
            # 1. Compute Feasibility/Quality Score (0-100)
            score = 65  # Baseline score
            
            # Specificity points
            if trend["region"] and trend["region"] != "Metropolitan Areas": score += 10
            if trend["state"]: score += 10
            
            # Industry weights
            if category in ("Real Estate", "Healthcare"): score += 10
            
            # Service fit weight
            if target_service in ("CRM Automation", "AI Chatbot", "Email Outreach"): score += 5
            
            # Limit score to 100
            score = min(score, 100)
            
            # 2. Build personalized B2B pitch offer
            suggested_offer = OFFER_TEMPLATES.get(
                target_service, 
                f"A specialized digital transformation package mapping {target_service} solutions to operational constraints."
            )
            
            # 3. Create Opportunity object
            opp = {
                "country": country,
                "state": trend["state"] or country,
                "region": region,
                "category": category,
                "trend_summary": f"Rising market indicators show B2B businesses in {region} are facing {trend['demand_signal'].lower()}.",
                "opportunity_reason": trend["trend_reason"],
                "suggested_offer": suggested_offer,
                "target_service": target_service,
                "score": score,
                "source_articles": [
                    {
                        "title": trend["title"],
                        "link": trend["link"]
                    }
                ]
            }
            
            opportunities.append(opp)
            if len(opportunities) >= limit:
                break
                
        return opportunities
