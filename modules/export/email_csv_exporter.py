import pandas as pd
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session

class EmailCSVExporter:
    """
    Service to export generated outreach emails as CSV files.
    Final output matches: receiverid, subject, body
    """
    
    def build_rows(self, leads_and_outreach: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Build CSV rows from a list of dictionaries containing lead email and generated email details.
        Expected keys in each dict: 'email', 'subject', 'body'.
        """
        rows = []
        for item in leads_and_outreach:
            receiverid = item.get("email") or ""
            subject = item.get("subject") or ""
            body = item.get("body") or ""
            
            rows.append({
                "receiverid": receiverid,
                "subject": subject,
                "body": body
            })
            
        return rows

    def get_campaign_email_rows(self, db: Session, campaign_id: str, include_missing_email: bool = False) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """
        Fetches all generated emails for a specific campaign.
        Returns a tuple of (rows, stats).
        """
        from modules.database.models import Lead, OutreachMessage
        
        leads = db.query(Lead).filter(Lead.campaign_id == campaign_id).all()
        
        rows = []
        stats = {
            "total_leads": len(leads),
            "generated_emails": 0,
            "rows_included": 0,
            "missing_email_skipped": 0,
            "missing_content_skipped": 0
        }
        
        for lead in leads:
            latest_msg = db.query(OutreachMessage).filter(OutreachMessage.lead_id == lead.id).order_by(OutreachMessage.created_at.desc()).first()
            
            if not latest_msg or not latest_msg.email_body:
                stats["missing_content_skipped"] += 1
                continue
                
            stats["generated_emails"] += 1
            
            if not lead.email and not include_missing_email:
                stats["missing_email_skipped"] += 1
                continue
                
            subject = ""
            if latest_msg.subject_lines and len(latest_msg.subject_lines) > 0:
                subject = latest_msg.subject_lines[0]
                
            rows.append({
                "receiverid": lead.email or "",
                "subject": subject,
                "body": latest_msg.email_body
            })
            stats["rows_included"] += 1
            
        return rows, stats

    def build_dataframe(self, rows: List[Dict[str, str]]) -> pd.DataFrame:
        """
        Convert the rows to a pandas DataFrame.
        """
        return pd.DataFrame(rows)

    def export_dataframe(self, rows: List[Dict[str, str]]) -> pd.DataFrame:
        """
        Legacy wrapper for build_dataframe.
        """
        return self.build_dataframe(rows)

    def to_csv_bytes(self, df: pd.DataFrame) -> bytes:
        """
        Convert DataFrame to CSV bytes for download.
        """
        return df.to_csv(index=False).encode('utf-8')
