import os, json, io
from datetime import date, datetime
from typing import List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, ForeignKey, Text, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image
import cloudinary, cloudinary.uploader

load_dotenv()

# --- DATABASE SETUP ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://cosmic_admin:secure_password_123@localhost:5432/cosmic_db")
if DATABASE_URL.startswith("postgres://"):
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

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- VISUAL DASHBOARD (Matches Result.png) ---
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(db: Session = Depends(get_db)):
    users = db.query(User).all()
    user_cards = ""
    for u in users:
        photos = json.loads(u.photos_json) if u.photos_json else []
        img_url = photos[0] if photos else "https://via.placeholder.com/400"
        
        # HTML styled like your Result.png reference
        user_cards += f"""
        <div style="background: #1F2937; color: white; margin: 20px; border-radius: 25px; width: 340px; font-family: sans-serif; overflow: hidden; box-shadow: 0 15px 30px rgba(0,0,0,0.5);">
            <div style="height: 400px; background: url('{img_url}') center/cover; position: relative;">
                <div style="position: absolute; bottom: 20px; left: 20px;">
                    <h2 style="margin: 0; font-size: 28px; text-shadow: 2px 2px 4px rgba(0,0,0,0.8);">{u.name}, 25</h2>
                    <div style="background: #FFD700; color: black; display: inline-block; padding: 4px 12px; border-radius: 8px; margin-top: 8px; font-weight: bold; font-size: 14px;">
                        Capricorn | LP: 4
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
                <button style="width:100%; background:#D946EF; border:none; color:white; padding:12px; border-radius:15px; margin-top:20px; font-weight:bold;">COSMIC CHAT</button>
            </div>
        </div>
        """
    return f"<html><body style='background: #0A0E17; display: flex; flex-wrap: wrap; justify-content: center; padding: 30px;'>{user_cards}</body></html>"

# (Include your existing /signup-full, /feed, and /chat endpoints below)