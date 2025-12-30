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

load_dotenv()

# ==========================================
# 1. API CONFIGURATION
# ==========================================
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
    photos_json = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 2. FASTAPI APP & ENDPOINTS
# ==========================================
app = FastAPI()

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
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    # Standardize email to lowercase and remove trailing dots
    clean_email = email.strip().rstrip('.').lower()
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user: return {"message": "User exists", "user_id": existing_user.id}

    new_user = User(
        name=name, email=clean_email, mobile=mobile,
        birthday=datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date(),
        birth_time=birth_time, birth_place=birth_place,
        photos_json=json.dumps(["https://via.placeholder.com/300"]) # Simplified for deploy
    )
    db.add(new_user)
    db.commit()
    return {"message": "Success", "user_id": new_user.id}

@app.get("/feed")
@app.get("/feed/") # Double-route fix
def get_feed(current_email: str, db: Session = Depends(get_db)):
    email_clean = current_email.strip().rstrip('.').lower() # Case-insensitive fix
    me = db.query(User).filter(User.email == email_clean).first()
    if not me: raise HTTPException(status_code=404, detail=f"Profile {email_clean} not found")
    
    others = db.query(User).filter(User.email != email_clean).all()
    return [{"name": o.name, "compatibility": "92%", "photos": json.loads(o.photos_json)} for o in others]