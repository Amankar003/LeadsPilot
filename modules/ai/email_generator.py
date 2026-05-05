import json
import re
import logging
import time
import random
from typing import Dict, Any
from modules.ai.ai_client import AIClient
from modules.ai.prompts import EMAIL_GENERATOR_PROMPT, FOLLOWUP_GENERATOR_PROMPT

# Set up logging
logger = logging.getLogger(__name__)

def normalize_lead_for_email(lead: dict) -> dict:
    """
    Safely maps different possible field names into a clean structure.
    Also truncates large fields to save tokens.
    """
    normalized = {
        "business_name": (lead.get("business_name") or lead.get("name") or lead.get("title") or lead.get("company") or ""),
        "category": (lead.get("category") or lead.get("business_category") or lead.get("industry") or lead.get("type") or ""),
        "location": (lead.get("location") or lead.get("address") or lead.get("city") or ""),
        "website": (lead.get("website") or lead.get("site") or lead.get("url") or ""),
        "phone": (lead.get("phone") or lead.get("mobile") or lead.get("contact") or ""),
        "email": (lead.get("email") or ""),
        "rating": (lead.get("rating") or lead.get("stars") or ""),
        "reviews": (lead.get("reviews") or lead.get("review_count") or ""),
        "description": (lead.get("description") or lead.get("snippet") or lead.get("summary") or ""),
        "source": (lead.get("source") or lead.get("platform") or ""),
    }
    
    # Truncate description to save tokens
    if normalized["description"] and len(normalized["description"]) > 300:
        normalized["description"] = normalized["description"][:300] + "..."
        
    # Ensure all values are strings and convert None to empty string
    for key, value in normalized.items():
        if value is None:
            normalized[key] = ""
        else:
            normalized[key] = str(value)
            
    # Include original data but filtered/cleaned to avoid huge blobs
    # We remove known large fields that shouldn't go to LLM
    clean_raw = {}
    if isinstance(lead, dict):
        for k, v in lead.items():
            if k.lower() in ['html', 'page_content', 'raw_html', 'text', 'content']:
                continue
            if isinstance(v, str) and len(v) > 500:
                clean_raw[k] = v[:500] + "..."
            else:
                clean_raw[k] = v
    normalized["raw_data_summary"] = clean_raw
            
    return normalized

def lead_to_prompt_json(lead: dict) -> str:
    """
    Converts normalized lead to a formatted JSON string for the prompt.
    """
    normalized = normalize_lead_for_email(lead)
    return json.dumps(normalized, indent=2, ensure_ascii=False)

def extract_json_response(text: str) -> dict:
    """
    Robust JSON extraction from LLM response.
    """
    # Fallback dictionary
    fallback = {
        "subject": "Quick idea for your online enquiries",
        "preview_text": "A simple digital improvement could make customer enquiries easier.",
        "email_body": "Hi Team,\n\nI came across your business details and noticed there may be an opportunity to make it easier for new customers to discover and contact you online.\n\nAt 3FI Tech, we help businesses build clean websites, enquiry flows, WhatsApp-first contact systems, and simple automation that can improve how customer enquiries are captured and followed up.\n\nWould you be open to a quick suggestion on how this could be improved for your business?\n\nBest regards,\nAman\nAI/ML Engineer\n3FI Tech",
        "identified_problem": "The available data is limited or AI generation could not be completed.",
        "proposed_solution": "Improve digital presence and enquiry flow with a website, WhatsApp CTA, or lead capture system.",
        "personalization_used": "Used fallback template due to limited data or service availability.",
        "confidence_score": "Low",
        "email_type": "General Business Outreach"
    }

    if not text or not isinstance(text, str):
        return fallback
        
    if text == "ERROR_QUOTA_EXHAUSTED":
        logger.warning("AI quota exceeded. Using fallback email.")
        fallback["personalization_used"] = "Fallback email used because AI generation was unavailable (Quota Exceeded)."
        return fallback

    try:
        # Try direct parsing
        return json.loads(text)
    except Exception:
        try:
            # Extract first JSON object using regex
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            logger.warning("JSON parsing failed, using fallback.")
            
    return fallback

class EmailGenerator:
    def __init__(self):
        self.ai = AIClient()
        self.quota_hit = False

    def generate_draft(self, lead_data: dict, insights: dict = None, service_focus: str = "", sender: dict = None) -> dict:
        """
        Generates a personalized cold outreach email for a business lead.
        Includes throttling and quota management.
        """
        if sender is None:
            sender = {}
            
        business_name = lead_data.get("business_name") or lead_data.get("name") or "Business"
        
        # If we already hit quota in this run, return fallback immediately
        if self.quota_hit:
            logger.info(f"Skipping AI for {business_name} (Quota already hit). Using fallback.")
            return extract_json_response("ERROR_QUOTA_EXHAUSTED")

        logger.info(f"Generating email for: {business_name}")

        try:
            # Normalize and convert to JSON for prompt
            lead_json = lead_to_prompt_json(lead_data)
            
            # Format prompt using the new flexible structure
            prompt = EMAIL_GENERATOR_PROMPT.format(
                lead_data=lead_json,
                sender_name=sender.get("sender_name", "Aman"),
                sender_role=sender.get("sender_role", "AI/ML Engineer"),
                agency_website=sender.get("agency_website", "https://3fitech.com")
            )
            
            # Throttling: random sleep to avoid RPM limits (2-4 seconds)
            wait_time = random.uniform(2.0, 4.0)
            time.sleep(wait_time)
            
            # Get response from AI
            raw_response = self.ai.generate_text(prompt)
            
            if raw_response == "ERROR_QUOTA_EXHAUSTED":
                self.quota_hit = True
                return extract_json_response(raw_response)
                
            result = extract_json_response(raw_response)
            
            # Map email_body to body/email for backward compatibility
            if "email_body" in result:
                result["body"] = result["email_body"]
                result["email"] = result["email_body"]
            
            # Ensure essential keys exist
            if "subject" not in result: result["subject"] = "Quick Question"
            if "body" not in result: result["body"] = "Hi,\n\nI noticed your business and thought we could help you grow."
            
            logger.info(f"Email generation successful for {business_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating email for {business_name}: {str(e)}")
            return extract_json_response("")

    def generate_followup(self, lead_data: dict, original_subject: str, original_body: str, followup_number: int) -> dict:
        """
        Generates a polite follow-up email.
        """
        try:
            prompt = FOLLOWUP_GENERATOR_PROMPT.format(
                lead_details=json.dumps(lead_data, indent=2),
                original_subject=original_subject,
                original_body=original_body,
                followup_number=followup_number
            )
            
            # Throttling
            time.sleep(2)
            
            raw_response = self.ai.generate_text(prompt)
            
            if raw_response == "ERROR_QUOTA_EXHAUSTED":
                return {
                    "subject": f"Re: {original_subject}",
                    "body": "Hi, just floating this to the top of your inbox. Let me know if you have any questions.\n\nIf this is not relevant, you can reply 'unsubscribe' and I won't follow up."
                }
                
            response = extract_json_response(raw_response)
            
            if "error" in response or "subject" not in response:
                raise ValueError("Invalid AI response")
                
            return response
        except Exception as e:
            logger.warning(f"Follow-up generation failed: {str(e)}")
            return {
                "subject": f"Re: {original_subject}",
                "body": "Hi, just floating this to the top of your inbox. Let me know if you have any questions.\n\nIf this is not relevant, you can reply 'unsubscribe' and I won't follow up."
            }
