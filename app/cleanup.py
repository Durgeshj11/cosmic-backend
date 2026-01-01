import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load local .env if testing locally, otherwise it uses Render's Env Var
load_dotenv()

# Get the URL from your Render environment settings
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def wipe_database():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found!")
        return

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            # This command empties the table completely
            connection.execute(text("TRUNCATE TABLE cosmic_profiles RESTART IDENTITY CASCADE;"))
            connection.commit()
            print("Successfully wiped all old 85% data from the cloud!")
    except Exception as e:
        print(f"Cleanup Error: {e}")

if __name__ == "__main__":
    wipe_database()