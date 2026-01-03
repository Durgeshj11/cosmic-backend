import os
import io
import random
import hashlib
import re
import json
import cloudinary
import cloudinary.uploader
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# --- Configurations ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
ai_model = genai.GenerativeModel('gemini-1.5-flash-latest')

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# --- Database Setup ---
DATABASE_URL = os.environ.get("DATABASE_URL").replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Models ---
class User(Base):
    __tablename__ = "cosmic_profiles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    birthday = Column(Date, nullable=False)
    palm_signature = Column(String)
    palm_analysis = Column(String)
    photos = Column(String)  # Comma-separated Cloudinary URLs
    birth_time = Column(String)
    birth_location = Column(String)
    full_legal_name = Column(String)

class Match(Base):
    __tablename__ = "cosmic_matches"
    id = Column(Integer, primary_key=True, index=True)
    user_a = Column(String, index=True) 
    user_b = Column(String, index=True)
    is_mutual = Column(Boolean, default=False)
    is_unlocked = Column(Boolean, default=False) # Paid to share info

class ChatMessage(Base):
    __tablename__ = "cosmic_messages"
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, index=True)
    sender_email = Column(String)
    content = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- AI Safety Interceptor ---
async def check_for_privacy_leak(text_content: str):
    """Detects leaks via Regex and Gemini AI deep-scan."""
    regex_leak = re.search(r"(\b\d{10}\b|\+?\d{1,3}[\s\-]?\d{6,}|@[\w]+|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b)", text_content)
    if regex_leak: return True

    prompt = f"Does this message share a phone number, email, or social handle? Answer ONLY 'YES' or 'NO': {text_content}"
    try:
        response = ai_model.generate_content(prompt)
        return "YES" in response.text.upper()
    except: return False

# --- API Endpoints ---

@app.get("/nuke-database")
def nuke_database(db: Session = Depends(get_db)):
    db.execute(text("DROP TABLE IF EXISTS cosmic_profiles, cosmic_matches, cosmic_messages CASCADE;"))
    db.commit()
    Base.metadata.create_all(bind=engine)
    return {"status": "success", "message": "Database reset for matching & chat."}

@app.post("/signup-full")
async def signup(
    name: str = Form(...), email: str = Form(...), birthday: str = Form(...),
    palm_signature: str = Form(...), photos: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
    photo_urls = []
    
    if photos: # Multi-photo upload logic
        for photo in photos:
            res = cloudinary.uploader.upload(photo.file)
            photo_urls.append(res['secure_url'])
    
    date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        user = User(email=clean_email)
        db.add(user)
    
    user.name, user.birthday = name, date_obj
    user.palm_signature = palm_signature
    user.photos = ",".join(photo_urls)
    db.commit()
    return {"message": "Success"}

@app.post("/like-profile")
async def like_profile(my_email: str = Form(...), target_email: str = Form(...), db: Session = Depends(get_db)):
    """Handles mutual match unlocking."""
    my_email, target_email = my_email.lower(), target_email.lower()
    existing = db.query(Match).filter(Match.user_a == target_email, Match.user_b == my_email).first()
    if existing:
        existing.is_mutual = True
        db.commit()
        return {"status": "match"}
    
    new_match = Match(user_a=my_email, user_b=target_email)
    db.add(new_match)
    db.commit()
    return {"status": "liked"}

@app.post("/send-message")
async def send_message(sender: str = Form(...), receiver: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    """Immediate unmatch on privacy leak detection."""
    sender, receiver = sender.lower(), receiver.lower()
    match = db.query(Match).filter(
        ((Match.user_a == sender) & (Match.user_b == receiver)) |
        ((Match.user_b == sender) & (Match.user_a == receiver))
    ).first()

    if not match or not match.is_mutual:
        raise HTTPException(status_code=403, detail="Mutual match required.")

    # Privacy Check
    if not match.is_unlocked:
        if await check_for_privacy_leak(content):
            db.delete(match) # IMMEDIATE PERMANENT UNMATCH
            db.commit()
            return {"status": "banned", "message": "Violation: Immediate Unmatch Triggered."}

    msg = ChatMessage(match_id=match.id, sender_email=sender, content=content)
    db.add(msg)
    db.commit()
    return {"status": "sent"}

@app.get("/feed")
async def get_feed(current_email: str, db: Session = Depends(get_db)):
    me = db.query(User).filter(User.email == current_email.strip().lower()).first()
    if not me: raise HTTPException(status_code=404)
    
    self_seed = str(me.birthday) + (me.palm_signature or "S1")
    random.seed(int(hashlib.md5(self_seed.encode()).hexdigest(), 16))
    
    self_results = {
        "name": "YOUR DESTINY", "percentage": "100%", "is_self": True,
        "photos": me.photos.split(",") if me.photos else [],
        "factors": {"Foundation": f"{random.randint(60,99)}%", "Economics": f"{random.randint(60,99)}%"}
    }
    
    others = db.query(User).filter(User.email != me.email).all()
    match_results = []
    for o in others:
        match = db.query(Match).filter(
            ((Match.user_a == me.email) & (Match.user_b == o.email) & (Match.is_mutual == True)) |
            ((Match.user_b == me.email) & (Match.user_a == o.email) & (Match.is_mutual == True))
        ).first()

        match_results.append({
            "name": o.name, "email": o.email, "is_self": False, 
            "is_matched": True if match else False,
            "photos": o.photos.split(",") if o.photos else [],
            "percentage": f"{random.randint(65, 98)}%"
        })
    return [self_results] + match_results

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user:
        db.delete(user)
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404)