import sys
import os
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up console logging for debug
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from config.database import SessionLocal
from modules.database.models import AnalysisReport, Lead
from modules.analysis.outreach_generator import generate_outreach

def run_test():
    db = SessionLocal()
    # Get latest completed report
    report = db.query(AnalysisReport).filter(AnalysisReport.ai_report_json != None).order_by(AnalysisReport.created_at.desc()).first()
    if not report:
        print("No report found in DB with ai_report_json.")
        return
        
    lead = db.query(Lead).filter(Lead.id == report.lead_id).first()
    print(f"Testing generation for Lead: {lead.business_name} ({lead.id})")
    print(f"Report ID: {report.id}")
    
    try:
        result = generate_outreach(
            report=report,
            lead=lead,
            email_type="Cold Outreach",
            tone="Professional",
            length="Short",
            cta_goal="Get Reply",
            service_focus="Auto (from report)"
        )
        print("\n\nFINAL RESULT JSON:")
        print(json.dumps(result, indent=2))
        print("\nEMAIL BODY:")
        print(result.get("email_body", "MISSING"))
    except Exception as e:
        print(f"Error generating outreach: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
