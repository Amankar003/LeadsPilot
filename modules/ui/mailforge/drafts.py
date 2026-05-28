import streamlit as st
import pandas as pd
from modules.mailforge.generator import MailForgeGenerator
from config.database import SessionLocal
from modules.database.models import MailForgeCampaign, MailForgeDraft, Lead
from datetime import datetime

def render_drafts():
    st.markdown("### 📝 Outreach Drafts Review")
    st.caption("Review, edit, bulk-approve, or regenerate cold email drafts. All drafts must be approved before campaign dispatch.")
    st.divider()

    db = SessionLocal()
    try:
        campaigns = db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).all()
        if not campaigns:
            st.info("Please create a campaign first.")
            return

        camp_options = {c.id: c.name for c in campaigns}
        selected_campaign_id = st.selectbox(
            "🎯 Filter by Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="drafts_select_camp"
        )

        status_filter = st.selectbox(
            "📌 Filter by Status",
            ["draft", "approved", "rejected", "edited", "sent", "failed", "ALL"],
            key="drafts_status_filter"
        )

        # Query drafts
        query = db.query(MailForgeDraft).filter(
            MailForgeDraft.mailforge_campaign_id == selected_campaign_id
        )
        if status_filter != "ALL":
            query = query.filter(MailForgeDraft.status == status_filter)
        
        drafts = query.order_by(MailForgeDraft.created_at.desc()).all()

        if not drafts:
            st.info(f"No drafts found with status '{status_filter}' for this campaign.")
            return

        # Bulk Actions
        if status_filter == "draft" or status_filter == "ALL":
            if st.button("✅ Bulk Approve All 'draft' Emails", type="primary", use_container_width=True):
                draft_count = 0
                for d in drafts:
                    if d.status == "draft":
                        d.status = "approved"
                        draft_count += 1
                db.commit()
                st.success(f"🎉 Successfully approved **{draft_count}** drafts!")
                st.rerun()

        st.divider()
        st.markdown(f"##### Showing {len(drafts)} drafts")

        generator = MailForgeGenerator()

        for idx, draft in enumerate(drafts):
            lead = db.query(Lead).filter(Lead.id == draft.lead_id).first()
            recipient_email = lead.email if lead else "Unknown"
            biz_name = lead.business_name if lead else "Unknown Business"
            
            status_emoji = {
                "draft": "📝", "approved": "✅", "rejected": "❌",
                "edited": "✏️", "sent": "📤", "failed": "⚠️"
            }.get(draft.status, "✉️")

            with st.expander(f"{status_emoji} {biz_name} ({recipient_email}) — {draft.subject[:40]}"):
                c1, c2 = st.columns(2)
                c1.caption(f"🎯 **Persona Reason:** {draft.personalization_reason or 'N/A'}")
                c2.caption(f"🚦 **Current Status:** {draft.status.upper()}")

                new_subject = st.text_input("Subject Line", value=draft.subject, key=f"subj_{draft.id}_{idx}")
                new_body = st.text_area("Email Body", value=draft.body, height=250, key=f"body_{draft.id}_{idx}")

                col_b1, col_b2, col_b3, col_b4 = st.columns(4)
                with col_b1:
                    if st.button("💾 Save Changes", key=f"save_{draft.id}_{idx}", use_container_width=True):
                        draft.subject = new_subject
                        draft.body = new_body
                        draft.status = "edited"
                        db.commit()
                        st.success("Draft saved!")
                        st.rerun()
                
                with col_b2:
                    if st.button("✅ Approve Draft", key=f"app_{draft.id}_{idx}", use_container_width=True, type="primary"):
                        draft.subject = new_subject
                        draft.body = new_body
                        draft.status = "approved"
                        db.commit()
                        st.success("Approved!")
                        st.rerun()

                with col_b3:
                    # Regenerate
                    regen_instruction = st.text_input("Regen Prompt (optional)", placeholder="e.g. make it shorter", key=f"inst_{draft.id}_{idx}")
                    if st.button("🔄 Regenerate", key=f"regen_{draft.id}_{idx}", use_container_width=True):
                        with st.spinner("Regenerating..."):
                            res = generator.regenerate_email(draft.id, regen_instruction)
                            if "error" in res:
                                st.error(res["error"])
                            else:
                                draft.subject = res["subject"]
                                draft.body = res["body"]
                                draft.opening_line = res.get("opening_line", draft.opening_line)
                                draft.cta = res.get("cta", draft.cta)
                                draft.personalization_reason = res.get("personalization_reason", draft.personalization_reason)
                                draft.status = "draft"
                                db.commit()
                                st.success("Regenerated draft successfully!")
                                st.rerun()

                with col_b4:
                    if st.button("🗑️ Delete/Reject", key=f"del_{draft.id}_{idx}", use_container_width=True):
                        db.delete(draft)
                        db.commit()
                        st.warning("Draft deleted.")
                        st.rerun()

    finally:
        db.close()
