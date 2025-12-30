import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Standardize the database URL for Render
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def reset_database():
    try:
        with engine.connect() as conn:
            print("Connecting to database...")
            # Clears the tables and resets IDs back to 1
            conn.execute(text("TRUNCATE TABLE \"user\", \"messages\" RESTART IDENTITY CASCADE;"))
            conn.commit()
            print("SUCCESS: All old records cleared. Database is fresh.")
    except Exception as e:
        print(f"ERROR: Could not clear database. {e}")

if __name__ == "__main__":
    reset_database()