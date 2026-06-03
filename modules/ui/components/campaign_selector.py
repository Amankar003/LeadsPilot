import streamlit as st
from modules.database.repositories import CampaignRepository
from modules.dork_optimizer.service import DorkOptimizerService
from modules.ui.components.campaign_creator import create_campaign_modal

def render_campaign_selector(db, service: DorkOptimizerService, selected_dork_ids: list, opp_id: str):
    """
    Renders the campaign selection dropdown, creation button, and dispatch button.
    
    Args:
        db: Database session.
        service: Instance of DorkOptimizerService for dispatching.
        selected_dork_ids: List of dork IDs to send.
        opp_id: Unique string to namespace keys.
    """
    st.markdown("##### ⚙️ Target Campaign Selection")
    
    campaign_repo = CampaignRepository(db)
    campaigns = campaign_repo.get_all() or []
    
    sc1, sc2 = st.columns([2, 1])
    with sc1:
        if campaigns:
            # Select the newly created campaign if present
            default_index = 0
            new_id = st.session_state.get("newly_created_campaign_id")
            if new_id:
                for i, c in enumerate(campaigns):
                    if c.id == new_id:
                        default_index = i
                        break
                        
            selected_camp = st.selectbox(
                "Select Target Campaign",
                options=[c.id for c in campaigns],
                format_func=lambda x: next(c.campaign_name for c in campaigns if c.id == x),
                index=default_index,
                key=f"camp_sel_{opp_id}"
            )
        else:
            selected_camp = None
            st.info("No campaigns exist. Create one to continue.")
            
        if st.button("➕ Create New Campaign", key=f"create_camp_btn_{opp_id}"):
            create_campaign_modal(db)
            
    with sc2:
        st.write("") # Spacing
        st.write("") # Spacing
        if selected_camp and st.button("Send Dorks to Campaign", key=f"send_btn_{opp_id}", use_container_width=True, type="primary"):
            if not selected_dork_ids:
                st.warning("Please select at least one dork query.")
            else:
                with st.spinner("Pushing job to database worker..."):
                    try:
                        scraper_res = service.send_dorks_to_scraper(selected_dork_ids, selected_camp)
                        st.success(f"✓ {len(selected_dork_ids)} dorks sent to campaign! Job {scraper_res['job_id']} queued.")
                    except Exception as e:
                        st.error(f"Failed to queue scraping job: {e}")
