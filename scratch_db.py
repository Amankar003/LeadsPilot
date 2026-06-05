import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database.connection import get_db_session
from modules.database.models import AnalysisReport, OutreachMessage, Lead

def check_db():
    with get_db_session() as db:
        reports = db.query(AnalysisReport).order_by(AnalysisReport.created_at.desc()).limit(3).all()
        for i, report in enumerate(reports):
            lead = db.query(Lead).filter(Lead.id == report.lead_id).first()
            print(f"--- Report {i+1} for Lead {lead.business_name if lead else 'Unknown'} ---")
            print(f"has_website: {report.has_website}")
            print(f"ai_report_json type: {type(report.ai_report_json)}")
            if isinstance(report.ai_report_json, dict):
                print(f"ai_report_json keys: {list(report.ai_report_json.keys())}")
                print(f"executive_summary: {report.ai_report_json.get('executive_summary', 'MISSING')[:100]}...")
            else:
                print(f"ai_report_json content: {report.ai_report_json}")
            
            print(f"pain_points_json: {report.pain_points_json}")
            print(f"recommended_services_json: {report.recommended_services_json}")
            
            outreach = db.query(OutreachMessage).filter(OutreachMessage.report_id == report.id).first()
            if outreach:
                print(f"Generated Email Body:\n{outreach.email_body[:300]}...")
            else:
                print("No OutreachMessage found for this report.")
            print("="*50)

if __name__ == "__main__":
    check_db()
