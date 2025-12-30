import os
import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import google.generativeai as genai
from PIL import Image
import io
from dotenv import load_dotenv

load_dotenv()

# Setup Gemini for Astrology & Palmistry
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

DATABASE_URL = os.environ.get("DATABASE_URL").replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    birthday = Column(Date, nullable=False)
    palm_analysis = Column(String, nullable=True) # Stores AI palm reading

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

async def analyze_palm(photo_bytes):
    img = Image.open(io.BytesIO(photo_bytes))
    prompt = "Analyze this palm for personality traits. Keep it to 2 sentences."
    response = model.generate_content([prompt, img])
    return response.text

@app.post("/signup-full")
async def signup(
    name: str = Form(...), email: str = Form(...), 
    birthday: str = Form(...), photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    # Perform Palm Reading on the first photo
    photo_data = await photos[0].read()
    reading = await analyze_palm(photo_data)
    
    new_user = User(
        name=name, email=email.lower(), 
        birthday=datetime.strptime(birthday, "%Y-%m-%d").date(),
        palm_analysis=reading
    )
    db.add(new_user)
    db.commit()
    return {"message": "Success", "analysis": reading}

@app.get("/compatibility")
async def check_compatibility(my_email: str, target_email: str, db: Session = Depends(get_db)):
    user1 = db.query(User).filter(User.email == my_email.lower()).first()
    user2 = db.query(User).filter(User.email == target_email.lower()).first()
    
    # AI Comparison of Astrology (DOB) and Palm Analysis
    prompt = f"""
    Calculate compatibility between:
    Person A: Born {user1.birthday}, Palm traits: {user1.palm_analysis}
    Person B: Born {user2.birthday}, Palm traits: {user2.palm_analysis}
    Provide a percentage and a 1-sentence explanation.
    """
    response = model.generate_content(prompt)
    return {"result": response.text}