import streamlit as st

def render_opportunity_card(opp_data: dict, score: int = None):
    """
    Renders the unified Opportunity Intelligence Card context.
    
    Args:
        opp_data: Dictionary containing opportunity details
                  (e.g., category, region, country, trend_summary, opportunity_reason, target_service, suggested_offer)
        score: Score out of 100
    """
    if score is None:
        score = opp_data.get('score', 0)
        
    score_color = "green" if score >= 80 else ("orange" if score >= 60 else "red")
    
    st.markdown(f"""
    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 10px; background-color: #fcfcfc;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h4 style="margin: 0; color: #1e3a8a;">💼 {opp_data.get('category', 'Opportunity')} in {opp_data.get('region') or opp_data.get('country', 'Unknown')}</h4>
            <span style="background-color: {score_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                Score: {score}/100
            </span>
        </div>
        <p style="margin-top: 10px; font-size: 14px;"><strong>Target Pitch Service:</strong> <span style="background-color: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-size: 12px;">{opp_data.get("target_service", "Not specified")}</span></p>
        <p style="font-size: 14px; color: #475569;"><strong>Market Trend Summary:</strong> {opp_data.get('trend_summary', opp_data.get('why_this_region', ''))}</p>
        <p style="font-size: 14px; color: #475569;"><strong>Opportunity Reason:</strong> {opp_data.get('opportunity_reason', opp_data.get('why_this_sector', ''))}</p>
        <p style="font-size: 14px; font-weight: 500; color: #0f172a;"><strong>Suggested Offer:</strong> {opp_data.get('suggested_offer', opp_data.get('recommended_service', ''))}</p>
    </div>
    """, unsafe_allow_html=True)
