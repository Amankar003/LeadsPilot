import streamlit as st
from datetime import datetime
from modules.database.models import get_or_create_default_user
from modules.database.repositories import CampaignRepository

@st.dialog("Create New Campaign")
def create_campaign_modal(db):
    """
    Renders a modal to create a new campaign and saves it to the database.
    Updates st.session_state["newly_created_campaign_id"] upon success.
    """
    st.markdown("All scraped data must be linked to a campaign.")
    default_name = f"Auto Campaign - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    new_camp_name = st.text_input("Campaign Name", value=default_name)
    new_camp_source = st.selectbox("Source", ["Manual Dork Generator", "Auto Dork Optimizer"])
    
    if st.button("Create & Continue", type="primary"):
        user = get_or_create_default_user(db)
        new_camp = CampaignRepository(db).create(
            user_id=user.id,
            campaign_name=new_camp_name,
            category=new_camp_source,
            location="Global",
            platform="serper_bulk",
            status="PENDING"
        )
        st.session_state["newly_created_campaign_id"] = new_camp.id
        st.rerun()
