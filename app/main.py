from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pget import get_env_variable # Ensure your DB_URL is handled
import os

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Updated User Model for Astrology & Palmistry
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)
    birthday = Column(Date)
    birth_time = Column(String)  # New: e.g., "14:30"
    birth_place = Column(String) # New: e.g., "Mumbai, India"
    palm_image_url = Column(String) # New: Base64 or URL link
    life_path = Column(Integer)

Base.metadata.create_all(bind=engine)

app = FastAPI()

# CRUD Logic
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/users")
def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@app.post("/users")
def create_user(user_data: dict, db: Session = Depends(get_db)):
    # Calculate Life Path locally before saving
    dob_digits = "".join(filter(str.isdigit, user_data['birthday']))
    lp = sum(int(d) for d in dob_digits)
    while lp > 9 and lp not in [11, 22, 33]:
        lp = sum(int(d) for d in str(lp))
        
    new_user = User(
        name=user_data['name'],
        email=user_data.get('email'),
        birthday=user_data['birthday'],
        birth_time=user_data.get('birth_time'),
        birth_place=user_data.get('birth_place'),
        palm_image_url=user_data.get('palm_image_url'),
        life_path=lp
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    return {"status": "success"}