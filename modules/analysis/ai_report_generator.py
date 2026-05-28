"""
ai_report_generator.py - Sends structured audit facts to Groq LLM to generate sales reports.
"""
import json
from modules.ai.ai_client import AIClient
from utils.logging_utils import get_logger

logger = get_logger(__name__)

REPORT_PROMPT = """
You are an AI Sales Analyst for a digital services company.

Your job is to analyze a business lead using only the provided structured audit data and generate a practical sales intelligence report.

You must:
- Identify real business pain points.
- Recommend only relevant services.
- Explain business impact in simple language.
- Create a professional outreach angle.
- Avoid exaggeration and false claims.
- Do not assume anything that is not present in the input.
- If a check was not performed, mark it as "Not verified".
- Do not insult the business or say the website is bad.
- Use soft professional language like "could improve", "may be missing", "there appears to be".
- Focus on how the business can get more inquiries, bookings, trust, visibility, conversions, and automation.

Input data will include:
- business details
- website presence
- audit scores
- SEO findings
- CTA findings
- speed findings
- security findings
- broken link findings
- trust signals
- app requirement signals
- rule-based pain points
- possible services

RAW AUDIT FACTS:
{audit_json}

PAIN POINTS IDENTIFIED BY RULE ENGINE:
{pain_points_json}

RECOMMENDED SERVICES:
{services_json}

Return only valid JSON with exactly this structure:

{{
  "executive_summary": "",
  "opportunity_level": "Very High | High | Medium | Low",
  "main_pitch_angle": "",
  "business_impact_summary": "",
  "top_pain_points": [
    {{
      "title": "",
      "severity": "critical | high | medium | low",
      "evidence": "",
      "business_impact": "",
      "recommended_service": ""
    }}
  ],
  "recommended_services": [
    {{
      "service_name": "",
      "priority": "High | Medium | Low",
      "reason": "",
      "pitch_angle": ""
    }}
  ],
  "outreach": {{
    "email_subject": "",
    "email_body": "",
    "whatsapp_message": "",
    "linkedin_message": ""
  }},
  "sales_call_notes": [
    ""
  ],
  "technical_summary": {{
    "digital_health_score": 0,
    "main_technical_issues": [
      ""
    ]
  }}
}}

Rules:
1. Recommend maximum 3 to 5 services only.
2. Prioritize services that directly match evidence.
3. If website is missing, focus on website development, local SEO, Google Business optimization, WhatsApp CTA, booking system if relevant.
4. If website exists but CTA is weak, recommend CTA/conversion optimization.
5. If SEO is weak, recommend SEO/technical SEO.
6. If business is appointment-based, recommend booking system.
7. If business has repeat customers, recommend app/customer portal only if justified.
8. If security headers are missing, recommend basic security hardening, not full VAPT unless explicitly allowed.
9. Outreach should be short, human, and personalized.
10. Do not include email address inside email body unless explicitly provided as business content.
"""


def generate_ai_report(audit_data: dict, pain_points: list, services: list) -> dict:
    """
    Generate AI sales report from structured audit facts.
    """
    ai = AIClient()
    
    prompt = REPORT_PROMPT.format(
        audit_json=json.dumps(audit_data, indent=2),
        pain_points_json=json.dumps(pain_points, indent=2),
        services_json=json.dumps(services, indent=2)
    )
    
    logger.info("Sending audit facts to Groq AI for report generation...")
    result = ai.generate_json(prompt)
    
    if "error" in result:
        logger.error(f"AI Report generation failed: {result['error']}")
        return {
            "error": "AI Generation Failed",
            "details": result
        }
        
    return result

OUTREACH_PROMPT = """
You are an expert sales copywriter.
Generate a new, alternative outreach message for a business lead based on the following analysis.

EXECUTIVE SUMMARY:
{summary}

MAIN PITCH ANGLE:
{pitch}

Make the email concise, personalized, and focus on the main pitch. Do not include placeholders like [Your Name], leave them generic or omit them.

Return ONLY valid JSON:
{{
  "email_subject": "",
  "email_body": "",
  "whatsapp_message": "",
  "linkedin_message": ""
}}
"""

def regenerate_outreach(ai_report_json: dict) -> dict:
    """Regenerate just the outreach portion based on existing report data."""
    ai = AIClient()
    
    prompt = OUTREACH_PROMPT.format(
        summary=ai_report_json.get("executive_summary", "Unknown"),
        pitch=ai_report_json.get("main_pitch_angle", "Unknown")
    )
    
    result = ai.generate_json(prompt)
    if "error" in result:
        return {}
    return result

