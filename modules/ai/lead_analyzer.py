from modules.ai.ai_client import AIClient
from modules.ai.prompts import LEAD_ANALYSIS_PROMPT
from modules.ai.lead_scoring import calculate_lead_score, determine_lead_type
import json

class LeadAnalyzer:
    def __init__(self):
        self.ai = AIClient()

    def analyze_lead(self, lead_data: dict, service_focus: str = "") -> dict:
        prompt = LEAD_ANALYSIS_PROMPT.format(
            lead_details=json.dumps(lead_data, indent=2),
            service_focus=service_focus
        )
        
        response = self.ai.generate_json(prompt)
        
        if "error" in response:
            score = calculate_lead_score(lead_data)
            return {
                "recommended_service": "General Services",
                "reason": "AI analysis failed, using fallback.",
                "pain_points": ["Unknown"],
                "lead_score": score,
                "lead_type": determine_lead_type(score),
                "ai_response": response
            }
            
        ai_adj = response.get('lead_score_adjustment', 0)
        final_score = calculate_lead_score(lead_data, ai_adj)
        final_type = determine_lead_type(final_score)
        
        return {
            "recommended_service": response.get("recommended_service", "General"),
            "reason": response.get("reason", "Good fit based on profile."),
            "pain_points": response.get("pain_points", []),
            "lead_score": final_score,
            "lead_type": final_type,
            "ai_response": response
        }
