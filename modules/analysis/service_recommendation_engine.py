"""
service_recommendation_engine.py - Maps pain points to 3FI Tech services.
"""

# Map of service to reasons and pitch angles
SERVICE_MAP = {
    "Website Development": {
        "reason": "The business lacks a professional web presence.",
        "pitch_angle": "We can build a fast, mobile-friendly website that acts as your 24/7 sales engine."
    },
    "Website Redesign": {
        "reason": "The current website is outdated or not mobile-friendly.",
        "pitch_angle": "A modern, responsive redesign will keep mobile users on your site and improve brand trust."
    },
    "Technical SEO": {
        "reason": "Missing critical SEO tags is hurting search visibility.",
        "pitch_angle": "Fixing your technical SEO will help you rank higher on Google without paying for ads."
    },
    "CTA & Conversion Optimization": {
        "reason": "The website has traffic but no clear way to capture leads.",
        "pitch_angle": "We can add clear contact flows to turn your existing website visitors into actual inquiries."
    },
    "WhatsApp Integration": {
        "reason": "Missing a modern, low-friction contact method.",
        "pitch_angle": "Adding a one-click WhatsApp button can instantly increase the number of messages you get from mobile users."
    },
    "Speed Optimization": {
        "reason": "The site loads too slowly, causing users to bounce.",
        "pitch_angle": "We can optimize your site speed so customers don't leave before seeing what you offer."
    },
    "Security Hardening": {
        "reason": "Missing basic security like HTTPS kills user trust.",
        "pitch_angle": "Securing your site prevents browser warnings and protects your customer data."
    },
    "Mobile App Development": {
        "reason": "High potential for customer retention via an app.",
        "pitch_angle": "A custom app can streamline your bookings/orders and build direct loyalty with your customers."
    },
    "Appointment Booking System & Customer App": {
        "reason": "Service business without a dedicated scheduling flow.",
        "pitch_angle": "Automating your bookings will save you hours of admin time and reduce no-shows."
    },
    "Ordering App & Loyalty Program": {
        "reason": "Food/retail business relying on third parties.",
        "pitch_angle": "Get your own ordering platform so you stop paying massive commissions to delivery apps."
    }
}

def generate_recommendations(pain_points: list) -> list:
    """
    Generate service recommendations based on identified pain points.
    """
    recommended = {}
    
    for pp in pain_points:
        service_name = pp.get("recommended_service")
        if not service_name:
            continue
            
        if service_name not in recommended:
            details = SERVICE_MAP.get(service_name, {
                "reason": f"To address: {pp.get('title')}",
                "pitch_angle": f"We can implement {service_name} to resolve issues with {pp.get('type')}."
            })
            
            priority = "High" if pp.get("severity") == "Critical" else "Medium"
            
            recommended[service_name] = {
                "service_name": service_name,
                "priority": priority,
                "reason": details["reason"],
                "pitch_angle": details["pitch_angle"],
                "matching_pain_points": [pp.get("title")]
            }
        else:
            recommended[service_name]["matching_pain_points"].append(pp.get("title"))
            if pp.get("severity") == "Critical":
                recommended[service_name]["priority"] = "High"
                
    # Convert to list and sort by priority
    rec_list = list(recommended.values())
    rec_list.sort(key=lambda x: 0 if x["priority"] == "High" else 1)
    
    return rec_list
