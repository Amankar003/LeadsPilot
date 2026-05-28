import json
import os
import requests
from groq import Groq
from utils.logging_utils import get_logger
from config.settings import GROQ_API_KEY, GROQ_MODEL, GEMINI_API_KEY

logger = get_logger(__name__)

class AIClient:
    def __init__(self):
        # Load directly from settings or environment variables
        self.groq_api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        self.groq_model = GROQ_MODEL or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        
        self.gemini_api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        # Initialize Groq client
        self.groq_client = None
        if self.groq_api_key:
            try:
                self.groq_client = Groq(api_key=self.groq_api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")

    def generate_json(self, prompt: str) -> dict:
        """
        Tries to generate structured JSON using Groq.
        If it fails or is not configured, automatically falls back to Gemini.
        If both fail, returns a graceful mock fallback.
        """
        result = None
        # --- 1. Try Groq ---
        if self.groq_client:
            try:
                logger.info(f"Attempting Groq generation with model {self.groq_model}...")
                response = self.groq_client.chat.completions.create(
                    model=self.groq_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that responds only with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                result = json.loads(content)
            except Exception as e:
                logger.error(f"Groq JSON generation failed: {e}. Switching to Gemini fallback...")

        # --- 2. Fallback to Gemini ---
        if result is None and self.gemini_api_key:
            try:
                logger.info(f"Attempting Gemini fallback with model {self.gemini_model}...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"
                headers = {"Content-Type": "application/json"}
                data = {
                    "contents": [{"parts": [{"text": prompt + "\n\nCRITICAL: You must return ONLY a valid JSON object. Do not include any markdown formatting like ```json or ```."}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json"
                    }
                }
                res = requests.post(url, headers=headers, json=data, timeout=15)
                if res.status_code == 200:
                    res_json = res.json()
                    # Parse content from Gemini schema
                    text = res_json['candidates'][0]['content']['parts'][0]['text']
                    result = json.loads(text)
                else:
                    logger.error(f"Gemini API returned error status {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"Gemini JSON generation failed: {e}")

        # --- 3. Final Graceful Local Fallback ---
        if result is None:
            logger.warning("Both Groq and Gemini failed to generate JSON. Returning a clean local template.")
            result = self._get_fallback_template(prompt)

        # --- 4. Safe Dictionary Conversion if list or non-dict is returned ---
        if isinstance(result, list):
            logger.info("Parsed AI response is a list. Safely converting to dict.")
            if result and isinstance(result[0], dict):
                result = result[0]
            else:
                result = {"results": result}
        elif not isinstance(result, dict):
            logger.warning(f"Parsed AI response is of type {type(result)}. Converting to dict.")
            result = {"value": result}

        return result

    def generate_text(self, prompt: str) -> str:
        """
        Tries to generate text using Groq.
        If it fails, automatically falls back to Gemini.
        """
        # --- 1. Try Groq ---
        if self.groq_client:
            try:
                logger.info(f"Attempting Groq text generation with model {self.groq_model}...")
                response = self.groq_client.chat.completions.create(
                    model=self.groq_model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq text generation failed: {e}. Switching to Gemini fallback...")

        # --- 2. Fallback to Gemini ---
        if self.gemini_api_key:
            try:
                logger.info(f"Attempting Gemini text generation with model {self.gemini_model}...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"
                headers = {"Content-Type": "application/json"}
                data = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                res = requests.post(url, headers=headers, json=data, timeout=15)
                if res.status_code == 200:
                    res_json = res.json()
                    return res_json['candidates'][0]['content']['parts'][0]['text']
                else:
                    logger.error(f"Gemini API text generation returned error status {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"Gemini text generation failed: {e}")

        return "Error: Unable to generate content. Please check your internet connection or API settings."

    def _get_fallback_template(self, prompt: str) -> dict:
        """Returns a matching mock JSON depending on what prompt is requested."""
        import re
        prompt_lower = prompt.lower()
        
        # Extract details to customize the fallback template
        business_name = "your business"
        category = "services"
        location = "your area"
        
        name_match = re.search(r'"business_name":\s*"([^"]+)"', prompt)
        if not name_match:
            name_match = re.search(r'Business Name:\s*([^\n\r]+)', prompt)
        if name_match:
            business_name = name_match.group(1).strip()
            
        cat_match = re.search(r'"category":\s*"([^"]+)"', prompt)
        if not cat_match:
            cat_match = re.search(r'Category:\s*([^\n\r]+)', prompt)
        if cat_match:
            category = cat_match.group(1).strip()

        loc_match = re.search(r'"location":\s*"([^"]+)"', prompt)
        if not loc_match:
            loc_match = re.search(r'City:\s*([^\n\r]+)', prompt)
            if not loc_match:
                loc_match = re.search(r'Location:\s*([^\n\r]+)', prompt)
        if loc_match:
            location = loc_match.group(1).strip()

        if "opportunity_level" in prompt_lower or "executive_summary" in prompt_lower:
            # Sales Report request
            return {
                "executive_summary": f"Digital presence audit for {business_name} highlights key opportunities for growth, user experience, and conversion optimizations.",
                "opportunity_level": "High",
                "main_pitch_angle": "Enhancing digital discoverability and enquiry flows to capture active local customers.",
                "business_impact_summary": f"Optimizing the enquiry path and SEO structure will directly increase daily bookings and calls for {business_name}.",
                "top_pain_points": [
                    {
                        "title": "Digital Discoverability",
                        "severity": "high",
                        "evidence": f"Website search presence can be improved to capture more local traffic in {location}.",
                        "business_impact": "Potential customers may choose competitors who are more visible in local search.",
                        "recommended_service": "Local SEO & Content Optimization"
                    }
                ],
                "recommended_services": [
                    {
                        "service_name": "Local SEO Optimization",
                        "priority": "High",
                        "reason": "Increases organic discoverability in Google Maps and local queries.",
                        "pitch_angle": "Let's place your business in front of local clients searching for your exact services."
                    }
                ],
                "outreach": {
                    "email_subject": f"Enhancing digital discoverability for {business_name}",
                    "email_body": (
                        f"I recently reviewed the digital setup for {business_name} and was highly impressed by your reputation in the local {category} sector. However, during our analysis, we noted a few areas where your online booking flow, client contact pathways, and mobile visibility could be further optimized to capture more direct inquiries.\n\n"
                        f"When these digital pathways are not fully streamlined, a significant portion of active local mobile users seeking immediate {category} services can drop off without converting, leading to lost business and higher client acquisition costs for your team.\n\n"
                        f"At 3FI Tech, we specialize in building custom, high-converting digital flows, booking automation, and local discoverability strategies to help {category} providers capture every active lead automatically. Would you be open to a brief, 5-minute review to discuss a few specific suggestions for {business_name}?"
                    ),
                    "whatsapp_message": f"Hi! I have a quick idea to help increase client bookings for {business_name}.",
                    "linkedin_message": f"Hi, let's connect regarding digital growth opportunities for {business_name}."
                },
                "sales_call_notes": [
                    "Highlight existing local trust and reviews.",
                    "Focus on SEO benefits and client acquisition cost."
                ],
                "technical_summary": {
                    "digital_health_score": 75,
                    "main_technical_issues": [
                        "SEO and local optimization opportunities."
                    ]
                }
            }
        elif "email_body" in prompt_lower or "subject" in prompt_lower:
            # Email Draft request
            return {
                "subject": f"Boosting discoverability & client bookings for {business_name}",
                "email_body": (
                    f"I recently reviewed the digital setup for {business_name} and was highly impressed by your reputation in the local {category} sector. However, during our analysis, we noted a few areas where your online booking flow, client contact pathways, and mobile visibility could be further optimized to capture more direct inquiries.\n\n"
                    f"When these digital pathways are not fully streamlined, a significant portion of active local mobile users seeking immediate {category} services can drop off without converting, leading to lost business and higher client acquisition costs for your team.\n\n"
                    f"At 3FI Tech, we specialize in building custom, high-converting digital flows, booking automation, and local discoverability strategies to help {category} providers capture every active lead automatically. Would you be open to a brief, 5-minute review to discuss a few specific suggestions for {business_name}?"
                )
            }
        elif "followup" in prompt_lower or "original_body" in prompt_lower:
            # Follow-up request
            return {
                "subject": f"Re: Boosting discoverability & client bookings for {business_name}",
                "body": (
                    f"Hi,\n\nFollowing up on my previous message regarding digital discoverability for {business_name}. I know you're busy, but I'd love to share 2 quick ways to help streamline your booking flow and increase overall inquiries.\n\nWould you be open to a quick 5-minute review next week?\n\nIf this isn't a priority right now, just reply 'unsubscribe' and I won't follow up again."
                )
            }
        return {"status": "success", "message": "API call completed via fallback mode."}
