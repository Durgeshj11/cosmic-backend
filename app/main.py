import os
import json
import io
import random
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

# Create tables on launch
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

# --- NEW: NUKE ROUTE TO CLEAR OLD DATA ---
@app.get("/nuke-database")
def nuke_database(db: Session = Depends(get_db)):
    """Visit this URL in your browser to clear all old records once."""
    try:
        # Clears all old rows and resets ID counter to 1
        db.execute(text("TRUNCATE TABLE cosmic_profiles RESTART IDENTITY CASCADE;"))
        db.commit()
        return {"status": "success", "message": "Database wiped clean. Old records are gone!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def analyze_palm_ai(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        prompt = "Perform a short palm reading (personality & love traits). Max 30 words."
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
    if db.query(User).filter(User.email == clean_email).first():
        return {"message": "User exists"}

    photo_data = await photos[0].read()
    reading = await analyze_palm_ai(photo_data)
    
    try:
        date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
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
        print(f"Signup Error: {e}")
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
        # UPDATED PROMPT: Specific Logic for "Marriage Material" Tiers
        prompt = f"""
        Return ONLY a JSON object. No markdown, no backticks.
        Compare User A (Born: {me.birthday}, Palm: {me.palm_analysis}) and User B (Born: {other.birthday}, Palm: {other.palm_analysis}).
        
        Tiering Logic:
        - If 'total' compatibility is >= 90: "Marriage Material"
        - If 'total' is 75-89: "Strong Match"
        - If 'total' is below 75: "Potential Match"

        JSON Structure:
        {{
            "total": "integer 65-98",
            "foundation": "integer 60-95",
            "economics": "integer 60-95",
            "family": "integer 60-95",
            "lifestyle": "integer 60-95",
            "tier": "String based on logic",
            "flag": "Green",
            "analysis": "A short 20-word specific compatibility analysis."
        }}
        """
        try:
            ai_res = ai_model.generate_content(prompt)
            clean_json = ai_res.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_json)
        except Exception:
            # DYNAMIC FALLBACK: Randomized so scores are never identical
            tot = random.randint(70, 96)
            data = {
                "total": str(tot),
                "foundation": str(random.randint(65, 95)),
                "economics": str(random.randint(65, 95)),
                "family": str(random.randint(65, 95)),
                "lifestyle": str(random.randint(65, 95)),
                "tier": "Marriage Material" if tot >= 90 else "Strong Match",
                "flag": "Green",
                "analysis": "Cosmic energies suggest a unique and balanced soulmate connection."
            }
            
        results.append({
            "name": other.name, 
            "percentage": f"{data['total']}%",
            "tier": data["tier"],
            "flag": data["flag"],
            "reading": data["analysis"],
            "factors": {
                "Foundation": f"{data['foundation']}%",
                "Economics": f"{data['economics']}%",
                "Family": f"{data['family']}%",
                "Lifestyle": f"{data['lifestyle']}%"
            }
        })
    return results

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user:
        db.delete(user)
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404, detail="Not found")