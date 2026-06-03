import sys
import os
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')

from config.database import SessionLocal
from modules.dork_optimizer.service import DorkOptimizerService
from modules.database.models import DorkOpportunity, GeneratedDork, DorkPipelineRun

def test_pipeline():
    print("=== STARTING DORK OPTIMIZER OPPORTUNITY PIPELINE TEST ===")
    db = SessionLocal()
    try:
        service = DorkOptimizerService(db)
        config = {
            "trend_scope": "Global",
            "num_opportunities": 2,
            "dorks_per_opportunity": 2
        }
        summary = service.run_pipeline(config)
        print("\n=== PIPELINE SUCCESS ===")
        print(summary)
        
        print(f"\nDB State:")
        print(f"- DorkPipelineRun count: {db.query(DorkPipelineRun).count()}")
        print(f"- DorkOpportunity count: {db.query(DorkOpportunity).count()}")
        print(f"- GeneratedDork count: {db.query(GeneratedDork).count()}")
            
    except Exception as e:
        print(f"\n=== PIPELINE FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_pipeline()
