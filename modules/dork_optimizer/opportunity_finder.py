import logging
from typing import List, Dict, Any
from modules.dork_optimizer.schemas import Trend

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
        seen = set()
        
        valid_trends = 0
        invalid_trends = 0
        
        for raw_trend in trends:
            try:
                # 1. Pydantic Validation & Default Injection
                trend_obj = Trend(**raw_trend)
                
                # 2. Extract safe properties
                category = trend_obj.category
                region = trend_obj.region or "Unknown Region"
                country = trend_obj.country or "Unknown Country"
                target_service = trend_obj.target_service
                
                dup_key = f"{category}|{region}|{country}"
                if dup_key in seen:
                    continue
                seen.add(dup_key)
                
                # 3. Compute Feasibility/Quality Score (0-100)
                score = 65  # Baseline score
                
                if region and region != "Metropolitan Areas": score += 10
                state_val = raw_trend.get("state")
                if state_val: score += 10
                if category in ("Real Estate", "Healthcare"): score += 10
                if target_service in ("CRM Automation", "AI Chatbot", "Email Outreach"): score += 5
                
                score = min(score, 100)
                
                # 4. Build personalized B2B pitch offer
                suggested_offer = OFFER_TEMPLATES.get(
                    target_service, 
                    f"A specialized digital transformation package mapping {target_service} solutions to operational constraints."
                )
                
                # Extract safe fallback fields for backwards compatibility with old dicts
                demand_signal = raw_trend.get("demand_signal", "market shifts")
                trend_reason = raw_trend.get("trend_reason") or trend_obj.description
                title = raw_trend.get("title") or trend_obj.trend_name
                link = raw_trend.get("link", "")
                
                # 5. Create Opportunity object
                opp = {
                    "country": country,
                    "state": state_val or country,
                    "region": region,
                    "category": category,
                    "trend_summary": f"Rising market indicators show B2B businesses in {region} are facing {demand_signal.lower()}.",
                    "opportunity_reason": trend_reason,
                    "suggested_offer": suggested_offer,
                    "target_service": target_service,
                    "score": score,
                    "trend_score": raw_trend.get("trend_score", 0),
                    "confidence_score": raw_trend.get("confidence_score", trend_obj.opportunity_score),
                    "source_articles": [
                        {
                            "title": title,
                            "link": link
                        }
                    ]
                }
                
                opportunities.append(opp)
                valid_trends += 1
                
                if len(opportunities) >= limit:
                    break
                    
            except Exception as e:
                logger.error(f"Validation Error for trend: {e}")
                invalid_trends += 1
                continue
                
        # 6. Detailed Diagnostics
        logger.info(f"Opportunity Generation Complete | Received: {len(trends)} | Valid: {valid_trends} | Invalid: {invalid_trends} | Opportunities Created: {len(opportunities)}")
        
        return opportunities
