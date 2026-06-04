from config.database import engine, Base, SessionLocal
import modules.database.models
from modules.database.migration import run_migration, _compute_schema_hash, _get_stored_schema_hash
from modules.database.models import get_or_create_default_user

def init_db():
    # Check if DB is already fully migrated using our fast hash
    dialect_name = engine.dialect.name
    is_pg = (dialect_name == 'postgresql')
    expected_hash = _compute_schema_hash()
    
    with engine.connect() as conn:
        stored_hash = _get_stored_schema_hash(conn, is_pg)
        
    # If hashes match, we skip create_all() AND skip migration
    if stored_hash != expected_hash:
        print("Schema changes detected. Creating missing tables...")
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully.")
    else:
        print("Schema hash matched. Skipping table creation checks.")
    
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
