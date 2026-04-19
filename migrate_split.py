import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'college_id.db')

def migrate():
    print(f"Connecting to {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("Database does not exist yet. No migration needed.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure scanners table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scanners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            plain_password VARCHAR(255),
            location_name VARCHAR(120),
            created_at DATETIME
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_scanners_username ON scanners (username)")

    # Check if 'role' column exists in admins table using pragma
    cursor.execute("PRAGMA table_info(admins)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if 'role' not in columns:
        print("Migration already performed.")
        return

    # Find existing scanners in admins table
    cursor.execute("SELECT username, password_hash, plain_password, location_name, created_at FROM admins WHERE role = 'scanner'")
    scanners_to_migrate = cursor.fetchall()

    print(f"Found {len(scanners_to_migrate)} scanners to migrate.")

    for scanner in scanners_to_migrate:
        username, pw_hash, plain_pw, loc, created_at = scanner
        try:
            cursor.execute("""
                INSERT INTO scanners (username, password_hash, plain_password, location_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (username, pw_hash, plain_pw, loc, created_at))
            print(f"Migrated scanner: {username}")
        except sqlite3.IntegrityError:
            print(f"Scanner {username} already exists in scanners table.")

    # Get remaining superadmins
    cursor.execute("SELECT id, username, password_hash, created_at FROM admins WHERE role = 'superadmin' OR role IS NULL")
    admins = cursor.fetchall()

    # Drop and recreate admins cleanly without the extra columns
    cursor.execute("DROP TABLE admins")
    cursor.execute("""
        CREATE TABLE admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME
        )
    """)
    cursor.execute("CREATE INDEX ix_admins_username ON admins (username)")

    for admin in admins:
        cursor.execute("INSERT INTO admins (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)", admin)
    
    print(f"Recreated admins table with {len(admins)} superadmins.")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    migrate()
