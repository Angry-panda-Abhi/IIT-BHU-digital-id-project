import sqlite3
import os
import shutil
from datetime import datetime


def get_db_path():
    
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

    instance_dir = "instance"
    if os.path.exists(instance_dir):
        for f in os.listdir(instance_dir):
            if f.endswith((".db", ".sqlite", ".sqlite3")):
                return os.path.join(instance_dir, f)

    return None


def column_exists(cursor, table, column):
    
    cursor.execute(f"PRAGMA table_info({table})")
    return column in [row[1] for row in cursor.fetchall()]


def migrate():
    db_path = get_db_path()
    if not db_path:
        print("❌ No SQLite database found in instance/ directory.")
        print("   If this is a fresh install, just start the app – db.create_all() will handle it.")
        return

    print(f"📂 Found database: {db_path}")


    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"💾 Backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    changes = 0

    try:

        if not column_exists(cursor, "users", "photo_updated_at"):
            cursor.execute("ALTER TABLE users ADD COLUMN photo_updated_at DATETIME")
            print("  ✅ Added users.photo_updated_at")
            changes += 1
        else:
            print("  ⏭️  users.photo_updated_at already exists – skipping")


        if not column_exists(cursor, "users", "photo_warning_scans"):
            cursor.execute(
                "ALTER TABLE users ADD COLUMN photo_warning_scans INTEGER NOT NULL DEFAULT 0"
            )
            print("  ✅ Added users.photo_warning_scans (default 0)")
            changes += 1
        else:
            print("  ⏭️  users.photo_warning_scans already exists – skipping")



        cursor.execute(
            
        )
        seeded = cursor.rowcount
        if seeded > 0:
            print(f"  ✅ Seeded photo_updated_at = created_at for {seeded} existing user(s) with photos")
        else:
            print("  ⏭️  No users needed photo_updated_at seeding")

        conn.commit()
        print(f"\n🎉 Migration complete! {changes} column(s) added.")
        if changes == 0:
            print("   Database was already up to date.")
            os.remove(backup_path)
            print("   Removed unnecessary backup.")
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
