import json
from groq import Groq
from utils.logging_utils import get_logger
from config.settings import GROQ_API_KEY, GROQ_MODEL

logger = get_logger(__name__)

class AIClient:
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.model = GROQ_MODEL
        
        if not self.api_key:
            logger.error("GROQ_API_KEY is not set.")
            self.client = None
        else:
            self.client = Groq(api_key=self.api_key)

    def generate_json(self, prompt: str) -> dict:
        if not self.client:
            return {"error": "AI not configured"}
            
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that responds only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Groq AI generation failed: {error_msg}")
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                return {"error": "QUOTA_EXHAUSTED", "details": error_msg}
            return {"error": error_msg}

    def generate_text(self, prompt: str) -> str:
        if not self.client:
            return ""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Groq AI generation failed: {error_msg}")
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                return "ERROR_QUOTA_EXHAUSTED"
            return ""
