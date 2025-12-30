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

# Load environment variables from .env if it exists
load_dotenv()

# ==========================================
# 1. API & CLOUD CONFIGURATION
# ==========================================

# Google Gemini API Configuration
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCR8IzhNB1y1b2iqUKwsBoeITH_M3s6ZGE")
genai.configure(api_key=GEMINI_KEY)

# Cloudinary Configuration
cloudinary.config( 
    cloud_name = os.environ.get("CLOUDINARY_NAME", "dio2xerg4"), 
    api_key = os.environ.get("CLOUDINARY_API_KEY", "324819165234627"), 
    api_secret = os.environ.get("CLOUDINARY_API_SECRET", "JnB_ptVwiNdUBIS4yRwmdNsZwv8") 
)

# Database Connection Logic for Render
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
    birth_time = Column(String, nullable=False)
    birth_place = Column(String, nullable=False)
    
    # Palmistry Data
    palm_reading = Column(String, nullable=True)     # The AI generated text
    palm_score = Column(Integer, nullable=True)      # Destiny Score (50-100)
    
    photos_json = Column(String, nullable=False)     # List of Cloudinary URLs
    deletion_date = Column(DateTime, nullable=True)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Ensure tables are created on app startup
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 3. COSMIC ENGINES (LOGIC)
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

def get_astro_compatibility(sign1, sign2):
    elements = {
        "Fire": ["Aries", "Leo", "Sagittarius"],
        "Earth": ["Taurus", "Virgo", "Capricorn"],
        "Air": ["Gemini", "Libra", "Aquarius"],
        "Water": ["Cancer", "Scorpio", "Pisces"]
    }
    elem1 = next(k for k, v in elements.items() if sign1 in v)
    elem2 = next(k for k, v in elements.items() if sign2 in v)
    if elem1 == elem2: return 95 
    if (elem1 in ["Fire", "Air"] and elem2 in ["Fire", "Air"]): return 85 
    if (elem1 in ["Earth", "Water"] and elem2 in ["Earth", "Water"]): return 85 
    return 60 

def get_life_path_number(d: date):
    digits = f"{d.year}{d.month}{d.day}"
    total = sum(int(char) for char in digits)
    while total > 9 and total not in [11, 22, 33]:
        total = sum(int(char) for char in str(total))
    return total

def get_numerology_score(num1, num2):
    diff = abs(num1 - num2)
    if diff == 0: return 90 
    if diff in [2, 4]: return 80 
    if diff in [1, 3]: return 65 
    return 75 

# ==========================================
# 4. FASTAPI APP SETUP
# ==========================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    sender_email: str
    receiver_id: int
    content: str

# ==========================================
# 5. API ENDPOINTS
# ==========================================

@app.get("/")
def read_root():
    return {"message": "Cosmic Backend: Real AI Vision Active"}

@app.post("/signup-full")
async def signup_full(
    name: str = Form(...),
    email: str = Form(...),
    mobile: str = Form(...),
    birthday: str = Form(...),
    birth_time: str = Form(...),
    birth_place: str = Form(...),
    palm_reading: str = Form(...), 
    photos: List[UploadFile] = File(...),
    palm_image: UploadFile = File(None), 
    db: Session = Depends(get_db)
):
    # Check existing user
    existing_user = db.query(User).filter((User.email == email) | (User.mobile == mobile)).first()
    if existing_user:
        return {"message": "User exists", "user_id": existing_user.id}

    # Date Parsing
    try:
        clean_date_str = birthday.split(" ")[0]
        bday_obj = datetime.strptime(clean_date_str, "%Y-%m-%d").date()
    except:
        bday_obj = date(2000, 1, 1)

    # --- 1. AI PALMISTRY (VISION) ---
    final_reading = "Destiny is glowing..."
    final_score = 75 

    if palm_image:
        try:
            image_bytes = await palm_image.read()
            pil_image = Image.open(io.BytesIO(image_bytes))
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = """
            Act as an expert Palmist. Analyze this image of a palm.
            Identify Heart Line and Life Line.
            Return ONLY this format:
            Score: [number 50-100]
            Reading: [mystical sentence]
            """
            response = model.generate_content([prompt, pil_image])
            
            # Robust Parsing
            for line in response.text.split('\n'):
                if "Score:" in line:
                    final_score = int(''.join(filter(str.isdigit, line)))
                if "Reading:" in line:
                    final_reading = line.split("Reading:")[1].strip()
        except Exception as e:
            print(f"AI ERROR: {e}")

    # --- 2. CLOUDINARY UPLOADS ---
    photo_urls = []
    for p in photos:
        try:
            content = await p.read()
            res = cloudinary.uploader.upload(content, folder="cosmic_users")
            photo_urls.append(res["secure_url"])
        except:
            photo_urls.append("https://via.placeholder.com/150")
    
    new_user = User(
        name=name, email=email, mobile=mobile, birthday=bday_obj,
        birth_time=birth_time, birth_place=birth_place,
        palm_reading=final_reading, palm_score=final_score,
        photos_json=json.dumps(photo_urls)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Profile Created", "user_id": new_user.id}

@app.get("/feed")
def get_feed(current_email: str, db: Session = Depends(get_db)):
    me = db.query(User).filter(User.email == current_email).first()
    if not me: raise HTTPException(status_code=404, detail="User not found")

    others = db.query(User).filter(User.email != current_email).all()
    matches = []
    
    my_sign = get_zodiac_sign(me.birthday)
    my_lp = get_life_path_number(me.birthday)
    my_palm_score = me.palm_score or 80

    for other in others:
        other_sign = get_zodiac_sign(other.birthday)
        other_lp = get_life_path_number(other.birthday)
        other_palm_score = other.palm_score or 80
        
        score_astro = get_astro_compatibility(my_sign, other_sign) 
        score_num = get_numerology_score(my_lp, other_lp)          
        score_palm = int((my_palm_score + other_palm_score) / 2)

        factor_foundation = min(100, score_num)
        factor_romance = min(100, score_astro)
        factor_destiny = min(100, score_palm) 
        factor_finance = min(100, int((score_num + score_palm) / 2) + random.randint(-5, 5))

        final_score = (factor_foundation + factor_romance + factor_destiny + factor_finance) // 4
        
        # Labeling Logic
        if final_score >= 88: label = "💍 Marriage Material"
        elif final_score >= 80: label = "✨ Soulmate Potential"
        elif factor_romance > 85: label = "🔥 Passionate Fling"
        else: label = "💫 Cosmic Connection"

        matches.append({
            "id": other.id,
            "name": other.name,
            "compatibility": f"{final_score}%",
            "relationship_label": label,
            "bio": (other.palm_reading[:100] + "...") if other.palm_reading else "Stars aligning...",
            "photos": json.loads(other.photos_json) if other.photos_json else []
        })

    return sorted(matches, key=lambda x: int(x['compatibility'].replace('%', '')), reverse=True)

# --- CHAT ---
@app.post("/chat/send")
def send_message(msg: ChatMessage, db: Session = Depends(get_db)):
    sender = db.query(User).filter(User.email == msg.sender_email).first()
    if not sender: raise HTTPException(status_code=404, detail="Sender not found")
    new_msg = Message(sender_id=sender.id, receiver_id=msg.receiver_id, content=msg.content)
    db.add(new_msg)
    db.commit()
    return {"message": "Sent"}

@app.get("/chat/history")
def get_chat_history(my_email: str, other_id: int, db: Session = Depends(get_db)):
    me = db.query(User).filter(User.email == my_email).first()
    if not me: raise HTTPException(status_code=404, detail="User not found")
    messages = db.query(Message).filter(
        ((Message.sender_id == me.id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == me.id))
    ).order_by(Message.timestamp).all()
    return [{"is_me": m.sender_id == me.id, "content": m.content, "timestamp": m.timestamp.strftime("%H:%M")} for m in messages]