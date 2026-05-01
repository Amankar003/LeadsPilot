import os
import json
from google import genai
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class AIClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        
        if not self.api_key:
            logger.error("GEMINI_API_KEY is not set.")
            self.client = None
        else:
            self.client = genai.Client(api_key=self.api_key)

    def generate_json(self, prompt: str) -> dict:
        if not self.client:
            return {"error": "AI not configured"}
            
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"AI generation failed: {str(e)}")
            return {"error": str(e)}

    def generate_text(self, prompt: str) -> str:
        if not self.client:
            return ""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"AI generation failed: {str(e)}")
            return ""
