"""
Seed script – create the default admin account.
Run:  python seed_admin.py
"""
import bcrypt
from app import create_app
from extensions import db
from models import Admin


def seed():
    app = create_app()
    with app.app_context():
        if Admin.query.first():
            print("⚠️  Admin account already exists. Skipping seed.")
            return

        password = "SecureAdmin@2026"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        admin = Admin(username="admin", password_hash=hashed)
        db.session.add(admin)
        db.session.commit()

        print("✅ Default admin created:")
        print(f"   Username: admin")
        print(f"   Password: {password}")
        print("   ⚠️  Change this password after first login!")


if __name__ == "__main__":
    seed()
