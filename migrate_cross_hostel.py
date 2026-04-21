import sqlite3

def migrate():
    print("Starting migration...")
    conn = sqlite3.connect("instance/college_id.db")
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE scanners ADD COLUMN scanner_type VARCHAR(20) NOT NULL DEFAULT 'general'")
        print("Added scanner_type to scanners")
    except sqlite3.OperationalError as e:
        print(f"Skipping scanner_type: {e}")

    try:
        cursor.execute("ALTER TABLE scanners ADD COLUMN assigned_hostel VARCHAR(120)")
        print("Added assigned_hostel to scanners")
    except sqlite3.OperationalError as e:
        print(f"Skipping assigned_hostel: {e}")

    try:
        cursor.execute("ALTER TABLE scan_logs ADD COLUMN is_cross_hostel BOOLEAN NOT NULL DEFAULT 0")
        print("Added is_cross_hostel to scan_logs")
    except sqlite3.OperationalError as e:
        print(f"Skipping is_cross_hostel: {e}")

    try:
        cursor.execute("ALTER TABLE scan_logs ADD COLUMN cross_hostel_reason VARCHAR(255)")
        print("Added cross_hostel_reason to scan_logs")
    except sqlite3.OperationalError as e:
        print(f"Skipping cross_hostel_reason: {e}")

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
