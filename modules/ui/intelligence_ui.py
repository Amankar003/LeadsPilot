import streamlit as st
import pandas as pd
from utils.logging_utils import get_logger
from config.database import SessionLocal
from modules.database.models import Campaign, ScrapingJob, Lead, Dork, AnalysisJob, AnalysisReport
from modules.analysis.job_processor import queue_analysis_job, get_job_status, get_report
from modules.database.repositories import EmailDraftRepository, LeadRepository, DorkRepository, JobRepository, CampaignRepository
from modules.ui.theme import page_header, empty_state, make_dataframe_arrow_compatible

logger = get_logger(__name__)

def render_analysis_dashboard():
    page_header("🧠", "Lead Intelligence & Analysis", "Analyze leads, find pain points, and generate targeted AI outreach.")
    
    db = SessionLocal()
    try:
        # -----------------------------
        # Quick Analyze: add business names and analyze
        # -----------------------------
        with st.expander("➕ Quick Analyze — add business names and run analysis", expanded=False):
            st.write("Paste one business name per line. A campaign will be created and each name saved as a lead and queued for analysis.")
            q_campaign_name = st.text_input("Campaign Name", "Quick Analysis Campaign", key="q_campaign_name")
            q_category = st.text_input("Category", "General Business", key="q_category")
            q_location = st.text_input("Location (optional)", "", key="q_location")
            q_names = st.text_area("Business Names (one per line)", key="q_names")
            q_analyze = st.checkbox("🔬 Analyze after adding", value=True, key="q_analyze")

            if st.button("Add & Analyze Now", key="q_add_analyze"):
                names = [n.strip() for n in str(q_names or "").splitlines() if n.strip()]
                if not q_campaign_name:
                    st.error("Please enter a campaign name for the quick analysis.")
                elif not names:
                    st.error("Please paste at least one business name.")
                else:
                    try:
                        from utils.hash_utils import generate_lead_hash

                        # Create Campaign
                        campaign = CampaignRepository(db).create(
                            campaign_name=q_campaign_name,
                            platform="manual_analysis",
                            category=q_category,
                            location=q_location or "",
                            status="COMPLETED"
                        )

                        # Create mock completed ScrapingJob
                        job = ScrapingJob(
                            campaign_id=campaign.id,
                            platform="manual_analysis",
                            category=q_category,
                            location=q_location or "",
                            status="COMPLETED",
                            total_scraped=len(names),
                            total_saved=0
                        )
                        db.add(job)
                        db.flush()

                        saved_ids = []
                        for n in names:
                            lead_hash = generate_lead_hash(n, None, None, q_location or "")
                            existing = db.query(Lead).filter(Lead.campaign_id == campaign.id, Lead.lead_hash == lead_hash).first()
                            if existing:
                                continue
                            lead_obj = Lead(
                                campaign_id=campaign.id,
                                scraping_job_id=job.id,
                                business_name=n,
                                category=q_category,
                                phone=None,
                                email=None,
                                website=None,
                                address=None,
                                city=q_location or None,
                                source="manual_analysis",
                                has_email=False,
                                has_phone=False,
                                has_website=False,
                                lead_hash=lead_hash,
                                status="NEW_LEAD"
                            )
                            db.add(lead_obj)
                            db.flush()
                            saved_ids.append(lead_obj.id)

                        job.total_saved = len(saved_ids)
                        db.commit()

                        queued = 0
                        if q_analyze and saved_ids:
                            for lid in saved_ids:
                                try:
                                    if queue_analysis_job(db, lid):
                                        queued += 1
                                except Exception as queue_err:
                                    logger.warning(f"Failed to queue analysis job for lead {lid}: {queue_err}")

                        st.success(f"Added {len(saved_ids)} leads to campaign '{q_campaign_name}' and queued {queued} for analysis.")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Failed to add leads: {e}")
        # Load campaigns
        campaigns = CampaignRepository(db).get_all()
        if not campaigns:
            empty_state("📋", "No Campaigns", "Create a campaign and scrape some leads first.")
            return

        camp_options = {c.id: c.campaign_name for c in campaigns}
        selected_camp_id = st.selectbox(
            "🎯 Select Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="intel_campaign"
        )
        # -----------------------------
        # Dork Overview & Actions
        # -----------------------------
        try:
            dork_repo = DorkRepository(db)
            dorks = dork_repo.get_by_campaign_id(selected_camp_id) or []
            total_dorks = len(dorks)
            pending_count = dork_repo.count_by_status(selected_camp_id, 'pending') or 0
            scraped_count = dork_repo.count_by_status(selected_camp_id, 'scraped') or 0
            failed_count = dork_repo.count_by_status(selected_camp_id, 'failed') or 0

            st.markdown("##### 📥 Saved Dorks")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Dorks", total_dorks)
            c2.metric("Pending", pending_count)
            c3.metric("Scraped", scraped_count)
            c4.metric("Failed", failed_count)

            if total_dorks:
                df_d = pd.DataFrame([{
                    "Dork": d.dork_text,
                    "Status": d.status,
                    "Source": d.source_file or "",
                    "Added": getattr(d, 'created_at', '')
                } for d in dorks])
                st.dataframe(make_dataframe_arrow_compatible(df_d), hide_index=True)

            if st.button("Start Scraping Using Saved Dorks", key="start_scraping_dorks"):
                pending = dork_repo.get_pending_by_campaign_id(selected_camp_id)
                if not pending:
                    st.info("No pending dorks to scrape for this campaign.")
                else:
                    import threading

                    pending_snapshot = [{"id": d.id, "dork_text": d.dork_text} for d in pending]

                    def run_pending_dorks(campaign_id, snapshot):
                        tdb = SessionLocal()
                        try:
                            from modules.jobs.scraping_planner import ScrapingPlanner
                            from modules.database.repositories import JobRepository, DorkRepository as _DorkRepo
                            from modules.database.models import ScrapingJob
                            from utils.constants import PLATFORM_SERPER_BULK

                            job_repo = JobRepository(tdb)
                            campaign_repo = CampaignRepository(tdb)
                            local_dork_repo = _DorkRepo(tdb)
                            planner = ScrapingPlanner(tdb)

                            campaign = campaign_repo.get_by_id(campaign_id)
                            for item in snapshot:
                                try:
                                    # Create a job for this single dork
                                    job = job_repo.create(
                                        campaign_id=campaign_id,
                                        platform=PLATFORM_SERPER_BULK,
                                        category=item.get("dork_text", ""),
                                        location=(campaign.location or ""),
                                        status="PENDING",
                                        total_scraped=0,
                                        total_saved=0
                                    )

                                    # Execute scraping for this job (will save leads)
                                    planner.execute_job(job.id)

                                    # Refresh job counts
                                    refreshed = tdb.query(ScrapingJob).filter(ScrapingJob.id == job.id).first()
                                    if refreshed and getattr(refreshed, 'total_saved', 0) > 0:
                                        local_dork_repo.update_status(item.get("id"), 'scraped')
                                    else:
                                        local_dork_repo.update_status(item.get("id"), 'failed')

                                except Exception:
                                    tdb.rollback()
                                    try:
                                        local_dork_repo.update_status(item.get("id"), 'failed')
                                    except Exception:
                                        pass
                        finally:
                            tdb.close()

                    thread = threading.Thread(target=run_pending_dorks, args=(selected_camp_id, pending_snapshot), daemon=True)
                    thread.start()
                    st.success(f"Started scraping {len(pending_snapshot)} dorks in background. Refresh to see updates.")
                    st.rerun()
        except Exception as dork_err:
            logger.warning(f"Dork module warning: {dork_err}")
        
        # Load leads for campaign
        leads = db.query(Lead).filter(Lead.campaign_id == selected_camp_id).all()
        if not leads:
            empty_state("👥", "No Leads", "No leads found for this campaign.")
            return
            
        # Get job statuses
        jobs = db.query(AnalysisJob).filter(AnalysisJob.lead_id.in_([l.id for l in leads])).all()
        job_map = {j.lead_id: j for j in jobs}
        
        # Filters
        st.markdown("##### Filters")
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            filter_email = st.checkbox("📧 Has Email only", key="intel_filter_email")
        with fc2:
            filter_phone = st.checkbox("📞 Has Phone only", key="intel_filter_phone")
        with fc3:
            filter_website = st.checkbox("🌐 Has Website only", key="intel_filter_website")

        # Build table data
        data = []
        select_top_30 = st.session_state.get("select_top_30", False)
        selected_count = 0
        
        for l in leads:
            # Apply filters
            if filter_email and not l.email:
                continue
            if filter_phone and not l.phone:
                continue
            if filter_website and not l.website:
                continue

            job = job_map.get(l.id)
            status = "Ready"
            if job:
                if job.status == "PENDING": status = "⏳ Queued"
                elif job.status == "RUNNING": status = "🔄 Analyzing"
                elif job.status == "COMPLETED": status = "✅ Report Ready"
                elif job.status == "FAILED": status = "❌ Failed"
                
            is_selected = False
            if select_top_30 and status == "Ready" and selected_count < 30:
                is_selected = True
                selected_count += 1
                
            data.append({
                "Select": is_selected,
                "Lead ID": l.id,
                "Business Name": l.business_name,
                "Email": l.email or "",
                "Phone": l.phone or "",
                "Website": l.website or "",
                "Category": l.category or "",
                "Status": status,
                "CRM State": l.status
            })
            
        if select_top_30:
            st.session_state["select_top_30"] = False
            
        if not data:
            empty_state("👥", "No Matching Leads", "No leads match the selected filters.")
            # Still display the action bar buttons but return early
            col1, col2, col3 = st.columns([1.5, 1, 1.5])
            with col2:
                if st.button("🔄 Refresh Status", use_container_width=True):
                    st.rerun()
            return

        df = pd.DataFrame(data)
        # Ensure 'Select' column is explicitly bool so CheckboxColumn works
        df["Select"] = df["Select"].astype(bool)
        df = make_dataframe_arrow_compatible(df)
        
        st.markdown(f"### 1. Queue Leads for Analysis ({len(df)} leads)")
        st.write("Select leads below and click 'Analyze Selected' to run the deep website audit.")
        
        # Action Bar
        col1, col2, col3 = st.columns([1.5, 1, 1.5])
        
        edited_df = st.data_editor(
            df, hide_index=True, width="stretch",
            column_config={
                "Select": st.column_config.CheckboxColumn("Select for Analysis", default=False),
                "Lead ID": st.column_config.TextColumn("Lead ID", disabled=True),
            },
            disabled=["Business Name", "Email", "Phone", "Website", "Category", "Status", "CRM State"],
            key="intel_editor"
        )
        
        selected_ids_for_analysis = edited_df[edited_df["Select"] == True]["Lead ID"].tolist()
        
        with col1:
            if st.button("🚀 Analyze Selected Leads", type="primary", use_container_width=True):
                if not selected_ids_for_analysis:
                    st.warning("Please select leads to analyze.")
                else:
                    queued = 0
                    for lid in selected_ids_for_analysis:
                        if queue_analysis_job(db, lid):
                            queued += 1
                    if queued > 0:
                        st.success(f"Queued {queued} leads for deep analysis!")
                        st.rerun()
                    else:
                        st.info("Selected leads are already queued or running.")
                        
        with col2:
            if st.button("🔄 Refresh Status", use_container_width=True):
                st.rerun()
                
        with col3:
            if st.button("👉 Select Top 30 Leads", use_container_width=True):
                st.session_state["select_top_30"] = True
                if "intel_editor" in st.session_state:
                    del st.session_state["intel_editor"]
                st.rerun()
                
    except Exception as e:
        db.rollback()
        logger.error(f"Error in render_analysis_dashboard: {e}", exc_info=True)
        st.error(f"⚠️ An error occurred while loading the dashboard: {str(e)}")
        with st.expander("🔍 Show technical details for debugging"):
            st.exception(e)
    finally:
        db.close()

