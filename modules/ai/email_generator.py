from modules.ai.ai_client import AIClient
from modules.ai.prompts import EMAIL_GENERATOR_PROMPT, FOLLOWUP_GENERATOR_PROMPT
import json

class EmailGenerator:
    def __init__(self):
        self.ai = AIClient()

    def generate_draft(self, lead_data: dict, insights: dict, service_focus: str = "") -> dict:
        prompt = EMAIL_GENERATOR_PROMPT.format(
            lead_details=json.dumps(lead_data, indent=2),
            insights=json.dumps(insights, indent=2),
            service_focus=service_focus
        )
        
        response = self.ai.generate_json(prompt)
        
        if "error" in response:
            return {
                "subject": "Quick Question",
                "body": f"Hi,\n\nI noticed {lead_data.get('business_name', 'your business')} and thought we could help you grow.\n\nLet me know if you are open to a quick chat.\n\nIf this is not relevant, you can reply 'unsubscribe' and I won't follow up."
            }
            
        return response

    def generate_followup(self, lead_data: dict, original_subject: str, original_body: str, followup_number: int) -> dict:
        prompt = FOLLOWUP_GENERATOR_PROMPT.format(
            lead_details=json.dumps(lead_data, indent=2),
            original_subject=original_subject,
            original_body=original_body,
            followup_number=followup_number
        )
        
        response = self.ai.generate_json(prompt)
        
        if "error" in response:
            return {
                "subject": f"Re: {original_subject}",
                "body": "Hi, just floating this to the top of your inbox. Let me know if you have any questions.\n\nIf this is not relevant, you can reply 'unsubscribe' and I won't follow up."
            }
            
        return response
