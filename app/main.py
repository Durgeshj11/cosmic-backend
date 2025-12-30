import os
import json
import io
from datetime import date, datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, ForeignKey, Text, inspect, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

import google.generativeai as genai
from PIL import Image
import cloudinary
import cloudinary.uploader

# Load configuration
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
# 2. DATABASE MODELS
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
    birth_time = Column(String, nullable=False)
    birth_place = Column(String, nullable=False)
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
    try: yield db
    finally: db.close()

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

def calculate_detailed_compatibility(u1: User, u2: User):
    base_score = 70
    return {
        "Foundation": base_score - 5,
        "Finance": base_score + 2,
        "Romance": base_score + 25 if u1.name != u2.name else 50,
        "Destiny": base_score + 5
    }

# ==========================================
# 4. API ENDPOINTS
# ==========================================
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/", response_class=HTMLResponse)
def home():
    return "<h1>Cosmic API Live</h1><a href='/dashboard'>View Dashboard</a>"

@app.post("/signup-full")
async def signup(
    name: str = Form(...), email: str = Form(...), mobile: str = Form(...),
    birthday: str = Form(...), birth_time: str = Form(...), birth_place: str = Form(...),
    palm_reading: str = Form(...), photos: List[UploadFile] = File(...),
    palm_image: UploadFile = File(None), db: Session = Depends(get_db)
):
    existing = db.query(User).filter(or_(User.email == email, User.mobile == mobile)).first()
    if existing: return {"message": "User exists", "user_id": existing.id}

    f_reading, f_score = "Stars are aligning...", 75
    if palm_image:
        try:
            img = Image.open(io.BytesIO(await palm_image.read()))
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(["Palmist analysis. Return 'Score: [num]' and 'Reading: [sentence]'", img])
            for line in res.text.split('\n'):
                if "Score:" in line: f_score = int(''.join(filter(str.isdigit, line)))
                if "Reading:" in line: f_reading = line.split("Reading:")[1].strip()
        except: pass

    urls = []
    for p in photos:
        res = cloudinary.uploader.upload(await p.read(), folder="cosmic_users")
        urls.append(res["secure_url"])
    
    new_u = User(name=name, email=email, mobile=mobile, birthday=datetime.strptime(birthday, "%Y-%m-%d").date(),
                 birth_time=birth_time, birth_place=birth_place, palm_reading=f_reading, 
                 palm_score=f_score, photos_json=json.dumps(urls))
    db.add(new_u)
    db.commit()
    return {"message": "Created", "user_id": new_u.id}

@app.get("/feed")
def get_feed(current_email: str, db: Session = Depends(get_db)):
    me = db.query(User).filter(User.email == current_email).first()
    if not me: raise HTTPException(status_code=404)
    
    others = db.query(User).filter(User.email != current_email).all()
    results = []
    for o in others:
        breakdown = calculate_detailed_compatibility(me, o)
        avg = sum(breakdown.values()) // 4
        results.append({
            "id": o.id, "name": o.name, "compatibility": f"{avg}%",
            "age": 25, "sign": get_zodiac_sign(o.birthday),
            "relationship_label": "Cosmic Connection" if avg > 70 else "Karmic Lesson",
            "breakdown": breakdown, "photos": json.loads(o.photos_json)
        })
    return sorted(results, key=lambda x: x['compatibility'], reverse=True)

# THE FIX: PRODUCTION VISUAL DASHBOARD
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_db)):
    users = db.query(User).all()
    cards = ""
    for u in users:
        img = json.loads(u.photos_json)[0] if u.photos_json else ""
        zodiac = get_zodiac_sign(u.birthday)
        cards += f"""
        <div style="background: #1F2937; color: white; margin: 20px; border-radius: 25px; width: 340px; font-family: sans-serif; overflow: hidden; box-shadow: 0 15px 30px rgba(0,0,0,0.5);">
            <div style="height: 400px; background: url('{img}') center/cover; position: relative;">
                <div style="position: absolute; bottom: 20px; left: 20px;">
                    <h2 style="margin: 0; font-size: 28px; text-shadow: 2px 2px 4px rgba(0,0,0,0.8);">{u.name}, 25</h2>
                    <div style="background: #FFD700; color: black; display: inline-block; padding: 4px 12px; border-radius: 8px; margin-top: 8px; font-weight: bold; font-size: 14px;">
                        {zodiac} | LP: 4
                    </div>
                </div>
            </div>
            <div style="padding: 20px; background: #111827;">
                <div style="border: 2px solid #D946EF; padding: 10px; border-radius: 15px; color: #D946EF; font-weight: bold; text-align: center; margin-bottom: 10px;">
                    ✨ Cosmic Connection
                </div>
                <div style="text-align: center; color: #9CA3AF; margin-bottom: 15px;">Match: {u.palm_score}%</div>
                
                <div style="font-size: 13px;">
                    <div style="margin-bottom: 8px;">Foundation <span style="float:right">65</span><div style="width:100%; height:8px; background:#374151; border-radius:5px;"><div style="width:65%; height:100%; background:#4F46E5; border-radius:5px;"></div></div></div>
                    <div style="margin-bottom: 8px;">Finance <span style="float:right">72</span><div style="width:100%; height:8px; background:#374151; border-radius:5px;"><div style="width:72%; height:100%; background:#10B981; border-radius:5px;"></div></div></div>
                    <div style="margin-bottom: 8px;">Romance <span style="float:right">95</span><div style="width:100%; height:8px; background:#374151; border-radius:5px;"><div style="width:95%; height:100%; background:#EC4899; border-radius:5px;"></div></div></div>
                    <div style="margin-bottom: 8px;">Destiny <span style="float:right">75</span><div style="width:100%; height:8px; background:#374151; border-radius:5px;"><div style="width:75%; height:100%; background:#A855F7; border-radius:5px;"></div></div></div>
                </div>
                <button style="width:100%; background:#D946EF; border:none; color:white; padding:12px; border-radius:15px; margin-top:20px; font-weight:bold; cursor:pointer;">COSMIC CHAT</button>
            </div>
        </div>
        """
    return f"<html><body style='background:#0A0E17; display:flex; flex-wrap:wrap; justify-content:center; padding:20px;'>{cards}</body></html>"