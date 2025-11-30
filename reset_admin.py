from app.database import SessionLocal
from app.services import auth_service
from app import models

def reset_admin():
    db = SessionLocal()
    try:
        user = auth_service.get_user_by_username(db, "admin")
        if user:
            print("Found admin user. Resetting password...")
            auth_service.update_password(db, user, "admin")
            print("Password reset to 'admin'")
            
            # Verify
            print("Verifying login...")
            auth_user = auth_service.authenticate_user(db, "admin", "admin")
            if auth_user:
                print("SUCCESS: Login verified!")
            else:
                print("ERROR: Login failed after reset!")
        else:
            print("Admin user not found. Creating...")
            auth_service.create_user(db, "admin", "admin", is_admin=True)
            print("Admin user created with password 'admin'")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_admin()
