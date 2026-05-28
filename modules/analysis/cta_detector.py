"""
cta_detector.py — Detects CTA elements, conversion signals, and contact methods.
Checks for call/WhatsApp/booking buttons, contact forms, social links, etc.
"""
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# CTA keyword categories
CTA_KEYWORDS = {
    "call": ["call", "call us", "call now", "phone us", "ring us", "give us a call"],
    "contact": ["contact", "contact us", "get in touch", "reach us", "reach out"],
    "book": ["book", "book now", "book online", "book appointment", "booking"],
    "appointment": ["appointment", "schedule", "schedule now", "make appointment"],
    "enquiry": ["enquire", "enquiry", "inquiry", "ask us", "submit enquiry"],
    "quote": ["get quote", "free quote", "request quote", "get estimate", "free estimate"],
    "consultation": ["consultation", "free consultation", "book consultation"],
    "whatsapp": ["whatsapp", "chat on whatsapp", "message us", "wa.me"],
    "demo": ["demo", "book demo", "request demo", "free demo", "live demo"],
    "order": ["order now", "buy now", "shop now", "add to cart", "purchase"],
    "apply": ["apply", "apply now", "register", "sign up", "enroll", "enrol"],
    "reserve": ["reserve", "reserve now", "make reservation"],
}

SOCIAL_PLATFORMS = {
    "facebook": ["facebook.com", "fb.com", "fb.me"],
    "instagram": ["instagram.com"],
    "twitter": ["twitter.com", "x.com"],
    "linkedin": ["linkedin.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "tiktok": ["tiktok.com"],
    "pinterest": ["pinterest.com"],
}


def audit_cta(html: str, url: str) -> dict:
    """
    Detect CTA elements, contact methods, and social links.
    """
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True).lower()

    result = {
        "cta_buttons_found": [],
        "total_cta_count": 0,
        "has_call_button": False,
        "has_contact_button": False,
        "has_whatsapp_link": False,
        "has_booking_button": False,
        "has_enquiry_button": False,
        "has_quote_button": False,
        "has_contact_form": False,
        "has_visible_email": False,
        "visible_emails": [],
        "has_visible_phone": False,
        "visible_phones": [],
        "has_sticky_cta": False,
        "social_links": {},
        "total_social_links": 0,
        "whatsapp_urls": [],
    }

    # ── Scan all links and buttons ──
    clickable = soup.find_all(["a", "button", "input"])

    for el in clickable:
        el_text = el.get_text(strip=True).lower()
        href = (el.get("href") or "").lower()
        el_type = (el.get("type") or "").lower()
        el_value = (el.get("value") or "").lower()

        combined_text = f"{el_text} {href} {el_value}"

        # WhatsApp detection
        if "wa.me" in href or "whatsapp" in href or "api.whatsapp.com" in href:
            result["has_whatsapp_link"] = True
            result["whatsapp_urls"].append(el.get("href", ""))

        # Tel links (call button)
        if href.startswith("tel:"):
            result["has_call_button"] = True
            phone = href.replace("tel:", "").strip()
            if phone and phone not in result["visible_phones"]:
                result["visible_phones"].append(phone)

        # Mailto links
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email and email not in result["visible_emails"]:
                result["visible_emails"].append(email)
                result["has_visible_email"] = True

        # CTA keyword matching
        for cta_type, keywords in CTA_KEYWORDS.items():
            for kw in keywords:
                if kw in combined_text:
                    if cta_type not in [c["type"] for c in result["cta_buttons_found"]]:
                        result["cta_buttons_found"].append({
                            "type": cta_type,
                            "text": el_text[:80],
                            "href": (el.get("href") or "")[:200],
                        })

                    if cta_type == "contact":
                        result["has_contact_button"] = True
                    elif cta_type in ("book", "appointment", "reserve"):
                        result["has_booking_button"] = True
                    elif cta_type in ("enquiry",):
                        result["has_enquiry_button"] = True
                    elif cta_type in ("quote", "consultation"):
                        result["has_quote_button"] = True
                    break

        # Social links
        if el.name == "a" and href:
            for platform, domains in SOCIAL_PLATFORMS.items():
                for d in domains:
                    if d in href and platform not in result["social_links"]:
                        result["social_links"][platform] = el.get("href", "")

    result["total_cta_count"] = len(result["cta_buttons_found"])
    result["total_social_links"] = len(result["social_links"])

    # ── Contact Form Detection ──
    forms = soup.find_all("form")
    for form in forms:
        form_text = form.get_text(strip=True).lower()
        form_action = (form.get("action") or "").lower()
        inputs = form.find_all("input")
        textareas = form.find_all("textarea")

        contact_signals = [
            "name" in form_text or "email" in form_text or "message" in form_text,
            "contact" in form_action or "enquiry" in form_action,
            len(inputs) >= 2 and len(textareas) >= 1,
            any("email" in (inp.get("name", "") + inp.get("type", "")).lower() for inp in inputs),
        ]
        if sum(contact_signals) >= 2:
            result["has_contact_form"] = True
            break

    # ── Email extraction from page text ──
    email_pattern = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    )
    page_emails = email_pattern.findall(page_text)
    for em in page_emails:
        if not any(x in em for x in ["example.com", "domain.com", ".png", ".jpg", ".gif", "wixpress"]):
            if em not in result["visible_emails"]:
                result["visible_emails"].append(em)
                result["has_visible_email"] = True

    # ── Phone extraction from page text ──
    phone_pattern = re.compile(
        r"(?:\+?\d{1,4}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}"
    )
    page_phones = phone_pattern.findall(soup.get_text(separator=" ", strip=True))
    for ph in page_phones:
        cleaned = re.sub(r"[\s\-.]", "", ph)
        if len(cleaned) >= 10 and cleaned not in result["visible_phones"]:
            result["visible_phones"].append(ph.strip())
            result["has_visible_phone"] = True

    # ── Sticky CTA detection (heuristic) ──
    for el in soup.find_all(["div", "nav", "header", "section"]):
        style = (el.get("style") or "").lower()
        classes = " ".join(el.get("class") or []).lower()
        if any(kw in style or kw in classes for kw in ["fixed", "sticky", "float"]):
            inner_text = el.get_text(strip=True).lower()
            if any(kw in inner_text for kw in ["call", "contact", "book", "whatsapp", "enquir"]):
                result["has_sticky_cta"] = True
                break

    return result
