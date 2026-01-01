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

# --- AI Configuration (Fixed for 404/Model-Not-Found Errors) ---
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

# Initialize database tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

# UNIVERSAL CORS FIX: Vital for Flutter Web/Mobile
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
        return {"status": "success", "message": "Database wiped clean. IDs and seeds reset."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def analyze_palm_ai(image_bytes):
    """Replicates a healthy human eye with a safety fallback."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        prompt = "Perform a detailed palm reading (Life, Heart, and Head lines). Max 40 words."
        response = ai_model.generate_content([prompt, img])
        return response.text
    except Exception as e:
        print(f"AI Model Error Fallback: {e}")
        return "Your palm reveals a journey of unique potential and cosmic alignment."

@app.post("/signup-full")
async def signup(
    name: str = Form(...), 
    email: str = Form(...), 
    birthday: str = Form(...), 
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
    
    # 1. Process Palm Photo
    try:
        photo_data = await photos[0].read()
        reading = await analyze_palm_ai(photo_data)
    except:
        reading = "Biological data captured. Alignment pending."

    try:
        # 2. Robust Date Parsing
        date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
        
        # 3. Evolution Support (Update or Create)
        existing_user = db.query(User).filter(User.email == clean_email).first()

        if existing_user:
            existing_user.name = name
            existing_user.birthday = date_obj
            existing_user.palm_analysis = reading
            db.commit()
            return {"message": "Success"}

        new_user = User(
            name=name, email=clean_email, birthday=date_obj, palm_analysis=reading
        )
        db.add(new_user)
        db.commit()
        return {"message": "Success"}
    except Exception as e:
        db.rollback()
        print(f"Signup Database Error: {e}")
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
        # --- THE DETERMINISTIC DESTINY LOGIC ---
        # Sorting birth dates ensures Symmetry
        birth_seeds = "".join(sorted([str(me.birthday), str(other.birthday)]))
        palm_seeds = (me.palm_analysis or "p") + (other.palm_analysis or "p")
        
        # MD5 Hashing locks all 6 factors to this pair
        seed_hash = hashlib.md5((birth_seeds + palm_seeds).encode()).hexdigest()
        random.seed(int(seed_hash, 16)) 
        
        tot = random.randint(65, 98)
        
        # 6 Factors: Random but seeded (permanent for the pair)
        fnd = random.randint(60, 95)
        eco = random.randint(60, 95)
        fam = random.randint(60, 95)
        lst = random.randint(60, 95)
        sxu = random.randint(60, 98) # Sexual Compatibility
        emo = random.randint(60, 98) # Emotional Compatibility

        if tot >= 90: tier = "Marriage Material"
        elif tot >= 78: tier = "Strong Match"
        elif tot >= 68: tier = "Fling / Casual"
        else: tier = "Just Friends"

        results.append({
            "name": other.name, 
            "percentage": f"{tot}%",
            "tier": tier,
            "reading": "Your connection is written in the physical alignment of your life paths.",
            "factors": {
                "Foundation": f"{fnd}%",
                "Economics": f"{eco}%",
                "Family": f"{fam}%",
                "Lifestyle": f"{lst}%",
                "Sexual": f"{sxu}%",
                "Emotional": f"{emo}%"
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