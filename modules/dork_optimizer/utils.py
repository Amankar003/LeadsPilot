import os
import json
import re
from config.settings import (
    LLM_PROVIDER,
    GROQ_API_KEY,
    TREND_MODEL,
    DORK_MODEL,
)

import os
from dotenv import load_dotenv

load_dotenv()

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "")

TARGET_COUNTRIES = ["India", "UAE", "Saudi Arabia", "UK", "USA", "Australia", "Canada", "Singapore", "Qatar"]

SECTOR_KEYWORDS = {
    "real estate": ["real estate", "property market", "property investment"],
    "tourism": ["tourism", "hotel booking", "travel industry"],
    "healthcare": ["healthcare", "medical clinic", "dental clinic"],
    "ecommerce": ["ecommerce", "online shopping", "shopify"],
    "ai digital transformation": ["digital transformation", "AI business", "automation"],
    "manufacturing": ["manufacturing", "industrial growth", "factory"],
    "education": ["education technology", "training institute"],
    "b2b services": ["business services", "consulting firm"],
    "wedding events": ["wedding planner", "event organizer"],
}

SERVICES_LIST = [
    "Website Development",
    "Website Redesign",
    "Landing Page Development",
    "Local SEO",
    "Google Business Profile Optimization",
    "Booking Website / Booking System",
    "WhatsApp Automation",
    "AI Chatbot",
    "CRM Automation",
    "Lead Generation System",
    "Portfolio Website",
    "Travel/Hotel Package Website",
    "Real Estate Property Website",
    "B2B Product Catalog Website",
    "Shopify SEO",
    "Ecommerce Conversion Optimization",
    "Email Marketing Automation",
]

API_KEY = GROQ_API_KEY

_client = None

def _get_client():
    global _client
    if _client is None:
        if not API_KEY:
            raise ValueError("GROQ_API_KEY not set in .env")

        from groq import Groq
        _client = Groq(api_key=API_KEY)
    return _client

def call_llm(prompt: str, system_prompt: str = None, model: str = None, temperature: float = 0.3) -> str:
    try:
        client = _get_client()
    except Exception as e:
        return f'{{"error": "{str(e)}"}}'

    model_name = model or TREND_MODEL

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        return completion.choices[0].message.content or ""
    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "unauthorized" in err_str.lower() or "invalid api key" in err_str.lower():
            return '{"error": "401 Unauthorized - Invalid Groq API Key"}'
        return f'{{"error": "{err_str}"}}'

call_gemini = call_llm

def extract_json_from_response(response: str):
    if not response:
        return {"error": "Empty response"}

    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        pass

    fence = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```", response, re.IGNORECASE)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except (json.JSONDecodeError, TypeError):
            pass

    for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
        match = re.search(pattern, response)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                pass

    return {"error": "Failed to parse JSON", "raw": response[:300]}
