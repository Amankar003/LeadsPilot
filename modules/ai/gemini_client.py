import os
import json
import logging

logger = logging.getLogger(__name__)

GEMINI_AVAILABLE = False
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError as e:
    logger.error(f"Gemini SDK not installed or import failed: {e}")

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

def get_gemini_client():
    if not GEMINI_AVAILABLE:
        return None
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def generate_json_with_gemini(
    prompt: str,
    system_prompt: str = "",
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 2048,
):
    if not GEMINI_AVAILABLE:
        raise RuntimeError("Gemini SDK not installed or import failed.")
    client = get_gemini_client()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    selected_model = model or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    full_prompt = prompt
    if system_prompt:
        full_prompt = f"{system_prompt.strip()}\n\n{prompt.strip()}"

    logger.info(f"Trying Gemini model: {selected_model}")

    response = client.models.generate_content(
        model=selected_model,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
        ),
    )

    content = response.text

    if not content or not content.strip():
        raise ValueError("Gemini returned empty response.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        logger.warning(f"Gemini returned invalid JSON: {error}")
        raise

    logger.info(f"Gemini generation succeeded with model: {selected_model}")
    return parsed

def generate_text_with_gemini(
    prompt: str,
    system_prompt: str = "",
    model: str | None = None,
    temperature: float = 0.4,
    max_output_tokens: int = 2048,
):
    if not GEMINI_AVAILABLE:
        raise RuntimeError("Gemini SDK not installed or import failed.")
    client = get_gemini_client()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    selected_model = model or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    full_prompt = prompt
    if system_prompt:
        full_prompt = f"{system_prompt.strip()}\n\n{prompt.strip()}"

    logger.info(f"Trying Gemini text model: {selected_model}")

    response = client.models.generate_content(
        model=selected_model,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )

    content = response.text

    if not content or not content.strip():
        raise ValueError("Gemini returned empty text response.")

    logger.info(f"Gemini text generation succeeded with model: {selected_model}")
    return content.strip()
