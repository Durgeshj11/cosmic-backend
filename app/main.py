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

# --- Models ---
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
    is_unlocked = Column(Boolean, default=False) # Bypasses AI Filter
    user_a_accepted = Column(Boolean, default=False)
    user_b_accepted = Column(Boolean, default=False)
    request_initiated_by = Column(String) 

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

# --- HIGH STABILITY CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With", "Access-Control-Allow-Origin"],
    max_age=600, 
)

# --- Helper Logic for Cosmic Data ---
def get_sun_sign(day, month):
    signs = [
        (20, "Capricorn"), (19, "Aquarius"), (20, "Pisces"), (20, "Aries"),
        (21, "Taurus"), (21, "Gemini"), (22, "Cancer"), (23, "Leo"),
        (23, "Virgo"), (23, "Libra"), (22, "Scorpio"), (22, "Sagittarius")
    ]
    return signs[month-1][1] if day > signs[month-1][0] else signs[month-2][1]

def get_life_path(dob_str):
    nums = [int(d) for d in dob_str if d.isdigit()]
    total = sum(nums)
    while total > 9:
        total = sum(int(d) for d in str(total))
    return total

# --- Endpoints ---

@app.api_route("/nuke-database", methods=["GET", "POST"])
def nuke_database(db: Session = Depends(get_db)):
    try:
        db.execute(text("DROP TABLE IF EXISTS cosmic_profiles, cosmic_matches, cosmic_messages CASCADE;"))
        db.commit()
        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database synchronized."}
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
                file_content = await photo.read()
                res = cloudinary.uploader.upload(file_content)
                photo_urls.append(res['secure_url'])
            except: pass

    try:
        date_str = birthday.split(" ")[0]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/feed")
async def get_feed(current_email: str, db: Session = Depends(get_db)):
    clean_me = current_email.strip().lower()
    if clean_me in ["ping", "warmup"]: return {"status": "ready"}
    me = db.query(User).filter(User.email == clean_me).first()
    if not me: raise HTTPException(status_code=404)
    others = db.query(User).filter(User.email != me.email).all()
    results = []

    # THE 12 COSMIC POINTS
    factor_labels = [
        "Health", "Power", "Creativity", "Social", "Emotional", "Mental",
        "Lifestyle", "Spiritual", "Sexual", "Family", "Economic", "Foundation"
    ]

    for o in others:
        pair_dates = sorted([str(me.birthday), str(o.birthday)])
        pair_sigs = sorted([me.palm_signature or "S1", o.palm_signature or "S2"])
        seed_hash = hashlib.md5(("".join(pair_dates) + "".join(pair_sigs)).encode()).hexdigest()
        random.seed(int(seed_hash, 16))
        tot = random.randint(65, 98)
        
        match_record = db.query(Match).filter(
            ((Match.user_a == me.email) & (Match.user_b == o.email) & (Match.is_mutual == True)) |
            ((Match.user_b == me.email) & (Match.user_a == o.email) & (Match.is_mutual == True))
        ).first()

        results.append({
            "name": o.name, "email": o.email, "is_self": False, 
            "is_matched": match_record is not None, 
            "percentage": f"{tot}%", "photos": o.photos.split(",") if o.photos else [],
            "sun_sign": get_sun_sign(o.birthday.day, o.birthday.month),
            "life_path": get_life_path(str(o.birthday)),
            "tier": "Marriage Material" if tot >= 90 else "Strong Match",
            "factors": {k: f"{random.randint(60,98)}%" for k in factor_labels},
            "reading": "Shared destiny updated based on real palm evolution."
        })
    return results

@app.post("/like-profile")
async def like_profile(my_email: str = Form(...), target_email: str = Form(...), db: Session = Depends(get_db)):
    my, target = my_email.lower().strip(), target_email.lower().strip()
    existing = db.query(Match).filter(Match.user_a == target, Match.user_b == my).first()
    if existing:
        existing.is_mutual = True
        if not existing.request_initiated_by: existing.request_initiated_by = target
        db.commit()
        return {"status": "match"}
    i_already_liked = db.query(Match).filter(Match.user_a == my, Match.user_b == target).first()
    if not i_already_liked:
        db.add(Match(user_a=my, user_b=target, is_mutual=False, request_initiated_by=my))
        db.commit()
    return {"status": "liked"}

@app.get("/chat-status")
async def chat_status(me: str, them: str, db: Session = Depends(get_db)):
    me, them = me.lower().strip(), them.lower().strip()
    match = db.query(Match).filter(
        ((Match.user_a == me) & (Match.user_b == them)) |
        ((Match.user_b == me) & (Match.user_a == them))
    ).first()

    is_globally_accepted = match.user_a_accepted or match.user_b_accepted if match else False
    engaged_count = db.query(Match).filter(
        ((Match.user_a == me) & (Match.user_a_accepted == True)) |
        ((Match.user_b == me) & (Match.user_b_accepted == True))
    ).count()
        
    return {
        "accepted": is_globally_accepted,
        "engaged_count": engaged_count,
        "is_paid": match.is_unlocked if match else False
    }

@app.post("/accept-chat")
async def accept_chat(me: str = Form(...), them: str = Form(...), is_paid: bool = Form(False), db: Session = Depends(get_db)):
    me, them = me.lower().strip(), them.lower().strip()
    match = db.query(Match).filter(
        ((Match.user_a == me) & (Match.user_b == them)) |
        ((Match.user_b == me) & (Match.user_a == them))
    ).first()
    if not match: raise HTTPException(status_code=404)

    engaged_count = db.query(Match).filter(
        ((Match.user_a == me) & (Match.user_a_accepted == True)) |
        ((Match.user_b == me) & (Match.user_b_accepted == True))
    ).count()

    if engaged_count >= 2 and not is_paid and not (match.user_a_accepted or match.user_b_accepted):
        return {"status": "payment_required", "engaged_count": engaged_count}

    if match.user_a == me: match.user_a_accepted = True
    else: match.user_b_accepted = True
    if is_paid: match.is_unlocked = True 
    db.commit()
    return {"status": "accepted"}

@app.get("/messages")
async def get_messages(me: str, them: str, db: Session = Depends(get_db)):
    me, them = me.lower().strip(), them.lower().strip()
    msgs = db.query(ChatMessage).filter(
        ((ChatMessage.sender == me) & (ChatMessage.receiver == them)) |
        ((ChatMessage.sender == them) & (ChatMessage.receiver == me))
    ).order_by(ChatMessage.timestamp.asc()).all()
    return [{"sender": m.sender, "content": m.content, "time": m.timestamp.isoformat()} for m in msgs]

@app.post("/send-message")
async def send_message(sender: str = Form(...), receiver: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    s_mail, r_mail = sender.lower().strip(), receiver.lower().strip()
    match = db.query(Match).filter(
        ((Match.user_a == s_mail) & (Match.user_b == r_mail) & (Match.is_mutual == True)) |
        ((Match.user_b == s_mail) & (Match.user_a == r_mail) & (Match.is_mutual == True))
    ).first()
    if not match: raise HTTPException(status_code=403, detail="Mutual match required.")

    if not match.is_unlocked:
        prompt = f"Reply ONLY 'LEAK' or 'SAFE': {content}"
        ai_resp = ai_model.generate_content(prompt).text.strip().upper()
        if "LEAK" in ai_resp:
            db.delete(match); db.commit()
            raise HTTPException(status_code=403, detail="Privacy Violation.")

    db.add(ChatMessage(sender=s_mail, receiver=r_mail, content=content))
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