from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # This allows localhost and Render to connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from sqlmodel import Session, select, SQLModel, Field, create_engine
from typing import Optional, List
from datetime import date
import os
import random
import re

# --- DATABASE SETUP ---
# PostgreSQL for Render Singapore Deployment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

app = FastAPI(title="Cosmic Match Pro API")

# Web Access: CORS Middleware for Flutter Web/Mobile compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE MODELS ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    mobile: str
    birthday: date  # YYYY-MM-DD
    birth_time: str
    birth_place: str
    # Logic Fields
    life_path: Optional[int] = None
    sun_sign: Optional[str] = None
    palm_line: str = "Heart" # Heart, Head, or Life
    otp_code: str = "0000"
    is_verified: bool = Field(default=False)
    is_banned: bool = Field(default=False)
    # Security/Consent fields
    phone_password: Optional[str] = None
    consent_given: bool = Field(default=False)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --- UTILITY: NUMEROLOGY & ASTROLOGY ---
def calculate_life_path(dob: date) -> int:
    digits = f"{dob.year}{dob.month:02d}{dob.day:02d}"
    lp = sum(int(d) for d in digits)
    while lp > 9 and lp not in [11, 22, 33]:
        lp = sum(int(d) for d in str(lp))
    return lp

def get_zodiac_sign(dob: date) -> str:
    m, d = dob.month, dob.day
    if (m == 3 and d >= 21) or (m == 4 and d <= 19): return "Aries"
    if (m == 4 and d >= 20) or (m == 5 and d <= 20): return "Taurus"
    if (m == 5 and d >= 21) or (m == 6 and d <= 20): return "Gemini"
    if (m == 6 and d >= 21) or (m == 7 and d <= 22): return "Cancer"
    if (m == 7 and d >= 23) or (m == 8 and d <= 22): return "Leo"
    if (m == 8 and d >= 23) or (m == 9 and d <= 22): return "Virgo"
    if (m == 9 and d >= 23) or (m == 10 and d <= 22): return "Libra"
    if (m == 10 and d >= 23) or (m == 11 and d <= 21): return "Scorpio"
    if (m == 11 and d >= 22) or (m == 12 and d <= 21): return "Sagittarius"
    if (m == 12 and d >= 22) or (m == 1 and d <= 19): return "Capricorn"
    if (m == 1 and d >= 20) or (m == 2 and d <= 18): return "Aquarius"
    return "Pisces"

# --- SAFETY FILTER: AUTO-BAN LOGIC ---
def safety_filter(text: str) -> bool:
    # Pattern for emails or 10-digit mobile numbers
    if re.search(r'[\w\.-]+@[\w\.-]+', text) or re.search(r'\d{10}', text):
        return True # Trigger ban
    return False

# --- API ENDPOINTS ---

# 1. Stage 1: Request OTP
@app.post("/request-otp")
def request_otp(contact: str):
    otp = str(random.randint(1000, 9999))
    # Check Render Dashboard Logs to see this code for simulation
    print(f"--- [SECURITY] OTP for {contact}: {otp} ---")
    return {"status": "OTP_SENT", "message": "Verification code generated in logs."}

# 2. Stage 2: Final Signup & Profile Initialization
@app.post("/signup", response_model=User)
def signup(user: User, db: Session = Depends(lambda: Session(engine))):
    # Auto-Ban Check (Safety Filter)
    if safety_filter(user.name) or safety_filter(user.birth_place):
        user.is_banned = True
        
    # Automated Calculations
    user.life_path = calculate_life_path(user.birthday)
    user.sun_sign = get_zodiac_sign(user.birthday)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# 3. Marriage Compatibility Logic (Soulmate Groups)
@app.get("/compatibility")
def check_compatibility(lp1: int, lp2: int):
    # Soulmate Groups: Group A(1,5,7), Group B(2,4,8), Group C(3,6,9)
    groups = [{1, 5, 7}, {2, 4, 8}, {3, 6, 9}]
    
    for group in groups:
        if lp1 in group and lp2 in group:
            return {
                "status": "💍 SOULMATE MATCH",
                "score": 95,
                "label": "Green Flag ✅",
                "reason": "Perfect alignment within the same Soulmate Cluster."
            }
    
    # Stability Indexing: LP 5 is a Red Flag for stability
    if lp1 == 5 or lp2 == 5:
        return {
            "status": "✨ KARMIC GROWTH",
            "score": 45,
            "label": "Red Flag 🚩",
            "reason": "High friction; lessons in stability required."
        }

    return {
        "status": "✨ STABLE MATCH",
        "score": 75,
        "label": "Orange Flag ⚠️",
        "reason": "Secondary compatibility cluster."
    }

# 4. Mutual-Consent Reveal Logic
@app.post("/provide-consent/{user_id}")
def provide_consent(user_id: int, db: Session = Depends(lambda: Session(engine))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.consent_given = True
    db.commit()
    return {"status": "CONSENT_RECORDED"}

@app.get("/users", response_model=List[User])
def get_matches(db: Session = Depends(lambda: Session(engine))):
    # Filter out banned users from the swipe deck
    return db.exec(select(User).where(User.is_banned == False)).all()