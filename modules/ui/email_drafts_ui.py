import streamlit as st
from config.database import SessionLocal
from modules.database.repositories import CampaignRepository, EmailDraftRepository, LeadRepository
from modules.database.models import EmailDraft, Lead
from modules.ui.theme import page_header, empty_state, workflow_indicator, status_badge
import datetime


def render_email_drafts():
    page_header("📝", "Email Drafts", "Review, edit, approve, or cancel AI-generated email drafts")

    workflow_indicator(
        ["Scrape", "Clean", "AI Analyze", "Generate Email", "Review Draft", "Send"],
        active_index=4
    )

    db = SessionLocal()
    try:
        campaigns = CampaignRepository(db).get_all()

        if not campaigns:
            empty_state("📋", "No Campaigns", "Create a campaign first.")
            return

        camp_options = {c.id: c.campaign_name for c in campaigns}

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_camp_id = st.selectbox(
                "🎯 Select Campaign",
                options=list(camp_options.keys()),
                format_func=lambda x: camp_options[x],
                key="drafts_campaign"
            )
        with col_f2:
            status_filter = st.selectbox(
                "📌 Filter by Status",
                ["DRAFT", "APPROVED", "SENT", "CANCELLED", "ALL"],
                key="draft_status_filter"
            )
        
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            has_email_only = st.checkbox("📧 Has Email only", key="draft_has_email")
        with c_f2:
            has_phone_only = st.checkbox("📞 Has Phone only", key="draft_has_phone")

        draft_repo = EmailDraftRepository(db)
        lead_repo = LeadRepository(db)

        if status_filter == "ALL":
            drafts = db.query(EmailDraft).filter(EmailDraft.campaign_id == selected_camp_id).all()
        else:
            drafts = db.query(EmailDraft).filter(
                EmailDraft.campaign_id == selected_camp_id,
                EmailDraft.status == status_filter
            ).all()

        if not drafts:
            empty_state("✉️", "No Drafts", f"No {status_filter.lower()} drafts for this campaign.")
            return

        # Apply email/phone filters
        filtered_drafts = []
        for d in drafts:
            lead = db.query(Lead).filter_by(id=d.lead_id).first()
            if has_email_only and not (lead and lead.email):
                continue
            if has_phone_only and not (lead and lead.phone):
                continue
            filtered_drafts.append(d)
        
        drafts = filtered_drafts

        if not drafts:
            st.info("No drafts match the selected filters.")
            return

        # Count by status
        all_drafts = db.query(EmailDraft).filter(EmailDraft.campaign_id == selected_camp_id).all()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📝 Draft", sum(1 for d in all_drafts if d.status == "DRAFT"))
        c2.metric("✅ Approved", sum(1 for d in all_drafts if d.status == "APPROVED"))
        c3.metric("📤 Sent", sum(1 for d in all_drafts if d.status == "SENT"))
        c4.metric("❌ Cancelled", sum(1 for d in all_drafts if d.status == "CANCELLED"))

        st.divider()
        st.markdown(f"##### Showing {len(drafts)} drafts")

        for draft in drafts:
            lead = db.query(Lead).filter_by(id=draft.lead_id).first()
            biz_name = lead.business_name if lead else "Unknown"
            status_icon = {"DRAFT": "📝", "APPROVED": "✅", "SENT": "📤", "CANCELLED": "❌"}.get(draft.status, "❓")

            with st.expander(f"{status_icon} {biz_name} — {draft.subject[:50]}"):
                if draft.status == "DRAFT":
                    if hasattr(draft, 'email_type') and draft.email_type:
                        c1, c2, c3 = st.columns(3)
                        c1.caption(f"🎯 **Type:** {draft.email_type}")
                        c2.caption(f"🧠 **Confidence:** {draft.confidence_score}")
                        c3.caption(f"📝 **Preview:** {getattr(draft, 'preview_text', 'N/A')}")
                        
                        st.info(f"**Problem:** {draft.identified_problem}\n\n**Solution:** {draft.proposed_solution}")

                    new_subject = st.text_input("Subject", value=draft.subject, key=f"subj_{draft.id}")
                    new_body = st.text_area("Body", value=draft.body, height=200, key=f"body_{draft.id}")

                    col1, col2, col3, _ = st.columns([1, 1, 1, 1])
                    with col1:
                        if st.button("💾 Save", key=f"save_{draft.id}", use_container_width=True):
                            draft_repo.update(draft.id, subject=new_subject, body=new_body)
                            st.success("Saved!")
                    with col2:
                        if st.button("✅ Approve", type="primary", key=f"approve_{draft.id}", use_container_width=True):
                            draft_repo.update(
                                draft.id,
                                subject=new_subject, body=new_body,
                                status="APPROVED", approved_by_user=True,
                                approved_at=datetime.datetime.utcnow(),
                            )
                            lead_repo.update_status(draft.lead_id, "EMAIL_APPROVED")
                            st.rerun()
                    with col3:
                        if st.button("❌ Reject", key=f"cancel_{draft.id}", use_container_width=True, help="Cancel this draft and send lead back to Generator"):
                            draft_repo.update(draft.id, status="CANCELLED")
                            lead_repo.update_status(draft.lead_id, "AI_ANALYZED")
                            st.rerun()
                else:
                    st.markdown(f"**Subject:** {draft.subject}")
                    
                    if hasattr(draft, 'email_type') and draft.email_type:
                        c1, c2, c3 = st.columns(3)
                        c1.caption(f"🎯 **Type:** {draft.email_type}")
                        c2.caption(f"🧠 **Confidence:** {draft.confidence_score}")
                        c3.caption(f"📝 **Preview:** {getattr(draft, 'preview_text', 'N/A')}")
                        
                        st.info(f"**Problem:** {draft.identified_problem}\n\n**Solution:** {draft.proposed_solution}")

                    st.code(draft.body, language=None)
                    st.caption(f"Status: {draft.status} | Created: {str(draft.created_at)[:16]}")
    finally:
        db.close()
