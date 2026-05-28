"""
app_requirement_detector.py - Detects if a business might benefit from an app/portal.
"""
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# Categories that highly benefit from apps/portals
HIGH_APP_POTENTIAL = {
    "salon": ["salon", "spa", "hair", "beauty", "massage", "barber"],
    "health": ["clinic", "doctor", "hospital", "dental", "physio", "medical", "pharmacy"],
    "fitness": ["gym", "fitness", "yoga", "pilates", "crossfit", "personal trainer"],
    "education": ["coaching", "institute", "school", "tutor", "academy", "training"],
    "food": ["restaurant", "cafe", "takeaway", "delivery", "kitchen", "pizza", "bakery"],
    "real_estate": ["real estate", "property", "broker", "realtor", "agent"],
    "home_services": ["plumber", "electrician", "cleaning", "hvac", "pest control", "repair", "handyman"],
    "ecommerce": ["store", "shop", "retail", "boutique", "supermarket"],
    "travel": ["travel", "tour", "hotel", "resort", "booking", "agency"],
}

def detect_app_requirement(category: str, cta_results: dict) -> dict:
    """
    Evaluate if the business has a high potential for an app, portal or booking system.
    """
    result = {
        "app_potential": "Low",
        "primary_reason": "Business type typically does not require dedicated portal/app.",
        "recommended_feature": None
    }
    
    cat = (category or "").lower()
    
    # Check against high-potential categories
    matched_type = None
    for business_type, keywords in HIGH_APP_POTENTIAL.items():
        if any(kw in cat for kw in keywords):
            matched_type = business_type
            break
            
    if matched_type:
        result["app_potential"] = "High"
        
        if matched_type in ["salon", "health", "fitness", "home_services"]:
            result["recommended_feature"] = "Appointment Booking System & Customer App"
            result["primary_reason"] = "Service-based businesses need streamlined scheduling, reminders, and repeat bookings."
            
        elif matched_type in ["food", "ecommerce"]:
            result["recommended_feature"] = "Ordering App & Loyalty Program"
            result["primary_reason"] = "Retail/Food businesses highly benefit from direct ordering apps to avoid third-party commissions."
            
        elif matched_type in ["education", "real_estate"]:
            result["recommended_feature"] = "Client Portal / App"
            result["primary_reason"] = "Information-heavy businesses benefit from portals for tracking progress, listings, or documents."
            
    # If they already have a booking button, they might need an upgrade or app
    if cta_results.get("has_booking_button") and result["app_potential"] != "High":
        result["app_potential"] = "Medium"
        result["recommended_feature"] = "Advanced Booking App / Portal"
        result["primary_reason"] = "They currently take bookings. A dedicated app/portal could improve retention."

    return result
