from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # Required for Web Testing
from sqlalchemy import create_engine, Column, Integer, String, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import os
import re

# --- DATABASE CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL")
# Fix for Render/PostgreSQL connection string compatibility
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- DATABASE MODEL ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    birthday = Column(String)  # Format: YYYY-MM-DD
    birth_time = Column(String, nullable=True)
    birth_place = Column(String, nullable=True)
    life_path = Column(Integer)
    # Profile & Lifestyle
    religion = Column(String, nullable=True)
    caste = Column(String, nullable=True)
    income = Column(String, nullable=True)
    diet = Column(String, nullable=True)
    pets = Column(String, nullable=True)
    # Hidden Features & Security
    sensitive_traits = Column(String, nullable=True) # Dick/Boobs/Butt size
    body_type = Column(String, nullable=True)
    phone_password = Column(String, nullable=True)
    nsfw_enabled = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)

# Automatic Database Migration
Base.metadata.create_all(bind=engine)

# --- FASTAPI APP SETUP ---
app = FastAPI(title="Cosmic Match Pro Backend")

# Enable CORS for Web Frontend Access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SECURITY LOGIC: CONTACT FILTER ---
def has_contact_info(text: str) -> bool:
    """Detects phone numbers and email addresses to prevent sharing"""
    phone_pattern = r'\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b'
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return bool(re.search(phone_pattern, text)) or bool(re.search(email_pattern, text))

# --- LOGIC: LIFE PATH CALCULATION ---
def calculate_life_path(dob_str: str) -> int:
    """Calculates Life Path Number from DOB string (YYYY-MM-DD)"""
    digits = [int(d) for d in dob_str if d.isdigit()]
    total = sum(digits)
    while total > 9 and total not in [11, 22, 33]:
        total = sum(int(d) for d in str(total))
    return total

# --- API ENDPOINTS ---
@app.post("/signup")
def signup(user_data: dict, db: Session = Depends(SessionLocal)):
    # Validate contact info in name/email fields
    if has_contact_info(user_data.get("name", "")) or has_contact_info(user_data.get("email", "")):
        raise HTTPException(status_code=403, detail="BANNED: Contact info in profile is forbidden.")
    
    # Calculate and assign Life Path
    lp = calculate_life_path(user_data.get("birthday", "2000-01-01"))
    
    db_user = User(**user_data, life_path=lp)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"status": "success", "life_path": lp, "user_id": db_user.id}

@app.get("/users")
def get_users(db: Session = Depends(SessionLocal)):
    """Fetch all non-banned souls for swiping"""
    return db.query(User).filter(User.is_banned == False).all()

@app.post("/chat/send")
def send_message(user_id: int, message: str, db: Session = Depends(SessionLocal)):
    """Filters chat and bans users attempting to share contact info"""
    if has_contact_info(message):
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_banned = True
            db.commit()
        raise HTTPException(status_code=403, detail="BANNED: Contact information sharing detected.")
    return {"status": "message_sent"}