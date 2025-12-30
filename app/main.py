import os
import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("DATABASE_URL").replace("postgres://", "postgresql://", 1)
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    mobile = Column(String, unique=False, index=True, nullable=True) # Fixed
    birthday = Column(Date, nullable=False)
    birth_time = Column(String, nullable=True) 
    birth_place = Column(String, nullable=True)
    photos_json = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/signup-full")
async def signup(
    name: str = Form(...), 
    email: str = Form(...), 
    mobile: str = Form(...), 
    birthday: str = Form(...), 
    birth_time: Optional[str] = Form(None), # Optional fix
    birth_place: Optional[str] = Form(None), # Optional fix
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    email_clean = email.strip().lower()
    if db.query(User).filter(User.email == email_clean).first():
        return {"message": "User exists"}
    
    new_user = User(
        name=name, 
        email=email_clean, 
        mobile=mobile, 
        birthday=datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date(), 
        birth_time=birth_time or "Not Provided", 
        birth_place=birth_place or "Not Provided", 
        photos_json='["https://via.placeholder.com/300"]'
    )
    db.add(new_user)
    db.commit()
    return {"message": "Success"}

@app.get("/feed")
@app.get("/feed/")
def get_feed(current_email: str, db: Session = Depends(get_db)):
    email_clean = current_email.strip().lower()
    me = db.query(User).filter(User.email == email_clean).first()
    if not me: raise HTTPException(status_code=404, detail="User Not Found")
    others = db.query(User).filter(User.email != email_clean).all()
    return [{"name": o.name, "compatibility": "95%", "photos": json.loads(o.photos_json)} for o in others]