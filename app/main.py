import os
import json
import io
import random
import hashlib  # Used for the deterministic "Shared Destiny" fingerprint
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- AI Configuration ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
# Using 1.5-flash for speed and structural visual precision
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# --- Database Setup ---
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "cosmic_profiles" 
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    birthday = Column(Date, nullable=False)
    palm_analysis = Column(String, nullable=True)

# Initialize database tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

# UNIVERSAL CORS FIX: Vital for Flutter Web connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "online", "message": "Cosmic Backend is LIVE"}

# --- UTILITY: RESET DATABASE ---
@app.get("/nuke-database")
def nuke_database(db: Session = Depends(get_db)):
    """Wipes all data to clear old records and reset IDs."""
    try:
        db.execute(text("TRUNCATE TABLE cosmic_profiles RESTART IDENTITY CASCADE;"))
        db.commit()
        return {"status": "success", "message": "Database wiped clean. Start fresh!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def analyze_palm_ai(image_bytes):
    """Replicates a healthy human eye by reading structural palm data."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Prompt designed to extract stable biological features for long-term consistency
        prompt = "Perform a detailed palm reading (Life, Heart, and Head lines). Max 40 words."
        response = ai_model.generate_content([prompt, img])
        return response.text
    except Exception as e:
        print(f"AI Analysis Error: {e}")
        return "Your palm suggests a journey of unique potential and cosmic alignment."

@app.post("/signup-full")
async def signup(
    name: str = Form(...), 
    email: str = Form(...), 
    birthday: str = Form(...), 
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
    
    # Check if user exists to allow for 'Evolution' (updating palm scan)
    existing_user = db.query(User).filter(User.email == clean_email).first()

    photo_data = await photos[0].read()
    reading = await analyze_palm_ai(photo_data)
    
    try:
        date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
        
        if existing_user:
            # Evolution Support: Update existing profile with new biological data
            existing_user.name = name
            existing_user.palm_analysis = reading
            db.commit()
            return {"message": "Success - Profile Evolved"}

        # Register fresh user
        new_user = User(
            name=name, 
            email=clean_email, 
            birthday=date_obj,
            palm_analysis=reading
        )
        db.add(new_user)
        db.commit()
        return {"message": "Success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error during signup")

@app.get("/feed")
async def get_feed(current_email: str, db: Session = Depends(get_db)):
    email_clean = current_email.strip().lower()
    me = db.query(User).filter(User.email == email_clean).first()
    if not me: 
        raise HTTPException(status_code=404, detail="User Not Found")
    
    others = db.query(User).filter(User.email != email_clean).all()
    results = []

    for other in others:
        # --- THE DETERMINISTIC COSMIC FINGERPRINT ---
        # 1. SYMMETRIC MATCHING: Sort emails so A matching B is identical to B matching A
        identity_part = "".join(sorted([me.email, other.email]))
        
        # 2. EVOLUTION SUPPORT: Any change in palm text resets the seed for BOTH
        evolution_part = (me.palm_analysis or "p") + (other.palm_analysis or "p")
        
        # 3. DETERMINISTIC SEED: MD5 hashing turns living data into a fixed number
        seed_hash = hashlib.md5((identity_part + evolution_part).encode()).hexdigest()
        random.seed(int(seed_hash, 16)) 
        
        # 4. Generate locked, repeatable scores based on the shared seed
        tot = random.randint(65, 98)
        fnd = random.randint(60, 95)
        eco = random.randint(60, 95)
        fam = random.randint(60, 95)
        lst = random.randint(60, 95)

        # Unified Tiering Logic
        if tot >= 90:
            tier = "Marriage Material"
        elif tot >= 75:
            tier = "Strong Match"
        else:
            tier = "Potential Match"

        results.append({
            "name": other.name, 
            "percentage": f"{tot}%",
            "tier": tier,
            "flag": "Green",
            "reading": f"Cosmic connection between {me.name} and {other.name} based on biological alignment.",
            "factors": {
                "Foundation": f"{fnd}%",
                "Economics": f"{eco}%",
                "Family": f"{fam}%",
                "Lifestyle": f"{lst}%"
            }
        })
        
        # Reset seed to avoid interference with the next person in the feed
        random.seed(None)
        
    return results

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    """Permanently erases own profile and data."""
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user:
        db.delete(user)
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404, detail="Not found")