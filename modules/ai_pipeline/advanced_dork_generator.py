import logging
from typing import List, Dict, Any

from modules.ai.ai_client import AIClient
from modules.trend_engine.constants import SECTOR_KEYWORDS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a B2B lead generation expert for 3FI Tech.

Generate highly advanced Google search dorks for lead extraction, NOT simple/basic keyword searches.

Every single dork MUST include at least one advanced search operator (like site:, inurl:, intitle:, OR) or specific lead intent keywords (like "@gmail.com", "info@", "contact us", "WhatsApp", "Powered by Shopify", or country phone codes).

Strict Rules:
1. Every dork must include standard noise filters: "-jobs -job -careers -hiring -recruitment -internship -pdf -gov -edu -org -news -press".
2. Avoid weak/generic dorks.
3. Output a valid JSON object.
4. Provide realistic lead potential estimates.
"""

def generate_ai_dorks(intent_description: str, location: str = "Global", industry: str = "B2B") -> Dict[str, Any]:
    """
    Generates advanced dorks dynamically using AI, along with Lead Potential metrics.
    Works across 3 Modes (Trend-Based, Free Prompt, Optimization).
    """
    ai_client = AIClient()
    
    prompt = f"""Generate 8-15 advanced Google search B2B business keywords and target website URLs for this opportunity.

Context/Intent: {intent_description}
Location: {location}
Industry/Sector: {industry}

Return ONLY valid JSON in this exact structure (no markdown, no explanation, no code block):
{{
  "lead_potential_range": "e.g. 500+",
  "confidence_score": 85,
  "target_persona": "e.g. Clinic Owners, Marketing Directors",
  "service_fit": "e.g. WhatsApp Automation",
  "keywords": ["keyword1", "keyword2", ...],
  "dorks": [
      {{ "dork": "...", "reason": "Why this dork works" }},
      {{ "dork": "...", "reason": "Why this dork works" }}
  ]
}}
"""

    logger.info(f"Generating advanced AI dorks for: {intent_description}")
    
    try:
        response_json = ai_client.generate_json(prompt=prompt, system_prompt=SYSTEM_PROMPT, temperature=0.4)
        
        # Fallback empty structure
        if not response_json or "dorks" not in response_json:
            logger.warning("AI failed to return valid dork schema. Returning fallback.")
            return _fallback_dorks(intent_description, location, industry)
            
        return response_json

    except Exception as e:
        logger.error(f"Failed to generate AI dorks: {e}")
        return _fallback_dorks(intent_description, location, industry)

def _fallback_dorks(intent_description: str, location: str, industry: str) -> Dict[str, Any]:
    """Deterministic fallback if AI fails."""
    return {
        "lead_potential_range": "Unknown",
        "confidence_score": 50,
        "target_persona": "Business Owners",
        "service_fit": "Lead Generation",
        "keywords": [industry, "services", "business"],
        "dorks": [
            {
                "dork": f'"{industry}" "{location}" "contact us" -jobs -careers -pdf -edu -gov',
                "reason": "Direct fallback contact page extraction."
            },
            {
                "dork": f'"{industry}" "{location}" "@gmail.com" -jobs -careers -pdf -edu -gov',
                "reason": "Fallback email extraction."
            }
        ]
    }
