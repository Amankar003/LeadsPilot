def calculate_lead_score(lead_data: dict, ai_adjustment: int = 0) -> int:
    score = 0
    
    # rule-based score
    if lead_data.get('has_email'):
        score += 20
    if lead_data.get('has_phone'):
        score += 10
    if lead_data.get('has_website'):
        score += 5
        
    # good rating
    rating = lead_data.get('rating')
    try:
        if rating and float(rating) >= 4.0:
            score += 15
    except:
        pass
        
    # high reviews
    reviews_count = lead_data.get('reviews_count')
    try:
        if reviews_count and int(str(reviews_count).replace(',', '')) > 50:
            score += 10
    except:
        pass
        
    score += ai_adjustment
    
    # clamp
    score = max(0, min(100, score))
    return score

def determine_lead_type(score: int) -> str:
    if score >= 80:
        return "HOT"
    elif score >= 60:
        return "WARM"
    elif score >= 40:
        return "COLD"
    else:
        return "LOW"
