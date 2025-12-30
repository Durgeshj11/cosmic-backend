import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# This uses the same URL your app uses
DATABASE_URL = os.environ.get("DATABASE_URL").replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("Connecting to cosmic-db...")
    try:
        # This adds the missing column manually
        conn.execute(text('ALTER TABLE "user" ADD COLUMN palm_analysis TEXT;'))
        conn.commit()
        print("SUCCESS: Column 'palm_analysis' added permanently!")
    except Exception as e:
        print(f"ERROR: {e}")