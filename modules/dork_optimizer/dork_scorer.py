import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DorkScorer:
    def __init__(self):
        pass

    def score_dork(self, dork: str, context: Dict[str, Any]) -> int:
        """
        Contextually scores a compiled Google dork on a scale of 0 to 100.
        Factors: specificity, search operator usage, TLD filtering, and negative operators.
        """
        if not dork:
            return 0
            
        score = 50  # Baseline score
        
        # 1. Negative Filter Exclusions (+20 points)
        # Having negative exclusions (excluding job boards, social listings, etc.) makes dorks highly targeted.
        negatives = [part for part in dork.split(" ") if part.startswith("-")]
        if negatives:
            score += min(len(negatives) * 3, 20)
            
        # 2. Quote Specificity (+20 points)
        # Specific double quoted strings guarantee exact matches in search results.
        quotes_count = dork.count('"')
        if quotes_count >= 4:  # At least two quoted phrases
            score += 15
        elif quotes_count >= 2:
            score += 10
            
        # 3. Country TLD search filter (+20 points)
        # Using the site: operator to restrict to country-specific TLDs (e.g. site:co.uk) is highly targeted.
        if "site:" in dork:
            score += 20
            
        # 4. Service-Intent Operators (+10 points)
        # Words indicating specific commercial intent like "book appointment" or "get quote"
        intent_keywords = ["appointment", "booking", "get quote", "services", "info@", "contact@"]
        if any(kw in dork.lower() for kw in intent_keywords):
            score += 10
            
        # 5. Length penalty (-10 points if too long or short)
        # Google search supports up to 32 words. Overly verbose queries fail to match.
        words_count = len(dork.split(" "))
        if words_count > 30:
            score -= 15
        elif words_count < 3:
            score -= 10
            
        # Guarantee boundary limits
        return max(min(score, 100), 0)
