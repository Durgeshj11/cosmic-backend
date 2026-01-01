import os
import io
import random
import hashlib
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

try:
    ai_model = genai.GenerativeModel('gemini-1.5-flash-latest')
except:
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
    
    # --- Multi-Tradition Preferences (Wisdom Layers) ---
    # As per image_472971.png logic
    astro_pref = Column(String, default="Western")   # Vedic vs. Western vs. Chinese
    num_pref = Column(String, default="Pythagorean") # Pythagorean vs. Chaldean
    palm_pref = Column(String, default="Western")    # Western vs. Vedic
    
    # --- Layered Accuracy Data ---
    # As per image_47f809.png logic
    birth_time = Column(String, nullable=True)      
    birth_location = Column(String, nullable=True)  
    full_legal_name = Column(String, nullable=True) 

# Initialize database tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

# UNIVERSAL CORS FIX
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

# --- UTILITY: RESET DATABASE (NUKE) ---
@app.get("/nuke-database")
def nuke_database(db: Session = Depends(get_db)):
    try:
        db.execute(text("TRUNCATE TABLE cosmic_profiles RESTART IDENTITY CASCADE;"))
        db.commit()
        return {"status": "success", "message": "Database wiped clean. Schema reset."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def analyze_palm_ai(image_bytes, palm_pref):
    """AI analysis adjusted by Western or Vedic preference."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Logic: Focus AI on lines (West) or symbols (Vedic)
        prompt = f"Perform a detailed {palm_pref} palm reading focusing on lines and cosmic symbols. Max 40 words."
        response = ai_model.generate_content([prompt, img])
        return response.text
    except Exception as e:
        return "Your palm reveals a journey of unique potential and cosmic alignment."

@app.post("/signup-full")
async def signup(
    name: str = Form(...), 
    email: str = Form(...), 
    birthday: str = Form(...),
    astro_pref: str = Form("Western"),
    num_pref: str = Form("Pythagorean"),
    palm_pref: str = Form("Western"),
    birth_time: str = Form(None),
    birth_location: str = Form(None),
    full_legal_name: str = Form(None),
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
    
    # 1. Process Palm Photo with preference
    try:
        photo_data = await photos[0].read()
        reading = await analyze_palm_ai(photo_data, palm_pref)
    except:
        reading = "Biological data captured. Alignment pending."

    try:
        # 2. Robust Date Parsing
        date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
        
        # 3. Evolution Support (Update or Create)
        user = db.query(User).filter(User.email == clean_email).first()

        if not user:
            user = User(email=clean_email)
            db.add(user)

        user.name = name
        user.birthday = date_obj
        user.palm_analysis = reading
        user.astro_pref = astro_pref
        user.num_pref = num_pref
        user.palm_pref = palm_pref
        user.birth_time = birth_time
        user.birth_location = birth_location
        user.full_legal_name = full_legal_name
        
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
        # --- LAYERED ACCURACY & DETERMINISTIC SEEDING ---
        # Base Data
        base_seeds = "".join(sorted([str(me.birthday), str(other.birthday)]))
        palm_seeds = (me.palm_analysis or "p") + (other.palm_analysis or "p")
        
        # Wisdom Layers
        pref_seeds = me.astro_pref + me.num_pref + me.palm_pref
        
        # Accuracy Data
        acc_data = (me.birth_time or "") + (me.birth_location or "") + (me.full_legal_name or "") + \
                   (other.birth_time or "") + (other.birth_location or "") + (other.full_legal_name or "")
        
        # Generate Seed Hash
        seed_hash = hashlib.md5((base_seeds + palm_seeds + pref_seeds + acc_data).encode()).hexdigest()
        random.seed(int(seed_hash, 16)) 
        
        tot = random.randint(65, 98)
        
        # Determine Result Quality
        if me.birth_time and me.birth_location and me.full_legal_name:
            quality = "Ultimate Accuracy"
        elif me.birth_time or me.full_legal_name:
            quality = "High Accuracy"
        else:
            quality = "Base Accuracy"

        # Dynamic Factor Naming based on Astrology Preference
        astro_label = "Zodiac Sync"
        if me.astro_pref == "Vedic": astro_label = "Karmic Link"
        elif me.astro_pref == "Chinese": astro_label = "Animal Sign"

        # Match Tier Logic
        if tot >= 90: tier = "Marriage Material"
        elif tot >= 78: tier = "Strong Match"
        elif tot >= 68: tier = "Fling / Casual"
        else: tier = "Just Friends"

        # 6-Field Report
        results.append({
            "name": other.name, 
            "percentage": f"{tot}%",
            "tier": tier,
            "accuracy_level": quality,
            "reading": "Your connection is written in the physical alignment of your life paths.",
            "factors": {
                "Foundation": f"{random.randint(60, 95)}%",
                "Economics": f"{random.randint(60, 95)}%",
                astro_label: f"{random.randint(60, 98)}%",
                "Lifestyle": f"{random.randint(60, 95)}%",
                "Sexual": f"{random.randint(60, 98)}%",
                "Emotional": f"{random.randint(60, 98)}%"
            }
        })
        random.seed(None)
        
    return results

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user:
        db.delete(user)
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404, detail="Not found")