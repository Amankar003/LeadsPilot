import json
import os
from groq import Groq
from utils.logging_utils import get_logger
from config import settings

logger = get_logger(__name__)

_GEMINI_QUOTA_EXHAUSTED = False
_GROQ_UNAVAILABLE = False

def get_provider_for_task(task_name: str) -> str:
    task_name = task_name.lower()

    if task_name in ["email_generation", "audit_generation", "pain_points", "executive_report"]:
        return os.getenv("LLM_QUALITY_PROVIDER", "gemini").lower()

    if task_name in ["free_prompt"]:
        return os.getenv("FREE_PROMPT_PROVIDER", os.getenv("LLM_QUALITY_PROVIDER", "gemini")).lower()

    return os.getenv("LLM_FAST_PROVIDER", "groq").lower()

class AIClient:
    def __init__(self):
        # Load directly from settings with a safe fallback
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_model = settings.GROQ_MODEL or "llama-3.1-8b-instant"
        
        global _GROQ_UNAVAILABLE
        self.groq_client = None
        if self.groq_api_key and not _GROQ_UNAVAILABLE:
            try:
                # Set max_retries=2 so Groq SDK automatically handles 429 rate limits with exponential backoff
                self.groq_client = Groq(api_key=self.groq_api_key, max_retries=2)
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")

    def health_check(self) -> dict:
        """
        Tests the Groq API connection.
        Returns a dict with status and message.
        """
        if not self.groq_client:
            return {"status": "error", "message": "Groq API key not configured"}
        try:
            # Send a tiny prompt to verify connectivity and API key validity
            self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            return {"status": "success", "message": "Connected successfully"}
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "unauthorized" in error_str or "invalid" in error_str:
                return {"status": "error", "message": "Invalid Groq API key (401 Unauthorized)"}
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

    def _safe_json_parse(self, content: str) -> dict:
        """Helper to safely parse JSON from string, handling markdown fences."""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing failed: {e}. Raw content: {content}")
            return None

    def get_groq_model_fallbacks(self):
        raw = settings.get_env_var("GROQ_MODEL_FALLBACKS", "")
        if raw and raw.strip():
            return [m.strip() for m in raw.split(",") if m.strip()]
        return [
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
            "openai/gpt-oss-20b",
        ]

    def is_usable_json(self, data):
        if data is None:
            return False
        if isinstance(data, dict):
            if not data:
                return False
            for key in ["trends", "results", "items", "leads", "opportunities", "actionable_trends"]:
                if key in data and data[key]:
                    return True
            return any(value not in [None, "", [], {}] for value in data.values())
        if isinstance(data, list):
            return len(data) > 0
        return False

    def generate_json(self, prompt: str, system_prompt: str = "You are a helpful assistant that responds only with valid JSON.", task_name: str = "default", temperature: float = 0.7, max_tokens: int = 1500) -> dict:
        """
        Generates structured JSON, routing between providers based on task_name.
        If it fails, automatically falls back to other providers or a graceful mock fallback.
        """
        provider = get_provider_for_task(task_name)
        logger.info(f"Selected provider for {task_name}: {provider}")

        providers_to_try = []
        if provider == "gemini":
            providers_to_try = ["gemini", "groq"]
        elif provider == "groq":
            providers_to_try = ["groq", "gemini"] if os.getenv("ENABLE_GEMINI_FALLBACK", "true").lower() == "true" else ["groq"]
        else:
            providers_to_try = ["groq", "gemini"]

        result = None
        last_error = None

        for selected_provider in providers_to_try:
            try:
                if selected_provider == "gemini":
                    global _GEMINI_QUOTA_EXHAUSTED
                    if _GEMINI_QUOTA_EXHAUSTED:
                        logger.warning("Gemini quota was previously exhausted. Skipping Gemini.")
                        continue
                    if not os.getenv("GEMINI_API_KEY"):
                        logger.warning("Gemini selected but GEMINI_API_KEY is missing. Skipping Gemini.")
                        continue
                        
                    from modules.ai.gemini_client import generate_json_with_gemini
                    result = generate_json_with_gemini(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_output_tokens=max_tokens
                    )
                    break

                if selected_provider == "groq":
                    if not self.groq_client:
                        logger.warning("Groq selected but client is not initialized. Skipping Groq.")
                        continue
                        
                    result = self._generate_json_with_groq_fallback(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    break

            except Exception as e:
                error_str = str(e).lower()
                if selected_provider == "gemini":
                    if "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str or "generate_content_free_tier_requests" in error_str:
                        logger.error("Gemini quota exhausted. Skipping Gemini for this task.")
                        _GEMINI_QUOTA_EXHAUSTED = True
                elif selected_provider == "groq":
                    if "401" in error_str or "unauthorized" in error_str or "invalid_api_key" in error_str:
                        logger.error("Groq API Key invalid (401). Disabling Groq for this session.")
                        global _GROQ_UNAVAILABLE
                        _GROQ_UNAVAILABLE = True
                        self.groq_client = None
                    elif "429" in error_str:
                        logger.warning("Groq rate limit hit (429). Retries exhausted.")
                
                last_error = e
                logger.warning(f"{selected_provider} failed for task {task_name}: {e}")
                continue

        # --- 2. Final Graceful Local Fallback ---
        if result is None:
            if last_error:
                logger.error(f"All LLM providers failed for task {task_name}. Last error: {last_error}")
            logger.info("All LLM providers unavailable. Using local fallback.")
            result = self._get_fallback_template(prompt)

        # --- 3. Safe Dictionary Conversion if list or non-dict is returned ---
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

    def _generate_json_with_groq_fallback(self, prompt: str, system_prompt: str, temperature: float, max_tokens: int) -> dict:
        models = self.get_groq_model_fallbacks()
        for model in models:
            try:
                logger.info(f"Trying Groq model: {model}")
                response = self.groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                content = response.choices[0].message.content if response.choices else None
                if not content or not content.strip():
                    logger.warning(f"Groq model returned empty response: {model}")
                    continue
                    
                parsed = self._safe_json_parse(content)
                if parsed is None:
                    logger.warning(f"Groq model returned invalid JSON: {model}")
                    continue
                    
                if not self.is_usable_json(parsed):
                    logger.warning(f"Groq model returned unusable JSON: {model}")
                    continue
                    
                logger.info(f"Groq generation succeeded with model: {model}")
                return parsed
            except Exception as e:
                error_str = str(e).lower()
                if "401" in error_str or "unauthorized" in error_str or "invalid_api_key" in error_str:
                    logger.error("Groq API Key invalid (401). Disabling Groq for this session.")
                    global _GROQ_UNAVAILABLE
                    _GROQ_UNAVAILABLE = True
                    self.groq_client = None
                    raise e
                logger.warning(f"Groq model failed: {model} | {e}")
                continue
        raise RuntimeError("All Groq models failed to generate valid JSON.")

    def generate_text(self, prompt: str, system_prompt: str = None, task_name: str = "default", temperature: float = 0.7, max_tokens: int = 1500) -> str:
        """
        Generates text using the routed provider.
        """
        provider = get_provider_for_task(task_name)
        logger.info(f"Selected provider for {task_name}: {provider}")

        providers_to_try = []
        if provider == "gemini":
            providers_to_try = ["gemini", "groq"]
        elif provider == "groq":
            providers_to_try = ["groq", "gemini"] if os.getenv("ENABLE_GEMINI_FALLBACK", "true").lower() == "true" else ["groq"]
        else:
            providers_to_try = ["groq", "gemini"]

        for selected_provider in providers_to_try:
            try:
                if selected_provider == "gemini":
                    global _GEMINI_QUOTA_EXHAUSTED
                    if _GEMINI_QUOTA_EXHAUSTED:
                        logger.warning("Gemini quota was previously exhausted. Skipping Gemini.")
                        continue
                    if not os.getenv("GEMINI_API_KEY"):
                        logger.warning("Gemini selected but GEMINI_API_KEY is missing. Skipping Gemini.")
                        continue
                    from modules.ai.gemini_client import generate_text_with_gemini
                    return generate_text_with_gemini(
                        prompt=prompt,
                        system_prompt=system_prompt or "",
                        temperature=temperature,
                        max_output_tokens=max_tokens
                    )
                
                if selected_provider == "groq":
                    if not self.groq_client:
                        logger.warning("Groq selected but client is not initialized. Skipping Groq.")
                        continue
                    return self._generate_text_with_groq_fallback(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
            except Exception as e:
                error_str = str(e).lower()
                if selected_provider == "gemini":
                    if "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str or "generate_content_free_tier_requests" in error_str:
                        logger.error("Gemini quota exhausted. Skipping Gemini for this task.")
                        _GEMINI_QUOTA_EXHAUSTED = True
                elif selected_provider == "groq":
                    if "401" in error_str or "unauthorized" in error_str or "invalid_api_key" in error_str:
                        logger.error("Groq API Key invalid (401). Disabling Groq for this session.")
                        global _GROQ_UNAVAILABLE
                        _GROQ_UNAVAILABLE = True
                        self.groq_client = None
                    elif "429" in error_str:
                        logger.warning("Groq rate limit hit (429). Retries exhausted.")
                logger.warning(f"{selected_provider} failed for task {task_name}: {e}")
                continue

        logger.info("All LLM providers unavailable. Using local fallback.")
        return "Error: Unable to generate content. Please check your internet connection or API settings."

    def _generate_text_with_groq_fallback(self, prompt: str, system_prompt: str, temperature: float, max_tokens: int) -> str:
        models = self.get_groq_model_fallbacks()
        for model in models:
            try:
                logger.info(f"Trying Groq text generation with model {model}...")
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = self.groq_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                content = response.choices[0].message.content if response.choices else None
                if not content or not content.strip():
                    logger.warning(f"Groq model returned empty response: {model}")
                    continue
                    
                logger.info(f"Groq text generation succeeded with model: {model}")
                return content
            except Exception as e:
                error_str = str(e).lower()
                if "401" in error_str or "unauthorized" in error_str or "invalid_api_key" in error_str:
                    logger.error("Groq API Key invalid (401). Disabling Groq for this session.")
                    global _GROQ_UNAVAILABLE
                    _GROQ_UNAVAILABLE = True
                    self.groq_client = None
                    raise e
                logger.warning(f"Groq model failed: {model} | {e}")
                continue
        raise RuntimeError("All Groq models failed to generate text.")

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
                    "subject": f"Enhancing digital discoverability for {business_name}",
                    "preview_text": f"Quick ideas to capture more direct inquiries for {business_name}.",
                    "email_body": (
                        f"Hi there,\n\n"
                        f"While reviewing {category} providers in {location}, I took a look at the digital setup for {business_name}.\n\n"
                        f"I noticed a specific missed opportunity regarding your online booking flow and client contact pathways. When these pathways are not fully streamlined, potential clients can drop off without converting, leading to missed local enquiries.\n\n"
                        f"A few practical improvements could help:\n"
                        f"- Improve local search visibility — so nearby customers can find the business faster.\n"
                        f"- Add a clear enquiry or booking flow — so website visitors know exactly how to take the next step.\n"
                        f"- Set up automated follow-ups — so potential customers do not get missed after the first enquiry.\n\n"
                        f"At 3Fi Tech, we provide these services by improving lead capture flows, local visibility, and customer follow-up systems to help businesses like yours capture every active lead.\n\n"
                        f"Would it be useful if we shared a complimentary audit report highlighting the highest-impact opportunities we identified?"
                    )
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
                "preview_text": f"Quick ideas to capture more direct inquiries for {business_name}.",
                "email_body": (
                    f"Hi there,\n\n"
                    f"While reviewing {category} providers in {location}, I took a look at the digital setup for {business_name}.\n\n"
                    f"I noticed a specific missed opportunity regarding your online booking flow and client contact pathways. When these pathways are not fully streamlined, potential clients can drop off without converting, leading to missed local enquiries.\n\n"
                    f"A few practical improvements could help:\n"
                    f"- Improve local search visibility — so nearby customers can find the business faster.\n"
                    f"- Add a clear enquiry or booking flow — so website visitors know exactly how to take the next step.\n"
                    f"- Set up automated follow-ups — so potential customers do not get missed after the first enquiry.\n\n"
                    f"At 3Fi Tech, we provide these services by improving lead capture flows, local visibility, and customer follow-up systems to help businesses like yours capture every active lead.\n\n"
                    f"Would it be useful if we shared a complimentary audit report highlighting the highest-impact opportunities we identified?"
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
