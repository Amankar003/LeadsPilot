import logging
import json
from typing import List, Dict, Any

from modules.ai.ai_client import AIClient
from modules.trend_engine.constants import SECTOR_KEYWORDS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite B2B Market Analyst.

Given a list of recent news/trends, identify ALL highly actionable B2B lead generation opportunities.

Rules:
1. Ignore consumer gossip or non-business news. Focus strictly on B2B trends, company expansions, funding, new regulations, tech adoption, or staffing shortages.
2. Return ONLY a valid JSON array of trend objects.

Required JSON Structure (Array of Objects):
[
  {
    "trend_name": "Short summary of the trend (e.g. London Clinics Adopting AI)",
    "country": "Target country (e.g. UK, USA)",
    "region": "Target region/city",
    "sector": "Broad sector (e.g. healthcare, real estate, ecommerce)",
    "opportunity_reason": "Why this is a good time to pitch them",
    "business_requirements": ["list", "of", "likely", "needs"],
    "recommended_service": "One service to pitch (e.g. WhatsApp Automation, Local SEO)",
    "confidence_score": 85
  }
]
"""

def analyze_trends(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Analyzes raw news signals and outputs actionable B2B trends using LeadPilot's AIClient.
    """
    if not signals:
        return []

    logger.info(f"Analyzing {len(signals)} signals for B2B trends...")

    ai_client = AIClient()

    # Consolidate signals to avoid blowing up the context window
    context_lines = []
    for s in signals[:20]:
        context_lines.append(
            f"Title: {s.get('title')}\n"
            f"Loc: {s.get('region')}, {s.get('country')}\n"
            f"Desc: {s.get('raw_text', '')[:200]}"
        )
    
    prompt = "Here is the recent news data:\n\n" + "\n---\n".join(context_lines)

    try:
        response_json = ai_client.generate_json(prompt=prompt, system_prompt=SYSTEM_PROMPT, temperature=0.3)
        
        # Depending on how groq formats it, we might get a list directly or a dict with a list inside
        trends = []
        if isinstance(response_json, list):
            trends = response_json
        elif isinstance(response_json, dict):
            # Sometimes LLMs wrap the array in a key like 'trends' or 'opportunities'
            for key, val in response_json.items():
                if isinstance(val, list):
                    trends = val
                    break
        
        # Filter and validate trends
        valid_trends = []
        for t in trends:
            if isinstance(t, dict) and t.get("trend_name") and t.get("sector"):
                valid_trends.append(t)
                
        logger.info(f"Identified {len(valid_trends)} actionable trends.")
        return valid_trends
    except Exception as e:
        logger.error(f"Failed to analyze trends: {e}")
        return []
