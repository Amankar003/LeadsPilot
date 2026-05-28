import time
import threading
from sqlalchemy.orm import Session
from config.database import SessionLocal
from modules.database.models import ScrapingJob
from modules.jobs.scraping_planner import ScrapingPlanner
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class BackgroundWorker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(BackgroundWorker, cls).__new__(cls)
                cls._instance._started = False
            return cls._instance

    def __init__(self):
        # Already initialized via __new__ singleton pattern
        pass

    def start(self):
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._thread.start()
            logger.info("Background job worker started successfully.")

    def stop(self):
        with self._lock:
            if not self._started:
                return
            self._stop_event.set()
            self._started = False
            logger.info("Background job worker stopped.")

    def _worker_loop(self):
        while not self._stop_event.is_set():
            db = SessionLocal()
            try:
                # Poll database for pending scraping jobs
                job = db.query(ScrapingJob).filter(ScrapingJob.status == "PENDING").first()
                if job:
                    logger.info(f"Worker picked up pending job: {job.id} ({job.category} in {job.location})")
                    planner = ScrapingPlanner(db)
                    planner.execute_job(job.id)
            except Exception as e:
                logger.error(f"Worker exception: {e}")
            finally:
                db.close()
            
            # Cooldown sleep
            time.sleep(5)

# Standalone execution support
def run_standalone_worker():
    print("Starting LeadPilot AI standalone background worker...")
    worker = BackgroundWorker()
    worker.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping worker...")
        worker.stop()

if __name__ == "__main__":
    run_standalone_worker()
