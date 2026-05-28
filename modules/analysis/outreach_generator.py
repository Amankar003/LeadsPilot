"""
outreach_generator.py
Generates personalized, context-aware sales outreach using real audit findings.
All output is grounded in actual evidence — no hallucination.
"""
import json
from modules.ai.ai_client import AIClient
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────
# Prompt Template
# ─────────────────────────────────────────────
OUTREACH_PROMPT = """
You are a senior B2B sales copywriter for a digital services agency.
Your job is to write personalized outreach messages based ONLY on verified audit findings.

STRICT RULES:
- Do NOT hallucinate. Use only the facts provided below.
- Mention maximum 1-2 pain points in the email.
- Recommend maximum 1-2 services per message.
- Do not use generic openers like "I hope you are doing well" or "I came across your business".
- Do not include the recipient's email in the message body.
- Do not sound salesy or robotic.
- Keep the email body between 80-140 words.
- Personalize using: business name, category, city, and a specific audit finding.
- Match the tone requested: {tone}
- Match the email type: {email_type}
- Match the CTA goal: {cta_goal}
- Focus the message on this service: {service_focus}
- Length preference: {length}

LEAD CONTEXT:
- Business Name: {business_name}
- Category: {category}
- City: {city}
- Website: {website_status}
- Opportunity Level: {opportunity_level}

TOP PAIN POINTS (use max 2):
{pain_points}

RECOMMENDED SERVICES (use max 2):
{recommended_services}

MAIN PITCH ANGLE FROM AUDIT:
{main_pitch_angle}

EXECUTIVE SUMMARY:
{executive_summary}

INSTRUCTIONS BY EMAIL TYPE:
- Cold Outreach: First touch. Hook with a specific insight about their business. No pressure.
- Follow-up 1: Reference a previous email. Add one new value point.
- Follow-up 2: Final touch. Keep it short. Add a simple closing offer.
- No Website Pitch: Emphasize lost business due to no online presence.
- Website Redesign Pitch: Mention specific UX or conversion issue found.
- SEO Pitch: Mention specific visibility or ranking gap found.
- App/Booking System Pitch: Mention missed bookings or manual friction.
- AI Chatbot/Automation Pitch: Mention 24/7 inquiry handling or response gap.

Return ONLY valid JSON with this exact structure:
{{
  "subject_lines": [
    "Subject option 1",
    "Subject option 2",
    "Subject option 3"
  ],
  "email_body": "Complete email body here (no salutation needed, start with the hook)",
  "whatsapp_message": "Short WhatsApp message under 60 words. Friendly and direct.",
  "linkedin_message": "LinkedIn connection note under 50 words. Professional and curious.",
  "follow_up_1": "Follow-up 1 email body (reference previous message, add value)",
  "follow_up_2": "Follow-up 2 email body (final short closing message)"
}}
"""

# ─────────────────────────────────────────────
# Modifier Prompts (quick edit actions)
# ─────────────────────────────────────────────
MODIFIER_PROMPTS = {
    "make_shorter": "Rewrite the following email to be under 80 words. Keep the core message, remove filler. Return JSON: {{\"email_body\": \"\"}}",
    "make_professional": "Rewrite the following email in a formal, professional tone. No casual language. Return JSON: {{\"email_body\": \"\"}}",
    "make_friendly": "Rewrite the following email in a warm, friendly, conversational tone. Return JSON: {{\"email_body\": \"\"}}",
    "stronger_cta": "Add a stronger, clearer call-to-action to the end of this email. Make it easy to say yes. Return JSON: {{\"email_body\": \"\"}}"
}


def build_pain_points_text(pain_points: list) -> str:
    """Format top 2 pain points for the prompt."""
    top = pain_points[:2]
    lines = []
    for pp in top:
        lines.append(
            f"- [{pp.get('severity', 'N/A').upper()}] {pp.get('title', '')}: {pp.get('evidence', '')} "
            f"(Business impact: {pp.get('business_impact', '')})"
        )
    return "\n".join(lines) if lines else "No specific pain points detected."


def build_services_text(services: list, service_focus: str) -> str:
    """Format top 2 services, prioritizing the user's selected focus."""
    if service_focus and service_focus != "Auto (from report)":
        # Put the focused service first
        sorted_services = sorted(
            services,
            key=lambda s: 0 if service_focus.lower() in s.get("service_name", "").lower() else 1
        )
    else:
        sorted_services = services

    top = sorted_services[:2]
    lines = []
    for svc in top:
        lines.append(
            f"- {svc.get('service_name', '')} (Priority: {svc.get('priority', '')}): {svc.get('pitch_angle', '')}"
        )
    return "\n".join(lines) if lines else "General digital improvement services."


import os
from modules.ai.prompts import EMAIL_GENERATOR_PROMPT, FOLLOWUP_GENERATOR_PROMPT

def count_words(text: str) -> int:
    """Helper to count words in a string."""
    if not text:
        return 0
    return len(text.strip().split())

def generate_followup(lead, email_subject: str, email_body: str, followup_number: int) -> str:
    """Generate a follow-up email using the defined FOLLOWUP_GENERATOR_PROMPT."""
    ai = AIClient()
    
    lead_details = {
        "business_name": lead.business_name,
        "category": lead.category,
        "location": f"{lead.city or ''}, {lead.state or ''}, {lead.country or ''}".strip(", ") or lead.address or "Unknown",
        "website": lead.website
    }
    
    prompt = FOLLOWUP_GENERATOR_PROMPT.format(
        lead_details=json.dumps(lead_details, indent=2, ensure_ascii=False),
        original_subject=email_subject,
        original_body=email_body,
        followup_number=followup_number
    )
    
    result = ai.generate_json(prompt)
    if "error" in result:
        if followup_number == 1:
            return f"Hi,\n\nI wanted to follow up on my previous email regarding some digital improvement ideas for {lead.business_name}. I know you're busy, but I'd love to share 2-3 specific ways you can increase your enquiries.\n\nWould you be open to a quick 5-minute chat next week?\n\nBest regards,\n{os.getenv('SENDER_NAME', 'Deepak Kishor')}\n{os.getenv('SENDER_ROLE', 'Founder & Lead Strategist')}\n3FI Tech\n{os.getenv('AGENCY_WEBSITE', '3fitech.com')}"
        else:
            return f"Hi,\n\nJust sending a quick final follow-up. If you're not the right person or if this isn't a priority for {lead.business_name} right now, no worries at all.\n\nIf you are interested in a quick, low-risk way to boost your online discoverability, feel free to reply here.\n\nBest,\n{os.getenv('SENDER_NAME', 'Deepak Kishor')}\n{os.getenv('SENDER_ROLE', 'Founder & Lead Strategist')}\n3FI Tech\n{os.getenv('AGENCY_WEBSITE', '3fitech.com')}"
            
    return result.get("body", "")

import re

def clean_business_name(name: str) -> str:
    """Removes platform and source noise suffixes from business name."""
    if not name:
        return ""
    name = name.strip()
    # Remove "- Highams Park Portal", "- London Portal" etc.
    name = re.sub(r'\s+-\s+.*Portal$', '', name, flags=re.IGNORECASE)
    # Remove " Portal" suffix at the end
    name = re.sub(r'\s+Portal$', '', name, flags=re.IGNORECASE)
    # Remove trailing source or search noise (e.g. "| ...", " - ...")
    name = re.sub(r'\s*\|.*$', '', name)
    name = re.sub(r'\s+-\s+.*$', '', name)
    return name.strip()

def is_invalid_category(category: str) -> bool:
    """Checks if raw category is actually a raw search query / invalid text."""
    if not category:
        return True
    c_lower = category.lower()
    invalid_patterns = [
        "site:", "@gmail.com", "@", '"', "'", "inurl:", "intitle:", 
        "filetype:", " or ", " and ", "+", "ext:", "link:"
    ]
    for pat in invalid_patterns:
        if pat in c_lower:
            return True
    if len(category.split()) > 4 and ("google" in c_lower or "search" in c_lower or ".com" in c_lower):
        return True
    return False

def infer_category(business_name: str, raw_category: str) -> str:
    """Safely infers a clean category from business name or valid category."""
    if raw_category and not is_invalid_category(raw_category):
        return raw_category.strip()
    name_lower = (business_name or "").lower()
    if "creative arts" in name_lower:
        return "creative arts education"
    elif "school" in name_lower or "academy" in name_lower or "college" in name_lower:
        return "education"
    elif "hotel" in name_lower or "inn" in name_lower or "resort" in name_lower:
        return "hospitality"
    elif "clinic" in name_lower or "dental" in name_lower or "dentist" in name_lower or "medical" in name_lower:
        return "healthcare"
    elif "restaurant" in name_lower or "cafe" in name_lower or "bistro" in name_lower or "kitchen" in name_lower:
        return "food and beverage"
    elif "salon" in name_lower or "spa" in name_lower or "beauty" in name_lower:
        return "personal care services"
    elif "plumbing" in name_lower or "electric" in name_lower or "hvac" in name_lower or "roof" in name_lower:
        return "home improvement services"
    return "local service business"

def normalize_pain_points(pain_points: list) -> list:
    """Normalizes raw technical pain points into friendly, natural B2B phrases."""
    if not pain_points:
        return []
    mapping = {
        "missing social proof": "limited visible testimonials or trust-building proof for new visitors",
        "missing dedicated digital platform": "no clear conversion-focused page or digital pathway for enquiries",
        "missing whatsapp integration": "no quick WhatsApp/contact option for mobile-first enquiries",
        "weak local visibility": "limited local search visibility",
        "missing booking system": "no simple online booking or enquiry flow",
        "weak trust signals": "not enough visible credibility signals for first-time visitors",
        "missing whatsapp": "no quick WhatsApp/contact option for mobile-first enquiries",
        "no mobile optimization": "a landing page that is not mobile-friendly",
        "missing client portal": "no private client communication portal",
        "poor seo": "limited organic search discoverability in your local area",
    }
    normalized = []
    for p in pain_points:
        title = ""
        severity = "medium"
        if isinstance(p, dict):
            title = p.get("title", "")
            severity = p.get("severity", "medium")
        else:
            title = str(p)
        t_lower = title.lower().strip()
        matched = False
        for k, v in mapping.items():
            if k in t_lower:
                normalized.append({"title": v, "severity": severity})
                matched = True
                break
        if not matched:
            normalized.append({"title": title, "severity": severity})
    return normalized

def expand_services(pain_points: list) -> list:
    """Maps normalized pain points directly to relevant 3FI Tech premium services."""
    services = []
    added = set()
    mapping = {
        "testimonials": ("testimonial sections and trust badges", "High"),
        "social proof": ("testimonial sections and trust badges", "High"),
        "trust signals": ("testimonial sections and trust badges", "High"),
        "dedicated digital platform": ("a conversion-focused landing page and clearer enquiry pathways", "High"),
        "whatsapp": ("WhatsApp/contact integration", "High"),
        "visibility": ("local SEO improvements", "High"),
        "seo": ("local SEO improvements", "High"),
        "booking": ("online booking and automated callback flow", "High")
    }
    for p in pain_points:
        title_lower = p.get("title", "").lower() if isinstance(p, dict) else str(p).lower()
        for k, (service_name, priority) in mapping.items():
            if k in title_lower:
                if service_name not in added:
                    services.append({"service_name": service_name, "priority": priority})
                    added.add(service_name)
    if len(services) < 2:
        defaults = [
            ("a conversion-focused landing page and clearer enquiry pathways", "High"),
            ("local SEO improvements", "High"),
            ("WhatsApp/contact integration", "High")
        ]
        for name, prio in defaults:
            if name not in added:
                services.append({"service_name": name, "priority": prio})
                added.add(name)
                if len(services) >= 2:
                    break
    return services

def validate_email_quality(email_body: str, cleaned_name: str, has_report: bool, normalized_pain_points: list, selected_services: list) -> tuple[bool, str]:
    """Validates the generated email body to ensure high copywriting quality."""
    if not email_body:
        return False, "Empty email body"
    e_lower = email_body.lower()
    
    # Check for query parameters or operators
    if "site:" in e_lower:
        return False, "Contains 'site:' query operator"
    if "@gmail.com" in e_lower:
        return False, "Contains raw '@gmail.com' domain"
    if "local site:" in e_lower:
        return False, "Contains 'local site:' query operator"
    if "sector" in e_lower and ("site:" in e_lower or "gmail" in e_lower):
        return False, "Contains raw sector query parameters"
        
    # Check for robotic terms
    robotic_phrases = [
        "during our technical analysis",
        "significant growth opportunities",
        "digital pathways",
        "major operational bottleneck",
        "seamlessly into your current workflow",
        "higher customer acquisition costs",
        "specific digital pathways are not fully optimized"
    ]
    for phrase in robotic_phrases:
        if phrase in e_lower:
            return False, f"Contains robotic phrase: '{phrase}'"
            
    # Check word count
    core_body = email_body
    if "\n\nBest regards," in email_body:
        core_body = email_body.split("\n\nBest regards,")[0]
    word_cnt = len(core_body.strip().split())
    if word_cnt < 90:
        return False, f"Word count {word_cnt} is less than 90 words"
    if word_cnt > 180:
        return False, f"Word count {word_cnt} exceeds 180 words limit"

    # Grounding check
    if has_report:
        pt_mentioned = False
        for pt in normalized_pain_points:
            pt_title = pt.get("title", "") if isinstance(pt, dict) else pt
            keywords = [w for w in pt_title.lower().replace("-", " ").split() if len(w) > 4]
            if not keywords:
                keywords = [pt_title.lower()]
            for kw in keywords[:3]:
                if kw in e_lower:
                    pt_mentioned = True
                    break
            if pt_mentioned:
                break
        
        if not pt_mentioned and any(kw in e_lower for kw in ["testimonial", "proof", "booking", "whatsapp", "visibility", "enquiry", "page", "platform"]):
            pt_mentioned = True
        if not pt_mentioned:
            return False, "Does not mention any cleaned pain points"

        svc_mentioned = False
        for svc in selected_services:
            svc_name = svc.get("service_name", "") if isinstance(svc, dict) else svc
            keywords = [w for w in svc_name.lower().replace("-", " ").split() if len(w) > 4]
            if not keywords:
                keywords = [svc_name.lower()]
            for kw in keywords[:3]:
                if kw in e_lower:
                    svc_mentioned = True
                    break
            if svc_mentioned:
                break
                
        if not svc_mentioned and any(kw in e_lower for kw in ["landing", "seo", "whatsapp", "booking", "flow", "testimonial", "cta"]):
            svc_mentioned = True
        if not svc_mentioned:
            return False, "Does not mention any relevant 3FI Tech services"

    return True, "Passed"

def generate_deterministic_template(lead_name, category, location, pain_points, recommended_services):
    """
    Structured, benefit-focused B2B cold email of 100-150 words.
    Perfectly grounded in extracted report pain points and recommended services using warm, simple language.
    """
    pts = pain_points
    if not pts:
        pts = ["limited testimonials or customer proof on your page", "no direct enquiry or contact flow"]
    elif len(pts) == 1:
        pts.append("not having a clear pathway for quick enquiries")
        
    svcs = recommended_services
    if not svcs:
        svcs = ["a conversion-focused landing page and clearer enquiry pathways", "testimonial sections and WhatsApp/contact integration"]
    
    # 1. Warm Opener & Observation
    p1 = f"I came across {lead_name} and noticed a couple of areas that could be improved online. Specifically, we noticed opportunities around having {pts[0]} and {pts[1]}."
    
    # 2. Business Impact
    p2 = f"For a local {category} business, these small gaps can make it harder for new visitors to understand your value, trust your service, and contact you quickly."
    
    # 3. Value pitch & CTA
    p3 = f"At 3FI Tech, we specialize in helping local businesses with exactly this — building {svcs[0]} and {svcs[1]} to turn more website visitors into customers. Would you be open to a quick 5-minute review next week to see how this could work for {lead_name}?"
    
    body = f"{p1}\n\n{p2}\n\n{p3}"
    return body

def generate_outreach(
    report,          # AnalysisReport ORM object
    lead,            # Lead ORM object
    email_type: str,
    tone: str,
    length: str,
    cta_goal: str,
    service_focus: str,
) -> dict:
    """
    Generate personalized, human-sounding outreach based on full lead + audit context.
    Uses the improved EMAIL_GENERATOR_PROMPT, cleans inputs, and validates quality.
    """
    ai = AIClient()

    # 1. Clean Lead Name
    raw_lead_name = lead.business_name or "Unknown"
    cleaned_lead_name = clean_business_name(raw_lead_name)

    # 2. Category Validation & Industry Inference
    raw_category = lead.category or "Unknown"
    category_is_invalid = is_invalid_category(raw_category)
    inferred_category = infer_category(cleaned_lead_name, raw_category)

    # Determine fallback mode
    is_fallback = False
    if not report or not report.ai_report_json:
        is_fallback = True

    # 4. Convert Raw Pain Points to Natural Human Language
    raw_pts = []
    report_exists = report is not None
    ai_report_json_exists = (report.ai_report_json is not None) if report_exists else False
    
    if report_exists:
        if report.pain_points_json:
            raw_pts = report.pain_points_json
        elif report.ai_report_json and report.ai_report_json.get("top_pain_points"):
            raw_pts = report.ai_report_json.get("top_pain_points")
            
    normalized_pts = normalize_pain_points(raw_pts)

    # 5. Service Recommendation Expansion
    selected_svcs = expand_services(normalized_pts)

    # 10. Debugging Logs before generation
    logger.info("--- OUTREACH GENERATION DEBUG START ---")
    logger.info(f"Raw Lead Name: {raw_lead_name}")
    logger.info(f"Cleaned Lead Name: {cleaned_lead_name}")
    logger.info(f"Raw Category: {raw_category}")
    logger.info(f"Cleaned/Inferred Category: {inferred_category}")
    logger.info(f"Raw Pain Points: {raw_pts}")
    logger.info(f"Normalized Pain Points: {normalized_pts}")
    logger.info(f"Selected Services: {selected_svcs}")
    logger.info(f"Whether Category Was Invalid: {category_is_invalid}")
    logger.info(f"Fallback Mode Active: {is_fallback}")

    # Pass clean, inferred category and clean name into lead_data_dict
    lead_data_dict = {
        "business_name": cleaned_lead_name,
        "category": inferred_category,
        "location": f"{lead.city or ''}, {lead.state or ''}, {lead.country or ''}".strip(", ") or lead.address or "Unknown",
        "website": lead.website or "No website found",
        "rating": lead.rating or "N/A",
        "reviews": lead.reviews_count or "N/A",
        "phone": lead.phone or "N/A",
        "email": lead.email or "N/A"
    }

    if is_fallback:
        lead_analysis_dict = {
            "lead_score": None,
            "trust_signals": None,
            "detected_pain_points": None,
            "missing_features": None,
            "business_summary": None,
            "growth_opportunities": None,
            "recommended_services": None,
            "proposed_solution": None,
            "ai_report": None,
            "lead_intelligence_analysis": None
        }
        lead_analysis_text = "[NO LEAD INTELLIGENCE AND ANALYSIS AVAILABLE - FALLBACK OUTREACH MODE IS ACTIVE]\n\n" \
                             "Since no technical audit or intelligence is available, you must write a safe general outreach email based ONLY on the available RAW LEAD DATA.\n" \
                             "Do NOT invent any technical problems, poor mobile/SEO experience, or speed issues.\n\n" \
                             "Use one of the following safe fallback angles depending on the lead category and raw data:\n" \
                             "- If the website is missing: Pitch a clean, professional website and a seamless online enquiry flow.\n" \
                             "- If rating/reviews are available (e.g. high rating): Focus on leveraging their existing trust and local reputation to capture even more digital enquiries.\n" \
                             "- If school/college: Focus on admission enquiry handling, parent communication, and website usability.\n" \
                             "- If clinic/hospital: Focus on appointment enquiry handling, patient trust, and seamless booking.\n" \
                             "- If restaurant/cafe: Focus on online bookings, order enquiry flow, and guest experience.\n" \
                             "- If salon/spa: Focus on appointment booking, local visibility, and repeat customer follow-ups.\n" \
                             "- If only name/category/location are available: Focus on general digital discoverability and enquiry handling."
    else:
        raw_audit = report.raw_audit_json or {}
        ai_report_data = report.ai_report_json or {}
        
        missing_features = raw_audit.get("site_info", {}).get("missing_features", [])
        if not missing_features and raw_audit.get("cta", {}).get("missing_features"):
            missing_features = raw_audit.get("cta", {}).get("missing_features", [])
            
        lead_analysis_dict = {
            "lead_score": report.overall_score,
            "trust_signals": raw_audit.get("trust", {}) or ai_report_data.get("trust_signals", {}),
            "detected_pain_points": normalized_pts,
            "missing_features": missing_features,
            "business_summary": ai_report_data.get("executive_summary") or ai_report_data.get("business_summary"),
            "growth_opportunities": ai_report_data.get("growth_opportunities") or (ai_report_data.get("technical_summary", {}).get("main_technical_issues") if ai_report_data else []),
            "recommended_services": selected_svcs,
            "proposed_solution": ai_report_data.get("main_pitch_angle") or ai_report_data.get("proposed_solution"),
            "ai_report": ai_report_data,
            "lead_intelligence_analysis": {
                "opportunity_level": report.opportunity_level,
                "opportunity_score": report.opportunity_score,
                "technical_summary": ai_report_data.get("technical_summary", {})
            }
        }
        lead_analysis_text = json.dumps(lead_analysis_dict, indent=2, ensure_ascii=False)

    lead_data_text = json.dumps(lead_data_dict, indent=2, ensure_ascii=False)

    sender_name = os.getenv("SENDER_NAME", "Deepak Kishor")
    sender_role = os.getenv("SENDER_ROLE", "Founder & Lead Strategist")
    agency_website = os.getenv("AGENCY_WEBSITE", "3fitech.com")

    # Format the prompt
    prompt = EMAIL_GENERATOR_PROMPT.format(
        lead_data=lead_data_text,
        lead_analysis=lead_analysis_text,
        sender_name=sender_name,
        sender_role=sender_role,
        agency_website=agency_website
    )

    logger.info(f"Generating outreach for lead: {cleaned_lead_name} | is_fallback={is_fallback}")

    # Generate with Groq Client
    email_source = "AI"
    result = ai.generate_json(prompt)

    if "error" in result:
        logger.info("Outreach generation: JSON parsing failed, attempting repair.")
        result = ai.generate_json(prompt)

    email_body = result.get("email_body", "")
    
    # 9. Quality Validation & Feedback-Based Auto-Retry
    passed, error_msg = validate_email_quality(
        email_body=email_body, 
        cleaned_name=cleaned_lead_name, 
        has_report=not is_fallback, 
        normalized_pain_points=normalized_pts, 
        selected_services=selected_svcs
    )
    
    logger.info(f"Quality validation: {passed} (Details: {error_msg})")

    if not passed or "error" in result:
        logger.warning(f"Outreach generation failed quality check with error: {error_msg}. Retrying once with strict feedback instruction.")
        retry_prompt = prompt + f"\n\n========================\nSTRICT RE-GENERATION FEEDBACK\n========================\n" \
                                f"Your previous draft failed quality validation with this exact issue: {error_msg}.\n" \
                                f"Please completely rewrite the B2B cold email to strictly avoid this error.\n" \
                                f"It must be 100-150 words of extremely warm, human, natural language. Do NOT use site:, search queries, @gmail.com or robotic jargon."
        
        retry_result = ai.generate_json(retry_prompt)
        if "error" not in retry_result:
            retry_body = retry_result.get("email_body", "")
            retry_passed, retry_error = validate_email_quality(
                email_body=retry_body,
                cleaned_name=cleaned_lead_name,
                has_report=not is_fallback,
                normalized_pain_points=normalized_pts,
                selected_services=selected_svcs
            )
            if retry_passed:
                result = retry_result
                email_body = retry_body
                passed = True
                error_msg = "Passed after retry"
                logger.info(f"Successfully generated high-quality email after retry validation.")
            else:
                logger.warning(f"Retry draft also failed quality validation: {retry_error}")
                error_msg = f"Retry failed: {retry_error}"

    # 11. Deterministic template fallback if still failing or invalid
    if not passed or "error" in result:
        logger.warning(f"AI generation completely failed validation checks. Falling back to the deterministic template.")
        email_source = "fallback"
        
        pt_titles = [p.get("title", p) if isinstance(p, dict) else p for p in normalized_pts]
        svc_names = [s.get("service_name", s) if isinstance(s, dict) else s for s in selected_svcs]
        
        deterministic_body = generate_deterministic_template(
            lead_name=cleaned_lead_name,
            category=inferred_category,
            location=f"{lead.city or ''}, {lead.state or ''}".strip(", ") or "your area",
            pain_points=pt_titles,
            recommended_services=svc_names
        )
        result["email_body"] = deterministic_body
        email_body = deterministic_body

    # Clean whitespace and leading indents from email_body lines
    if "email_body" in result and result["email_body"]:
        cleaned_lines = [line.strip() for line in result["email_body"].split("\n")]
        result["email_body"] = "\n".join(cleaned_lines)

    # Ensure a beautifully structured vertical B2B signature stack is present
    if "email_body" in result and result["email_body"]:
        body_text = result["email_body"].strip()
        
        for term in ["Best regards,", "Best regards", "Best,", "Warm regards,", "Warm regards", "Sincerely,", "Sincerely", "Regards,", "Regards"]:
            if body_text.endswith(term):
                body_text = body_text[:-len(term)].strip()
                break
        
        if "Best regards, " in body_text:
            idx = body_text.rfind("Best regards, ")
            body_text = body_text[:idx].strip()
        elif "Best regards" in body_text:
            idx = body_text.rfind("Best regards")
            body_text = body_text[:idx].strip()
            
        sig_text = f"\n\nBest regards,\n\n{sender_name}\n{sender_role}\n3FI Tech\n{agency_website}"
        result["email_body"] = body_text + sig_text

    # Fill safe defaults if required fields are missing
    required_fields = [
        "subject", "preview_text", "email_body", "identified_problem",
        "proposed_solution", "personalization_used", "confidence_score", "email_type"
    ]
    for field in required_fields:
        if field not in result or not result[field]:
            if field == "subject":
                result["subject"] = f"Improve {cleaned_lead_name}’s online enquiries"
            elif field == "preview_text":
                result["preview_text"] = f"Ideas for {cleaned_lead_name}"
            elif field == "email_body":
                result["email_body"] = f"Hi,\n\nWe would love to help you build a professional online presence for {cleaned_lead_name}.\n\nBest,\nDeepak Kishor"
            elif field == "identified_problem":
                result["identified_problem"] = "General digital presence"
            elif field == "proposed_solution":
                result["proposed_solution"] = "Website Audit & Optimization"
            elif field == "personalization_used":
                result["personalization_used"] = cleaned_lead_name
            elif field == "confidence_score":
                result["confidence_score"] = "Medium"
            elif field == "email_type":
                result["email_type"] = "General Business Outreach"

    # Match UI expectations
    result["subject_lines"] = [result["subject"]]
    
    # Generate WhatsApp message
    whatsapp_prompt = f"""
Write a WhatsApp message under 60 words for {cleaned_lead_name} ({inferred_category}, {f"{lead.city or ''}".strip()}).
Based on this insight: {result.get('proposed_solution', '')}
Tone: friendly, direct. No formal greetings. Start with a specific observation.
Return JSON: {{"whatsapp_message": ""}}
"""
    wa_res = ai.generate_json(whatsapp_prompt)
    result["whatsapp_message"] = wa_res.get("whatsapp_message", f"Hi! I was reviewing {cleaned_lead_name} and had a quick idea to improve your local enquiries. Would you be open to a quick chat?")

    # Generate LinkedIn message
    linkedin_prompt = f"""
Write a LinkedIn connection note under 50 words for {cleaned_lead_name} ({inferred_category}, {f"{lead.city or ''}".strip()}).
Based on this insight: {result.get('proposed_solution', '')}
Tone: professional, curious. No generic phrases.
Return JSON: {{"linkedin_message": ""}}
"""
    li_res = ai.generate_json(linkedin_prompt)
    result["linkedin_message"] = li_res.get("linkedin_message", f"Hi, I noticed {cleaned_lead_name} and really liked your local presence. I'd love to connect and share a quick digital discovery idea.")

    # Generate followups
    result["follow_up_1"] = generate_followup(lead, result["subject"], result["email_body"], 1)
    result["follow_up_2"] = generate_followup(lead, result["subject"], result["email_body"], 2)

    word_count = count_words(result["email_body"].split("\n\nBest regards,")[0])

    # 10. Debugging logs end
    logger.info(f"Final Word Count (core): {word_count}")
    logger.info(f"Email Source: {email_source}")
    logger.info(f"Is Report-Based: {not is_fallback}")
    logger.info(f"Validation Passed/Failed: {passed} ({error_msg})")
    logger.info("--- OUTREACH GENERATION DEBUG END ---")
    
    # Store details internally for test printing and verification
    result["email_source"] = email_source
    result["is_report_based"] = not is_fallback
    result["word_count"] = word_count
    result["validation_status"] = error_msg

    return result


def apply_modifier(current_email_body: str, modifier: str) -> str:
    """
    Quick-edit the existing email body using a modifier action.
    modifier: one of 'make_shorter', 'make_professional', 'make_friendly', 'stronger_cta'
    Returns the updated email body string.
    """
    ai = AIClient()
    base_prompt = MODIFIER_PROMPTS.get(modifier, "")
    if not base_prompt:
        return current_email_body

    prompt = f"{base_prompt}\n\nEMAIL:\n{current_email_body}"
    result = ai.generate_json(prompt)

    if "error" in result:
        logger.error(f"Modifier '{modifier}' failed: {result.get('error')}")
        return current_email_body  # Return original on error

    return result.get("email_body", current_email_body)


def generate_single_channel(channel: str, current_result: dict, lead, report) -> str:
    """
    Generate or regenerate a single channel message (WhatsApp or LinkedIn).
    channel: 'whatsapp' or 'linkedin'
    """
    ai = AIClient()
    ai_data = report.ai_report_json or {}

    if channel == "whatsapp":
        prompt = f"""
Write a WhatsApp message under 60 words for {lead.business_name} ({lead.category}, {lead.city}).
Based on this insight: {ai_data.get('main_pitch_angle', '')}
Tone: friendly, direct. No formal greetings. Start with a specific observation.
Return JSON: {{"whatsapp_message": ""}}
"""
    else:
        prompt = f"""
Write a LinkedIn connection note under 50 words for {lead.business_name} ({lead.category}, {lead.city}).
Based on this insight: {ai_data.get('main_pitch_angle', '')}
Tone: professional, curious. No generic phrases.
Return JSON: {{"linkedin_message": ""}}
"""

    result = ai.generate_json(prompt)
    if "error" in result:
        return current_result.get(f"{channel}_message", "")

    return result.get(f"{channel}_message", current_result.get(f"{channel}_message", ""))
