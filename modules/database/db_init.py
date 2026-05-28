from config.database import engine, Base, SessionLocal
import modules.database.models
from modules.database.migration import run_migration
from modules.database.models import get_or_create_default_user

def init_db():
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")
    
    # Run database migration to ensure all Lead columns exist
    run_migration()
    
    # Seed default user
    db = SessionLocal()
    try:
        get_or_create_default_user(db)
        print("Default user seeded successfully.")
    except Exception as e:
        print(f"Error seeding default user: {e}")
    finally:
        db.close()
    
if __name__ == "__main__":
    init_db()
