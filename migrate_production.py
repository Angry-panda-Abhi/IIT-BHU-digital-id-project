from app import app
from extensions import db
from sqlalchemy import text

def run_migrations():
    with app.app_context():
        print("Starting production migration...")
        

        migrations = [
            "ALTER TABLE scanners ADD COLUMN IF NOT EXISTS scanner_type VARCHAR(20) NOT NULL DEFAULT 'general'",
            "ALTER TABLE scanners ADD COLUMN IF NOT EXISTS assigned_hostel VARCHAR(120)",
            "ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS is_cross_hostel BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS cross_hostel_reason VARCHAR(255)"
        ]
        


        
        for sql in migrations:
            try:
                db.session.execute(text(sql))
                db.session.commit()
                print(f"Executed: {sql}")
            except Exception as e:
                db.session.rollback()

                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print(f"Skipping (already exists): {sql}")
                else:
                    print(f"Error executing {sql}: {e}")
        
        print("Migration complete!")

if __name__ == "__main__":
    run_migrations()
