import os
import io
import random
import hashlib
import re
import cloudinary
import cloudinary.uploader
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, DateTime, text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# --- AI & Cloudinary Config ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
ai_model = genai.GenerativeModel('gemini-1.5-flash-latest')

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# --- Database Setup ---
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
    photos = Column(String)  # Store as comma-separated Cloudinary URLs
    birth_time = Column(String)
    birth_location = Column(String)
    full_legal_name = Column(String)
    methods = Column(String) # JSON stored as string

class Match(Base):
    __tablename__ = "cosmic_matches"
    id = Column(Integer, primary_key=True, index=True)
    user_a = Column(String, index=True) # Email 1
    user_b = Column(String, index=True) # Email 2
    is_mutual = Column(Boolean, default=False)
    is_unlocked = Column(Boolean, default=False) # Paid via Stripe

class ChatMessage(Base):
    __tablename__ = "cosmic_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String)
    receiver = Column(String)
    content = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- Security Filter ---
async def detect_leak(text: str):
    """AI deep-scan for phone, email, or social handles."""
    prompt = f"Identify if this text shares contact info (mobile, email, social ID). Reply ONLY 'LEAK' or 'SAFE': {text}"
    try:
        response = ai_model.generate_content(prompt)
        return "LEAK" in response.text.upper()
    except:
        return False

# --- Endpoints ---

@app.get("/nuke-database")
def nuke_database(db: Session = Depends(get_db)):
    db.execute(text("DROP TABLE IF EXISTS cosmic_profiles, cosmic_matches, cosmic_messages CASCADE;"))
    db.commit()
    Base.metadata.create_all(bind=engine)
    return {"status": "success"}

@app.post("/signup-full")
async def signup(
    name: str = Form(...), email: str = Form(...), birthday: str = Form(...),
    palm_signature: str = Form(...), photos: List[UploadFile] = File(None),
    full_legal_name: str = Form(None), birth_time: str = Form(None),
    birth_location: str = Form(None), methods: str = Form(""),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
    photo_urls = []
    if photos:
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
    user.full_legal_name, user.birth_time, user.birth_location = full_legal_name, birth_time, birth_location
    user.methods = methods
    db.commit()
    return {"message": "Success"}

@app.get("/feed")
async def get_feed(current_email: str, db: Session = Depends(get_db)):
    me = db.query(User).filter(User.email == current_email.strip().lower()).first()
    if not me: raise HTTPException(status_code=404)
    
    # Symmetric Matching Logic
    others = db.query(User).filter(User.email != me.email).all()
    results = []

    # Own Fate Card (Index 0)
    self_seed = str(me.birthday) + (me.palm_signature or "SELF")
    random.seed(int(hashlib.md5(self_seed.encode()).hexdigest(), 16))
    results.append({
        "name": "YOUR DESTINY", "percentage": "100%", "is_self": True,
        "photos": me.photos.split(",") if me.photos else [],
        "factors": {k: f"{random.randint(40,99)}%" for k in ["Foundation", "Economics", "Lifestyle", "Emotional", "Physical", "Spiritual", "Sexual"]}
    })

    for o in others:
        pair_dates = sorted([str(me.birthday), str(o.birthday)])
        pair_sigs = sorted([me.palm_signature or "S1", o.palm_signature or "S2"])
        seed_raw = "".join(pair_dates) + "".join(pair_sigs)
        random.seed(int(hashlib.md5(seed_raw.encode()).hexdigest(), 16))
        tot = random.randint(65, 98)

        match_info = db.query(Match).filter(
            ((Match.user_a == me.email) & (Match.user_b == o.email) & (Match.is_mutual == True)) |
            ((Match.user_b == me.email) & (Match.user_a == o.email) & (Match.is_mutual == True))
        ).first()

        results.append({
            "name": o.name, "email": o.email, "is_self": False, "is_matched": match_info is not None,
            "percentage": f"{tot}%", "photos": o.photos.split(",") if o.photos else [],
            "tier": "Marriage Material" if tot >= 90 else "Strong Match" if tot >= 78 else "Just Friends",
            "factors": {k: f"{random.randint(60,98)}%" for k in ["Foundation", "Economics", "Lifestyle", "Emotional", "Physical", "Spiritual", "Sexual"]},
            "reading": "Shared destiny updated based on real palm evolution."
        })
    return results

@app.post("/like-profile")
async def like_profile(my_email: str = Form(...), target_email: str = Form(...), db: Session = Depends(get_db)):
    existing = db.query(Match).filter(Match.user_a == target_email, Match.user_b == my_email).first()
    if existing:
        existing.is_mutual = True
        db.commit()
        return {"status": "match"}
    
    db.add(Match(user_a=my_email, user_b=target_email))
    db.commit()
    return {"status": "liked"}

@app.post("/send-message")
async def send_message(sender: str = Form(...), receiver: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    match = db.query(Match).filter(
        ((Match.user_a == sender) & (Match.user_b == receiver)) |
        ((Match.user_a == receiver) & (Match.user_b == sender))
    ).first()

    if not match or not match.is_mutual: raise HTTPException(status_code=403)

    if not match.is_unlocked and await detect_leak(content):
        # NUCLEAR OPTION: Permanent Unmatch
        db.delete(match)
        db.commit()
        raise HTTPException(status_code=403, detail="Permanent Unmatch triggered by Privacy Violation.")

    msg = ChatMessage(sender=sender, receiver=receiver, content=content)
    db.add(msg)
    db.commit()
    return {"status": "sent"}

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user:
        db.delete(user)
        # Cascade logic
        db.query(Match).filter((Match.user_a == email) | (Match.user_b == email)).delete()
        db.query(ChatMessage).filter((ChatMessage.sender == email) | (ChatMessage.receiver == email)).delete()
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404)