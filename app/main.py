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

# --- Models (Updated for Dual-Paid Gating & Acceptance) ---
class User(Base):
    __tablename__ = "cosmic_profiles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    birthday = Column(Date, nullable=False)
    palm_signature = Column(String)  
    photos = Column(String)          
    birth_time = Column(String)
    birth_location = Column(String)
    full_legal_name = Column(String)
    methods = Column(String)         

class Match(Base):
    __tablename__ = "cosmic_matches"
    id = Column(Integer, primary_key=True, index=True)
    user_a = Column(String, index=True) 
    user_b = Column(String, index=True) 
    is_mutual = Column(Boolean, default=False)
    is_unlocked = Column(Boolean, default=False) # Global Unlock (Bypasses AI Filter)
    
    # NEW: Tracking for Dual-Paid Gate & Acceptance
    user_a_accepted = Column(Boolean, default=False)
    user_b_accepted = Column(Boolean, default=False)
    request_initiated_by = Column(String) # Track who started the chat request

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
    try:
        db.execute(text("DROP TABLE IF EXISTS cosmic_profiles, cosmic_matches, cosmic_messages CASCADE;"))
        db.commit()
        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database synchronized with v1.2 Monetization logic."}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

@app.post("/signup-full")
async def signup(
    name: str = Form(...), email: str = Form(...), birthday: str = Form(...),
    palm_signature: str = Form(...), full_legal_name: str = Form(None),
    birth_time: str = Form(None), birth_location: str = Form(None),
    methods: str = Form("{}"), photos: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
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
        user.palm_signature, user.full_legal_name = palm_signature, full_legal_name
        user.birth_time, user.birth_location = birth_time, birth_location
        user.methods, user.photos = methods, ",".join(photo_urls)
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

    # 1. Self Card
    self_seed = str(me.birthday) + (me.palm_signature or "SELF")
    random.seed(int(hashlib.md5(self_seed.encode()).hexdigest(), 16))
    results.append({
        "name": "YOUR DESTINY", "percentage": "100%", "is_self": True, "email": me.email,
        "photos": me.photos.split(",") if me.photos else [],
        "factors": {k: f"{random.randint(40,99)}%" for k in ["Foundation", "Economics", "Lifestyle", "Emotional", "Physical", "Spiritual", "Sexual"]}
    })

    # 2. Match Feed with Symmetric Visibility
    for o in others:
        pair_dates = sorted([str(me.birthday), str(o.birthday)])
        pair_sigs = sorted([me.palm_signature or "S1", o.palm_signature or "S2"])
        seed_hash = hashlib.md5(("".join(pair_dates) + "".join(pair_sigs)).encode()).hexdigest()
        random.seed(int(seed_hash, 16))
        tot = random.randint(65, 98)
        
        # Symmetric Visibility: Button appears for both once mutual
        match_record = db.query(Match).filter(
            ((Match.user_a == me.email) & (Match.user_b == o.email) & (Match.is_mutual == True)) |
            ((Match.user_b == me.email) & (Match.user_a == o.email) & (Match.is_mutual == True))
        ).first()

        results.append({
            "name": o.name, "email": o.email, "is_self": False, 
            "is_matched": match_record is not None, 
            "percentage": f"{tot}%", "photos": o.photos.split(",") if o.photos else [],
            "tier": "Marriage Material" if tot >= 90 else "Strong Match",
            "factors": {k: f"{random.randint(60,98)}%" for k in ["Foundation", "Economics", "Lifestyle", "Emotional", "Physical", "Spiritual", "Sexual"]},
            "reading": "Shared destiny updated based on real palm evolution."
        })
    return results

@app.post("/like-profile")
async def like_profile(my_email: str = Form(...), target_email: str = Form(...), db: Session = Depends(get_db)):
    """Unlimited free likes."""
    my, target = my_email.lower().strip(), target_email.lower().strip()
    existing = db.query(Match).filter(Match.user_a == target, Match.user_b == my).first()
    if existing:
        existing.is_mutual = True
        db.commit()
        return {"status": "match"}
    i_already_liked = db.query(Match).filter(Match.user_a == my, Match.user_b == target).first()
    if not i_already_liked:
        db.add(Match(user_a=my, user_b=target, is_mutual=False))
        db.commit()
    return {"status": "liked"}

@app.get("/chat-status")
async def chat_status(me: str, them: str, db: Session = Depends(get_db)):
    """Acceptance Gate: Checks if user has accepted the 3rd person limit."""
    me, them = me.lower().strip(), them.lower().strip()
    
    # Count unique engagements for the Dual-Paid Gate
    engaged_count = db.query(Match).filter(
        ((Match.user_a == me) & ((Match.user_a_accepted == True) | (Match.request_initiated_by == me))) |
        ((Match.user_b == me) & ((Match.user_b_accepted == True) | (Match.request_initiated_by == me)))
    ).count()

    match = db.query(Match).filter(
        ((Match.user_a == me) & (Match.user_b == them)) |
        ((Match.user_b == me) & (Match.user_a == them))
    ).first()
    
    accepted = False
    if match:
        accepted = match.user_a_accepted if match.user_a == me else match.user_b_accepted
        
    return {
        "accepted": accepted,
        "engaged_count": engaged_count,
        "is_paid": match.is_unlocked if match else False
    }

@app.post("/accept-chat")
async def accept_chat(me: str = Form(...), them: str = Form(...), is_paid: bool = Form(False), db: Session = Depends(get_db)):
    """Handles logic for free vs paid chat acceptances."""
    me, them = me.lower().strip(), them.lower().strip()
    
    # Check engagement limit (3rd person costs money)
    engaged_query = db.query(Match).filter(
        ((Match.user_a == me) & ((Match.user_a_accepted == True) | (Match.request_initiated_by == me))) |
        ((Match.user_b == me) & ((Match.user_b_accepted == True) | (Match.request_initiated_by == me)))
    )
    engaged_count = engaged_query.count()

    match = db.query(Match).filter(
        ((Match.user_a == me) & (Match.user_b == them)) |
        ((Match.user_b == me) & (Match.user_a == them))
    ).first()

    if not match: raise HTTPException(status_code=404, detail="Match not found")

    # Gate logic: if not already talking to this person and count >= 2, require payment
    is_new_engagement = not ((match.user_a == me and match.user_a_accepted) or 
                             (match.user_b == me and match.user_b_accepted) or 
                             (match.request_initiated_by == me))
    
    if is_new_engagement and engaged_count >= 2 and not is_paid:
        return {"status": "payment_required", "engaged_count": engaged_count}

    if match.user_a == me: match.user_a_accepted = True
    else: match.user_b_accepted = True
    
    if is_paid: match.is_unlocked = True # Mark as premium
    db.commit()
    return {"status": "accepted"}

@app.post("/send-message")
async def send_message(sender: str = Form(...), receiver: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    sender_mail, receiver_mail = sender.lower().strip(), receiver.lower().strip()
    match = db.query(Match).filter(
        ((Match.user_a == sender_mail) & (Match.user_b == receiver_mail) & (Match.is_mutual == True)) |
        ((Match.user_b == sender_mail) & (Match.user_a == receiver_mail) & (Match.is_mutual == True))
    ).first()

    if not match: raise HTTPException(status_code=403, detail="Mutual match required.")

    # Nuclear filter bypass if is_unlocked
    if not match.is_unlocked:
        prompt = f"Reply ONLY 'LEAK' or 'SAFE': {content}"
        ai_resp = ai_model.generate_content(prompt).text.strip().upper()
        if "LEAK" in ai_resp:
            db.delete(match); db.commit()
            raise HTTPException(status_code=403, detail="Privacy Violation.")

    db.add(ChatMessage(sender=sender_mail, receiver=receiver_mail, content=content))
    db.commit()
    return {"status": "sent"}

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if user:
        db.delete(user)
        db.query(Match).filter((Match.user_a == clean_email) | (Match.user_b == clean_email)).delete()
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404)