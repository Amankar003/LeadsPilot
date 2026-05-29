import streamlit as st
import pandas as pd
from datetime import datetime
from config.database import SessionLocal
from modules.database.models import Campaign, Lead, AnalysisJob, OutreachMessage
from modules.analysis.job_processor import queue_analysis_job, get_report
from modules.analysis.outreach_generator import generate_outreach
from modules.database.repositories import OutreachMessageRepository
from modules.export.email_csv_exporter import EmailCSVExporter

def render_campaign_card(campaign: Campaign):
    st.markdown(f"### 🎯 {campaign.campaign_name}")
    st.caption(f"**Category:** {campaign.category} | **Location:** {campaign.location} | **Created:** {campaign.created_at.strftime('%Y-%m-%d %H:%M') if campaign.created_at else 'Unknown'}")
    
    db = SessionLocal()
    try:
        # Calculate Metrics
        leads = db.query(Lead).filter(Lead.campaign_id == campaign.id).all()
        total_leads = len(leads)
        
        # We need Lead IDs to query AnalysisJobs and OutreachMessages efficiently
        lead_ids = [l.id for l in leads]
        
        analyzed_leads = db.query(AnalysisJob).filter(AnalysisJob.lead_id.in_(lead_ids), AnalysisJob.status == 'COMPLETED').count() if lead_ids else 0
        pending_analysis = db.query(AnalysisJob).filter(AnalysisJob.lead_id.in_(lead_ids), AnalysisJob.status.in_(['PENDING', 'RUNNING'])).count() if lead_ids else 0
        failed_analysis = db.query(AnalysisJob).filter(AnalysisJob.lead_id.in_(lead_ids), AnalysisJob.status == 'FAILED').count() if lead_ids else 0
        
        # Instead of distinct on sqlite, we can just filter
        # Get count of leads that have at least one outreach message
        generated_emails_count = 0
        if lead_ids:
            # We can use python to count distinct leads with outreach
            msgs = db.query(OutreachMessage.lead_id).filter(OutreachMessage.lead_id.in_(lead_ids)).all()
            generated_emails_count = len(set(m[0] for m in msgs))
            
        leads_with_email = sum(1 for l in leads if l.email and l.email.strip())

        # Display Metrics
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("👥 Total Leads", total_leads)
        c2.metric("🧠 Analyzed", analyzed_leads)
        c3.metric("✉️ Generated Emails", generated_emails_count)
        c4.metric("📧 Leads w/ Email", leads_with_email)
        c5.metric("⏳ Pending Analysis", pending_analysis)
        c6.metric("❌ Failed Analysis", failed_analysis)
        
        st.markdown("#### ⚡ Actions")
        
        # Action Buttons row 1
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("👀 View Leads", key=f"view_{campaign.id}", use_container_width=True):
                st.session_state[f"show_leads_{campaign.id}"] = not st.session_state.get(f"show_leads_{campaign.id}", False)
        
        with a2:
            if st.button("🚀 Analyze Campaign Leads", key=f"analyze_{campaign.id}", type="primary", use_container_width=True):
                if total_leads == 0:
                    st.warning("No leads to analyze.")
                else:
                    queued_count = 0
                    for lead in leads:
                        # queue_analysis_job checks if job exists already internally
                        if queue_analysis_job(db, lead.id):
                            queued_count += 1
                    if queued_count > 0:
                        st.success(f"Queued {queued_count} new leads for analysis!")
                    else:
                        st.info("All leads are already analyzed or queued.")
                    st.rerun()
                    
        with a3:
            if st.button("✉️ Generate Missing Emails", key=f"generate_{campaign.id}", type="primary", use_container_width=True):
                with st.spinner("Generating emails for analyzed leads missing outreach..."):
                    generated_count = 0
                    outreach_repo = OutreachMessageRepository(db)
                    for lead in leads:
                        # Check if already generated
                        latest = outreach_repo.get_latest_for_lead(lead.id)
                        if not latest:
                            report = get_report(db, lead.id)
                            if report and report.ai_report_json:
                                try:
                                    res = generate_outreach(report, lead, "Cold Outreach", "Professional", "Short", "Get Reply", "Auto (from report)")
                                    if "error" not in res:
                                        outreach_repo.create(
                                            lead_id=lead.id,
                                            report_id=report.id,
                                            email_type="Cold Outreach",
                                            tone="Professional",
                                            length="Short",
                                            cta_goal="Get Reply",
                                            service_focus="Auto (from report)",
                                            subject_lines=res.get("subject_lines", []),
                                            email_body=res.get("email_body", "")
                                        )
                                        generated_count += 1
                                except Exception as e:
                                    pass # Skip on failure
                    
                    if generated_count > 0:
                        st.success(f"Generated {generated_count} new emails!")
                    else:
                        st.info("No missing emails to generate (or leads haven't been analyzed yet).")
                    st.rerun()

        # Action Buttons row 2 (Exports)
        e1, e2 = st.columns(2)
        with e1:
            # Download Leads CSV
            if total_leads > 0:
                df = pd.DataFrame([{
                    "Business Name": l.business_name,
                    "Email": l.email,
                    "Phone": l.phone,
                    "Website": l.website,
                    "Category": l.category,
                    "Status": l.status
                } for l in leads])
                csv_bytes = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Leads CSV",
                    data=csv_bytes,
                    file_name=f"leads_{campaign.campaign_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key=f"dl_leads_{campaign.id}",
                    use_container_width=True
                )
        
        with e2:
            # Download Generated Email CSV
            exporter = EmailCSVExporter()
            rows, stats = exporter.get_campaign_email_rows(db, campaign.id, include_missing_email=False)
            
            # Show summary logic
            with st.expander("Email Export Stats", expanded=False):
                if stats["missing_content_skipped"] > 0:
                    st.warning(f"⚠️ {stats['missing_content_skipped']} leads do not have generated emails yet.")
                st.write(f"- Total Leads: {stats['total_leads']}")
                st.write(f"- Generated Emails: {stats['generated_emails']}")
                st.write(f"- Rows Included in CSV: {stats['rows_included']}")
                st.write(f"- Skipped (Missing Contact Email): {stats['missing_email_skipped']}")
                st.write(f"- Skipped (Missing AI Content): {stats['missing_content_skipped']}")
            
            if rows:
                df_export = exporter.build_dataframe(rows)
                csv_export_bytes = exporter.to_csv_bytes(df_export)
                st.download_button(
                    label="📥 Download Generated Email CSV",
                    data=csv_export_bytes,
                    file_name=f"leadpilot_emails_{campaign.campaign_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key=f"dl_email_{campaign.id}",
                    use_container_width=True,
                    type="primary"
                )
            else:
                st.button("📥 Download Generated Email CSV", disabled=True, key=f"dl_email_dis_{campaign.id}", use_container_width=True)
                st.caption("No emails generated or no leads have emails.")

        # View Leads Dropdown
        if st.session_state.get(f"show_leads_{campaign.id}", False):
            if leads:
                lead_data = [{"Business": l.business_name, "Email": l.email, "Phone": l.phone, "Website": l.website} for l in leads]
                st.dataframe(pd.DataFrame(lead_data), hide_index=True, width="stretch")
            else:
                st.info("No leads found for this campaign.")
        
        st.divider()

    finally:
        db.close()
