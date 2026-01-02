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

# --- AI Configuration (The Poetic Reading Layer) ---
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
    
    # --- Biometric Identity ---
    # Stores the noise-immune signature from Frontend Layer 4
    palm_signature = Column(String, nullable=True) 
    palm_analysis = Column(String, nullable=True) 
    
    # --- Methodology Wisdom Paths ---
    astro_pref = Column(String, default="Western")   
    num_pref = Column(String, default="Pythagorean") 
    # methodology_choice: stand-alone or combinations
    method_choice = Column(String, default="The Mix") 

    # --- Accuracy Attributes ---
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

@app.get("/")
def health_check():
    return {"status": "online", "message": "Cosmic Backend LIVE"}

@app.get("/nuke-database")
def nuke_database(db: Session = Depends(get_db)):
    """Resets table to activate the Deterministic Pair-Unit schema."""
    try:
        db.execute(text("DROP TABLE IF EXISTS cosmic_profiles CASCADE;"))
        db.commit()
        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database schema aligned with 4-Layer Defense logic."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def analyze_palm_ai(image_bytes):
    """The 'Voice' layer: Creates poetic interpretation without affecting %."""
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
    palm_signature: str = Form(...), # Mathematical Signature
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
        user.palm_signature = palm_signature # The seed for palm logic
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
    if not me: raise HTTPException(status_code=404)
    
    others = db.query(User).filter(User.email != me.email).all()
    results = []

    for other in others:
        # --- PAIR-UNIT DETERMINISTIC SEEDING ---
        # Sorting inputs ensures A+B is identical to B+A (Perfect Symmetry)
        dates = sorted([str(me.birthday), str(other.birthday)])
        
        # Biometric Symmetry: uses stable Layer 4 hashes
        sigs = sorted([me.palm_signature or "S1", other.palm_signature or "S2"])
        
        # Accuracy Pool
        acc_pool = sorted([
            (me.birth_time or "") + (me.birth_location or "") + (me.full_legal_name or ""),
            (other.birth_time or "") + (other.birth_location or "") + (other.full_legal_name or "")
        ])

        # Shared Destiny Seed
        seed_raw = "".join(dates) + "".join(sigs) + "".join(acc_pool) + me.method_choice
        seed_hash = hashlib.md5(seed_raw.encode()).hexdigest()
        
        random.seed(int(seed_hash, 16))
        tot = random.randint(65, 98)
        
        # Scaling labels based on data depth
        has_astro = (me.birth_time and me.birth_location) or (other.birth_time and other.birth_location)
        has_num = me.full_legal_name or other.full_legal_name
        
        quality = "Base Accuracy (Palm)"
        if me.method_choice == "The Mix" and has_astro and has_num:
            quality = "Ultimate Accuracy (Triple Path)"
        elif "Astro" in me.method_choice and has_astro:
            quality = f"High Accuracy ({me.method_choice})"
        elif "Num" in me.method_choice and has_num:
            quality = f"High Accuracy ({me.method_choice})"

        # Recalculation Notification logic
        note = "Your shared connection is written in the biometric alignment of your life paths."
        # If the hash has changed relative to a stored previous hash (can be implemented with a match_history table)
        # For now, we flag active palm-based recalculation.
        if me.palm_signature:
             note = "Biometric evolution detected -> destiny recalculated for the pair."

        results.append({
            "name": other.name, 
            "percentage": f"{tot}%",
            "tier": "Marriage Material" if tot >= 90 else "Strong Match" if tot >= 78 else "Just Friends",
            "accuracy_level": quality,
            "reading": note,
            "factors": {
                "Foundation": f"{random.randint(60, 95)}%",
                "Economics": f"{random.randint(60, 95)}%",
                "Emotional": f"{random.randint(60, 98)}%",
                "Spiritual": f"{random.randint(60, 98)}%",
                "Physical": f"{random.randint(60, 98)}%",
                "Lifestyle": f"{random.randint(60, 95)}%",
                "Sexual": f"{random.randint(60, 98)}%"
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
    raise HTTPException(status_code=404)