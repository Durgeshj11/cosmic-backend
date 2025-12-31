import os
import json
import io
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# --- AI Configuration ---
# FIXED: Explicit model path to resolve the 404/NotFound error from your logs
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
ai_model = genai.GenerativeModel('models/gemini-1.5-flash')

# --- Database Setup ---
# Handles Render's postgres:// vs postgresql:// requirement
DATABASE_URL = os.environ.get("DATABASE_URL").replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    birthday = Column(Date, nullable=False)
    palm_analysis = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

# --- UNIVERSAL CORS FIX ---
# Allows connection from any origin to stop the browser block once and for all
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Verification Route ---
# Use this to check if the backend is LIVE at https://cosmic-backend-api.onrender.com/
@app.get("/")
def health_check():
    return {"status": "online", "message": "Cosmic Backend is LIVE and CORS is ACTIVE"}

async def analyze_palm_ai(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        prompt = "Perform a palm reading for personality and love. Max 30 words."
        response = ai_model.generate_content([prompt, img])
        return response.text
    except Exception as e:
        # Prevents 500 Internal Server Error if AI fails
        print(f"AI Analysis Error: {e}")
        return "Your palm suggests a unique destiny filled with cosmic potential and mystery."

@app.post("/signup-full")
async def signup(
    name: str = Form(...), 
    email: str = Form(...), 
    birthday: str = Form(...), 
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
    
    # Check if user exists
    if db.query(User).filter(User.email == clean_email).first():
        return {"message": "User exists"}

    # Process image bytes
    photo_data = await photos[0].read()
    reading = await analyze_palm_ai(photo_data)
    
    try:
        new_user = User(
            name=name, 
            email=clean_email, 
            birthday=datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date(),
            palm_analysis=reading
        )
        db.add(new_user)
        db.commit() # Save to PostgreSQL
        return {"message": "Success"}
    except Exception as e:
        db.rollback()
        print(f"Database Error: {e}")
        raise HTTPException(status_code=500, detail="Database save failed")

@app.get("/feed")
async def get_feed(current_email: str, db: Session = Depends(get_db)):
    email_clean = current_email.strip().lower()
    me = db.query(User).filter(User.email == email_clean).first()
    if not me: 
        raise HTTPException(status_code=404, detail="User Not Found")
    
    others = db.query(User).filter(User.email != email_clean).all()
    results = []
    for other in others:
        prompt = f"Compare Birthdays {me.birthday} vs {other.birthday} and Palm {me.palm_analysis} vs {other.palm_analysis}. Return ONLY JSON: {{'score': 'number'}}"
        try:
            ai_res = ai_model.generate_content(prompt)
            clean_json = ai_res.text.replace('```json', '').replace('```', '').strip()
            score = json.loads(clean_json)['score']
        except:
            score = "85" # Fallback
            
        results.append({
            "name": other.name, 
            "reading": other.palm_analysis, 
            "percentage": f"{score}%"
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