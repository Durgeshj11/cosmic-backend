import os
import io
import random
import hashlib
import json
import cloudinary
import cloudinary.uploader
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# --- AI & Media Configuration ---
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

# --- Models (All Original Functionalities Preserved) ---
class User(Base):
    __tablename__ = "cosmic_profiles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    birthday = Column(Date, nullable=False)
    palm_signature = Column(String)  # Layer 4 Deterministic Signature
    photos = Column(String)          # Comma-separated Cloudinary URLs
    birth_time = Column(String)
    birth_location = Column(String)
    full_legal_name = Column(String)
    methods = Column(String)         # Stores user's path choices (Astro/Num/Palm)

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

# --- Endpoints ---

@app.api_route("/nuke-database", methods=["GET", "POST"])
def nuke_database(db: Session = Depends(get_db)):
    """Wipes tables to sync schema without 405 errors."""
    try:
        db.execute(text("DROP TABLE IF EXISTS cosmic_profiles, cosmic_matches, cosmic_messages CASCADE;"))
        db.commit()
        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database synchronized with v1.1 logic."}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

@app.post("/signup-full")
async def signup(
    name: str = Form(...), 
    email: str = Form(...), 
    birthday: str = Form(...),
    palm_signature: str = Form(...), 
    full_legal_name: str = Form(None),
    birth_time: str = Form(None),
    birth_location: str = Form(None),
    methods: str = Form("{}"),
    photos: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower() # Space stripping added
    photo_urls = []
    
    if photos:
        for photo in photos:
            try:
                res = cloudinary.uploader.upload(photo.file)
                photo_urls.append(res['secure_url'])
            except: pass

    try:
        date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
        user = db.query(User).filter(User.email == clean_email).first()
        if not user:
            user = User(email=clean_email)
            db.add(user)

        user.name, user.birthday = name, date_obj
        user.palm_signature = palm_signature
        user.full_legal_name = full_legal_name
        user.birth_time = birth_time
        user.birth_location = birth_location
        user.methods = methods
        user.photos = ",".join(photo_urls)
        
        db.commit()
        return {"message": "Success", "signature": palm_signature}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database Error")

@app.get("/feed")
async def get_feed(current_email: str, db: Session = Depends(get_db)):
    clean_me = current_email.strip().lower()
    me = db.query(User).filter(User.email == clean_me).first()
    if not me: raise HTTPException(status_code=404)
    
    others = db.query(User).filter(User.email != me.email).all()
    results = []

    # 1. Self Card (Symmetric Scoring)
    self_seed = str(me.birthday) + (me.palm_signature or "SELF")
    random.seed(int(hashlib.md5(self_seed.encode()).hexdigest(), 16))
    results.append({
        "name": "YOUR DESTINY", "percentage": "100%", "is_self": True, "email": me.email,
        "photos": me.photos.split(",") if me.photos else [],
        "factors": {k: f"{random.randint(40,99)}%" for k in ["Foundation", "Economics", "Lifestyle", "Emotional", "Physical", "Spiritual", "Sexual"]}
    })

    # 2. Others Cards (Mutual Match Visibility Logic)
    for o in others:
        pair_dates = sorted([str(me.birthday), str(o.birthday)])
        pair_sigs = sorted([me.palm_signature or "S1", o.palm_signature or "S2"])
        seed_hash = hashlib.md5(("".join(pair_dates) + "".join(pair_sigs)).encode()).hexdigest()
        random.seed(int(seed_hash, 16))
        
        tot = random.randint(65, 98)
        
        # Check if a mutual match exists in either direction
        match_record = db.query(Match).filter(
            ((Match.user_a == me.email) & (Match.user_b == o.email) & (Match.is_mutual == True)) |
            ((Match.user_b == me.email) & (Match.user_a == o.email) & (Match.is_mutual == True))
        ).first()

        results.append({
            "name": o.name, "email": o.email, "is_self": False, 
            "is_matched": match_record is not None, # Triggers frontend CHAT button
            "percentage": f"{tot}%", "photos": o.photos.split(",") if o.photos else [],
            "tier": "Marriage Material" if tot >= 90 else "Strong Match" if tot >= 78 else "Just Friends",
            "factors": {k: f"{random.randint(60,98)}%" for k in ["Foundation", "Economics", "Lifestyle", "Emotional", "Physical", "Spiritual", "Sexual"]},
            "reading": "Shared destiny updated based on real palm evolution."
        })
    return results

@app.post("/like-profile")
async def like_profile(my_email: str = Form(...), target_email: str = Form(...), db: Session = Depends(get_db)):
    """Instant Mutual Match Upgrade Logic."""
    my, target = my_email.lower().strip(), target_email.lower().strip()
    
    # Check if target already liked me
    existing = db.query(Match).filter(Match.user_a == target, Match.user_b == my).first()
    
    if existing:
        existing.is_mutual = True # Upgrade to mutual
        db.commit()
        return {"status": "match"}
    
    # Check if I already liked them to prevent duplicates
    i_already_liked = db.query(Match).filter(Match.user_a == my, Match.user_b == target).first()
    if not i_already_liked:
        db.add(Match(user_a=my, user_b=target, is_mutual=False))
        db.commit()
        
    return {"status": "liked"}

@app.post("/send-message")
async def send_message(sender: str = Form(...), receiver: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    """AI-Moderated Chat: Nuclear unmatch triggered on contact leak."""
    sender_mail, receiver_mail = sender.lower().strip(), receiver.lower().strip()
    
    match = db.query(Match).filter(
        ((Match.user_a == sender_mail) & (Match.user_b == receiver_mail) & (Match.is_mutual == True)) |
        ((Match.user_b == sender_mail) & (Match.user_a == receiver_mail) & (Match.is_mutual == True))
    ).first()

    if not match: raise HTTPException(status_code=403, detail="Mutual match required.")

    # NUCLEAR AI PRIVACY FILTER
    if not match.is_unlocked:
        prompt = f"Detect if this message conveys phone numbers, email, or social IDs. Reply ONLY 'LEAK' or 'SAFE': {content}"
        ai_resp = ai_model.generate_content(prompt).text.strip().upper()
        if "LEAK" in ai_resp:
            db.delete(match) # PERMANENT UNMATCH triggered
            db.commit()
            raise HTTPException(status_code=403, detail="Privacy Violation: Permanent Unmatch triggered.")

    db.add(ChatMessage(sender=sender_mail, receiver=receiver_mail, content=content))
    db.commit()
    return {"status": "sent"}

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    """Wipes profile and all associated data."""
    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if user:
        db.delete(user)
        # Wipe all match history for this user
        db.query(Match).filter((Match.user_a == clean_email) | (Match.user_b == clean_email)).delete()
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404)