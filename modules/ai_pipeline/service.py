import logging
from typing import Dict, Any, List
from modules.ai_pipeline.advanced_dork_generator import generate_ai_dorks
from modules.ai_pipeline.trend_analyzer import analyze_trends
from modules.trend_engine.shared_trend_engine import SharedTrendEngine

logger = logging.getLogger(__name__)

class AIPipelineService:
    """
    Coordinates the AI Pipeline 3 Modes:
    1. Trend Based
    2. Free Prompt
    3. Optimize Existing Dorks
    """

    def __init__(self):
        pass

    def run_mode_1_trend_based(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Mode 1: Trend Based
        Fetches trends from SharedTrendEngine -> Analyzes -> Generates Dorks.
        Returns a list of Opportunities, each containing their AI Dorks.
        """
        logger.info("Running AI Pipeline Mode 1: Trend Based")
        # 1. Fetch from shared engine
        raw_signals = SharedTrendEngine.get_trends(force_refresh=force_refresh)
        
        # 2. Analyze
        trends = analyze_trends(raw_signals)
        
        results = []
        for trend in trends:  # Limit removed to show all trends
            intent = f"{trend.get('trend_name', '')}. Requirements: {', '.join(trend.get('business_requirements', []))}"
            location = trend.get("region") or trend.get("country") or "Global"
            industry = trend.get("sector") or "B2B"
            
            dork_payload = generate_ai_dorks(intent, location, industry)
            
            trend["dork_payload"] = dork_payload
            results.append(trend)
            
        return results

    def run_mode_2_free_prompt(self, prompt: str, location: str = "Global") -> Dict[str, Any]:
        """
        Mode 2: Free Prompt Mode
        Directly generates dorks based on a user's natural language request.
        """
        logger.info(f"Running AI Pipeline Mode 2 for prompt: {prompt}")
        return generate_ai_dorks(intent_description=prompt, location=location, industry="Custom")

    def run_mode_3_optimize(self, existing_dorks: List[str], intent: str = "Lead Generation") -> Dict[str, Any]:
        """
        Mode 3: Optimize Existing Dorks
        Enhances existing user dorks.
        """
        logger.info("Running AI Pipeline Mode 3: Optimize")
        prompt = f"Optimize these existing dorks for {intent}:\n" + "\n".join(existing_dorks)
        return generate_ai_dorks(intent_description=prompt, location="Global", industry="Optimization")
