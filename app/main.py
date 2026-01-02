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

load_dotenv()

# --- AI Configuration (The "Voice" Layer) ---
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
    
    # --- Biometric Identity (Layer 4 Deterministic Signature) ---
    palm_signature = Column(String, nullable=True) 
    palm_analysis = Column(String, nullable=True) 
    
    # --- Tradition Specific Toggles ---
    astro_pref = Column(String, default="Western")   
    num_pref = Column(String, default="Pythagorean") 
    palm_pref = Column(String, default="Western")    
    method_choice = Column(String, default="The Mix") 

    # --- Restored Fields for Accurate Logic ---
    birth_time = Column(String, nullable=True)      
    birth_location = Column(String, nullable=True)  
    full_legal_name = Column(String, nullable=True) 

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/nuke-database")
def nuke_database(db: Session = Depends(get_db)):
    """Wipes table to activate the Deterministic Pair-Unit schema."""
    try:
        db.execute(text("DROP TABLE IF EXISTS cosmic_profiles CASCADE;"))
        db.commit()
        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database schema aligned with 4-Layer Defense & 7-Factor logic."}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

async def analyze_palm_ai(image_bytes):
    """Fallback AI for descriptive reading (not for seeding)."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        prompt = "Perform a brief, poetic palm reading (Life, Heart, Head lines). Max 35 words."
        response = ai_model.generate_content([prompt, img])
        return response.text
    except:
        return "Your palm reveals a journey of unique potential and cosmic alignment."

@app.post("/signup-full")
async def signup(
    name: str = Form(...), 
    email: str = Form(...), 
    birthday: str = Form(...),
    palm_signature: str = Form(...), 
    astro_pref: str = Form("Western"),
    num_pref: str = Form("Pythagorean"),
    method_choice: str = Form("The Mix"),
    birth_time: str = Form(None),
    birth_location: str = Form(None),
    full_legal_name: str = Form(None),
    photos: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
    reading = "Cosmic alignment captured."
    if photos:
        try:
            photo_data = await photos[0].read()
            reading = await analyze_palm_ai(photo_data)
        except: pass

    try:
        date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
        user = db.query(User).filter(User.email == clean_email).first()
        if not user:
            user = User(email=clean_email)
            db.add(user)

        user.name, user.birthday = name, date_obj
        user.palm_signature = palm_signature # Seed for Biometric Stability
        user.palm_analysis = reading
        user.astro_pref, user.num_pref = astro_pref, num_pref
        user.method_choice = method_choice
        user.birth_time, user.birth_location, user.full_legal_name = birth_time, birth_location, full_legal_name
        
        db.commit()
        return {"message": "Success", "signature": palm_signature}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database Error")

@app.get("/feed")
async def get_feed(current_email: str, db: Session = Depends(get_db)):
    me = db.query(User).filter(User.email == current_email.strip().lower()).first()
    if not me: raise HTTPException(status_code=404, detail="User Not Found")
    
    # --- 1. CALCULATE INDIVIDUAL FATE (SELF) ---
    # Seed based ONLY on the individual's data for deterministic personal fate
    self_seed = str(me.birthday) + (me.palm_signature or "SELF_SEED")
    self_hash = hashlib.md5(self_seed.encode()).hexdigest()
    random.seed(int(self_hash, 16))
    
    self_results = {
        "name": "YOUR INDIVIDUAL FATE", 
        "percentage": "100%", 
        "tier": "Personal Destiny",
        "accuracy_level": "Individual Soul Map",
        "reading": "This is your independent cosmic path based on your biometric and temporal markers.",
        "factors": {
            "Foundation": f"{random.randint(40, 99)}%",
            "Economics": f"{random.randint(40, 99)}%",
            "Emotional": f"{random.randint(40, 99)}%",
            "Spiritual": f"{random.randint(40, 99)}%",
            "Physical": f"{random.randint(40, 99)}%",
            "Lifestyle": f"{random.randint(40, 99)}%",
            "Sexual": f"{random.randint(40, 99)}%"
        },
        "is_self": True
    }
    random.seed(None) # Reset seed

    # --- 2. CALCULATE MATCHES (OTHERS) ---
    others = db.query(User).filter(User.email != me.email).all()
    match_results = []

    for other in others:
        # PAIR-UNIT SYMMETRIC SEEDING: sorting ensures A+B = B+A (Perfect Symmetry)
        dates = sorted([str(me.birthday), str(other.birthday)])
        sigs = sorted([me.palm_signature or "S1", other.palm_signature or "S2"])
        
        seed_raw = "".join(dates) + "".join(sigs)
        seed_hash = hashlib.md5(seed_raw.encode()).hexdigest()
        
        random.seed(int(seed_hash, 16))
        tot = random.randint(65, 98)
        
        # Accuracy Scaling Logic based on provided fields
        has_astro = (me.birth_time and me.birth_location) or (other.birth_time and other.birth_location)
        has_num = me.full_legal_name or other.full_legal_name
        
        quality = "Base Accuracy (Palm)"
        if "Mix" in me.method_choice and has_astro and has_num:
            quality = "Ultimate Accuracy (Triple Path)"
        elif "Astro" in me.method_choice and has_astro:
            quality = "High Accuracy (Astrology Enhanced)"
        elif "Num" in me.method_choice and has_num:
            quality = "High Accuracy (Numerology Enhanced)"

        match_results.append({
            "name": other.name, 
            "percentage": f"{tot}%",
            "tier": "Marriage Material" if tot >= 90 else "Strong Match" if tot >= 78 else "Just Friends",
            "accuracy_level": quality,
            "reading": "Biometric update detected -> Shared destiny recalculated for the pair." if me.palm_signature else "Connection stable.",
            "factors": {
                "Foundation": f"{random.randint(60, 95)}%",
                "Economics": f"{random.randint(60, 95)}%",
                "Emotional": f"{random.randint(60, 98)}%",
                "Spiritual": f"{random.randint(60, 98)}%",
                "Physical": f"{random.randint(60, 98)}%",
                "Lifestyle": f"{random.randint(60, 95)}%",
                "Sexual": f"{random.randint(60, 98)}%"
            },
            "is_self": False
        })
        random.seed(None)
        
    # Return Self Fate at Index 0, followed by list of matches
    return [self_results] + match_results

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user:
        db.delete(user)
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404)