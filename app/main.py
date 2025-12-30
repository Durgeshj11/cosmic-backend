import os
import json
import random
import io
from datetime import date, datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from dotenv import load_dotenv

import google.generativeai as genai
from PIL import Image
import cloudinary
import cloudinary.uploader

# Load environment variables
load_dotenv()

# ==========================================
# 1. API CONFIGURATION
# ==========================================
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCR8IzhNB1y1b2iqUKwsBoeITH_M3s6ZGE")
genai.configure(api_key=GEMINI_KEY)

cloudinary.config( 
    cloud_name = os.environ.get("CLOUDINARY_NAME", "dio2xerg4"), 
    api_key = os.environ.get("CLOUDINARY_API_KEY", "324819165234627"), 
    api_secret = os.environ.get("CLOUDINARY_API_SECRET", "JnB_ptVwiNdUBIS4yRwmdNsZwv8") 
)

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
elif not DATABASE_URL:
    DATABASE_URL = "postgresql://cosmic_admin:secure_password_123@localhost:5432/cosmic_db"

# ==========================================
# 2. DATABASE SETUP
# ==========================================
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    mobile = Column(String, unique=True, index=True, nullable=False)
    birthday = Column(Date, nullable=False)
    birth_time = Column(String, nullable=True) 
    birth_place = Column(String, nullable=True)
    palm_reading = Column(String, nullable=True)
    palm_score = Column(Integer, nullable=True)
    photos_json = Column(String, nullable=False)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_email = Column(String, nullable=False)
    receiver_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 3. COSMIC LOGIC
# ==========================================
def get_zodiac_sign(d: date):
    day, month = d.day, d.month
    if (month == 3 and day >= 21) or (month == 4 and day <= 19): return "Aries"
    if (month == 4 and day >= 20) or (month == 5 and day <= 20): return "Taurus"
    if (month == 5 and day >= 21) or (month == 6 and day <= 20): return "Gemini"
    if (month == 6 and day >= 21) or (month == 7 and day <= 22): return "Cancer"
    if (month == 7 and day >= 23) or (month == 8 and day <= 22): return "Leo"
    if (month == 8 and day >= 23) or (month == 9 and day <= 22): return "Virgo"
    if (month == 9 and day >= 23) or (month == 10 and day <= 22): return "Libra"
    if (month == 10 and day >= 23) or (month == 11 and day <= 21): return "Scorpio"
    if (month == 11 and day >= 22) or (month == 12 and day <= 21): return "Sagittarius"
    if (month == 12 and day >= 22) or (month == 1 and day <= 19): return "Capricorn"
    if (month == 1 and day >= 20) or (month == 2 and day <= 18): return "Aquarius"
    return "Pisces"

def get_life_path(d: date):
    total = sum(int(c) for c in f"{d.year}{d.month}{d.day}")
    while total > 9 and total not in [11, 22, 33]:
        total = sum(int(c) for c in str(total))
    return total

def calculate_detailed_compatibility(u1: User, u2: User):
    lp1, lp2 = get_life_path(u1.birthday), get_life_path(u2.birthday)
    finance = 85 if lp1 == lp2 else random.randint(60, 95)
    romance = 90 if get_zodiac_sign(u1.birthday) == get_zodiac_sign(u2.birthday) else random.randint(55, 98)
    foundation = 80 if abs(lp1 - lp2) <= 2 else random.randint(50, 85)
    destiny = (u1.palm_score + u2.palm_score) // 2 if (u1.palm_score and u2.palm_score) else 75
    return {
        "Foundation": foundation, "Finance": finance, "Romance": romance, "Destiny": destiny,
        "Total": (foundation + finance + romance + destiny) // 4
    }

# ==========================================
# 4. FASTAPI APP & ENDPOINTS
# ==========================================
app = FastAPI()

# MASTER CORS FIX
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/signup-full")
async def signup_full(
    name: str = Form(...), email: str = Form(...), mobile: str = Form(...),
    birthday: str = Form(...), 
    birth_time: Optional[str] = Form(None), 
    birth_place: Optional[str] = Form(None),
    palm_reading: str = Form(...), photos: List[UploadFile] = File(...),
    palm_image: UploadFile = File(None), db: Session = Depends(get_db)
):
    # Standardize lookup email to lowercase
    existing_user = db.query(User).filter((User.email == email.lower()) | (User.mobile == mobile)).first()
    if existing_user: return {"message": "User exists", "user_id": existing_user.id}

    try:
        bday_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
    except:
        bday_obj = date(2000, 1, 1)

    final_reading, final_score = "Stars are aligning for you.", 75
    if palm_image:
        try:
            image_bytes = await palm_image.read()
            pil_image = Image.open(io.BytesIO(image_bytes))
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = "Act as an expert Palmist. Return ONLY: 'Score: [number 50-100]' and 'Reading: [1 mystical sentence about destiny]'"
            response = model.generate_content([prompt, pil_image])
            for line in response.text.split('\n'):
                if "Score:" in line: final_score = int(''.join(filter(str.isdigit, line)))
                if "Reading:" in line: final_reading = line.split("Reading:")[1].strip()
        except: pass

    photo_urls = []
    for p in photos:
        try:
            res = cloudinary.uploader.upload(await p.read(), folder="cosmic_profiles")
            photo_urls.append(res["secure_url"])
        except: photo_urls.append("https://via.placeholder.com/300")

    new_user = User(
        name=name, email=email.lower(), mobile=mobile, birthday=bday_obj,
        birth_time=birth_time, birth_place=birth_place,
        palm_reading=final_reading, palm_score=final_score,
        photos_json=json.dumps(photo_urls)
    )
    db.add(new_user)
    db.commit()
    return {"message": "Destiny Initialized", "user_id": new_user.id}

# DOUBLE ROUTE FIX: Accepts /feed and /feed/
@app.get("/feed")
@app.get("/feed/")
def get_feed(current_email: str, db: Session = Depends(get_db)):
    me = db.query(User).filter(User.email == current_email.lower()).first()
    if not me: raise HTTPException(status_code=404, detail="Profile not found")
    
    others = db.query(User).filter(User.email != current_email.lower()).all()
    results = []
    for other in others:
        stats = calculate_detailed_compatibility(me, other)
        results.append({
            "id": other.id, "name": other.name, "sign": get_zodiac_sign(other.birthday),
            "lp": get_life_path(other.birthday), "compatibility": f"{stats['Total']}%",
            "breakdown": stats, "bio": other.palm_reading, "photos": json.loads(other.photos_json)
        })
    return sorted(results, key=lambda x: int(x['compatibility'].replace('%','')), reverse=True)

class ChatMsg(BaseModel):
    sender_email: str
    receiver_id: int
    content: str

# DOUBLE ROUTE FIX: Accepts /chat/send and /chat/send/
@app.post("/chat/send")
@app.post("/chat/send/")
def send_chat(msg: ChatMsg, db: Session = Depends(get_db)):
    new_m = Message(sender_email=msg.sender_email.lower(), receiver_id=msg.receiver_id, content=msg.content)
    db.add(new_m)
    db.commit()
    return {"status": "sent"}

# DOUBLE ROUTE FIX: Accepts /chat/history and /chat/history/
@app.get("/chat/history")
@app.get("/chat/history/")
def get_history(my_email: str, other_id: int, db: Session = Depends(get_db)):
    me = db.query(User).filter(User.email == my_email.lower()).first()
    if not me: return []
    
    other_user = db.query(User).filter(User.id == other_id).first()
    if not other_user: return []

    msgs = db.query(Message).filter(
        ((Message.sender_email == my_email.lower()) & (Message.receiver_id == other_id)) |
        ((Message.sender_email == other_user.email) & (Message.receiver_id == me.id))
    ).order_by(Message.timestamp).all()
    return [{"content": m.content, "is_me": m.sender_email == my_email.lower()} for m in msgs]

@app.get("/dashboard")
@app.get("/dashboard/")
def dashboard(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{
        "name": u.name, "email": u.email, "palm": u.palm_reading, 
        "photos": json.loads(u.photos_json)
    } for u in users]

# Force Update 5.0 - Double Routing & Case Insensitive Logic