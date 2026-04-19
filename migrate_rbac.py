"""
Safe DB migration script for RBAC.
Adds role/location_name columns to admins table and location column to scan_logs.
Idempotent – safe to run multiple times (checks if columns exist before adding).

Run:  python migrate_rbac.py
"""
import sqlite3
import os
import shutil
from datetime import datetime


def get_db_path():
    """Locate the SQLite database file."""
    # Check common locations
    candidates = [
        os.path.join("instance", "college_id.db"),
        os.path.join("instance", "exploitation.db"),
        os.path.join("instance", "app.db"),
        os.path.join("instance", "database.db"),
        os.path.join("instance", "digital_id.db"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path

    # Fallback: scan instance directory
    instance_dir = "instance"
    if os.path.exists(instance_dir):
        for f in os.listdir(instance_dir):
            if f.endswith(".db") or f.endswith(".sqlite") or f.endswith(".sqlite3"):
                return os.path.join(instance_dir, f)

    return None


def column_exists(cursor, table, column):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate():
    db_path = get_db_path()
    if not db_path:
        print("❌ No SQLite database found in instance/ directory.")
        print("   If this is a fresh install, just start the app – db.create_all() will handle it.")
        return

    print(f"📂 Found database: {db_path}")

    # --- Safety: create timestamped backup ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"💾 Backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    changes = 0

    try:
        # --- admins.role ---
        if not column_exists(cursor, "admins", "role"):
            cursor.execute("ALTER TABLE admins ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'superadmin'")
            print("  ✅ Added admins.role (default: superadmin)")
            changes += 1
        else:
            print("  ⏭️  admins.role already exists – skipping")

        # --- admins.location_name ---
        if not column_exists(cursor, "admins", "location_name"):
            cursor.execute("ALTER TABLE admins ADD COLUMN location_name VARCHAR(120)")
            print("  ✅ Added admins.location_name")
            changes += 1
        else:
            print("  ⏭️  admins.location_name already exists – skipping")

        # --- scan_logs.location ---
        if not column_exists(cursor, "scan_logs", "location"):
            cursor.execute("ALTER TABLE scan_logs ADD COLUMN location VARCHAR(120)")
            print("  ✅ Added scan_logs.location")
            changes += 1
        else:
            print("  ⏭️  scan_logs.location already exists – skipping")

        # --- Ensure existing admin accounts are marked as superadmin ---
        cursor.execute("UPDATE admins SET role = 'superadmin' WHERE role IS NULL OR role = ''")
        updated = cursor.rowcount
        if updated > 0:
            print(f"  ✅ Updated {updated} existing admin(s) to role=superadmin")

        conn.commit()
        print(f"\n🎉 Migration complete! {changes} column(s) added.")
        if changes == 0:
            print("   Database was already up to date.")
            # Clean up unnecessary backup
            os.remove(backup_path)
            print(f"   Removed unnecessary backup.")
        else:
            print(f"   Backup preserved at: {backup_path}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        print(f"   Database was NOT modified. Backup at: {backup_path}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
