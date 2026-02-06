import secrets
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from brokerage_parser.db import SessionLocal
from brokerage_parser.models import AdminUser
from brokerage_parser.core.security import get_password_hash

def create_first_admin():
    db = SessionLocal()
    try:
        email = "admin@parsefin.com"
        existing_user = db.query(AdminUser).filter(AdminUser.email == email).first()
        if existing_user:
            print(f"Admin user {email} already exists.")
            return

        password = secrets.token_urlsafe(16)
        hashed_password = get_password_hash(password)

        admin = AdminUser(
            email=email,
            password_hash=hashed_password,
            role="superadmin",
            is_active=True
        )
        db.add(admin)
        db.commit()

        print("\n" + "="*50)
        print("FIRST ADMIN USER CREATED")
        print("="*50)
        print(f"Email:    {email}")
        print(f"Password: {password}")
        print("="*50)
        print("SAVE THESE CREDENTIALS NOW! They will not be shown again.\n")

    except Exception as e:
        print(f"Error creating admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_first_admin()
