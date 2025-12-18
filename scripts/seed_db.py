import sys
import os

# --- THE FIX: Tell Python to look in the main folder ---
sys.path.append(os.getcwd())
# -------------------------------------------------------

from sqlmodel import Session, create_engine, SQLModel
from app.db.models import User
from datetime import date

# Connect to DB
DATABASE_URL = "postgresql://cosmic_admin:secure_password_123@localhost:5432/cosmic_db"
engine = create_engine(DATABASE_URL)

def create_fake_users():
    users = [
        User(
            name="Luna Star",
            email="luna@cosmos.com",
            dob=date(1995, 7, 24), # Leo (Fire)
            sun_sign="Leo",
            life_path_number=1,
            hand_element="Fire",
            dominant_mount="Venus",
            heart_line_type="Curved"
        ),
        User(
            name="Orion Hunter",
            email="orion@cosmos.com",
            dob=date(1992, 11, 15), # Scorpio (Water)
            sun_sign="Scorpio",
            life_path_number=7,
            hand_element="Water",
            dominant_mount="Moon",
            heart_line_type="Straight"
        ),
        User(
            name="Terra Green",
            email="terra@cosmos.com",
            dob=date(1990, 5, 2), # Taurus (Earth)
            sun_sign="Taurus",
            life_path_number=4,
            hand_element="Earth",
            dominant_mount="Jupiter",
            heart_line_type="Straight"
        )
    ]

    with Session(engine) as session:
        for user in users:
            session.add(user)
        session.commit()
        print("✨ Success! 3 Cosmic Users added to the database. ✨")

if __name__ == "__main__":
    create_fake_users()