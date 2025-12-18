from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from app.db.session import get_session
from app.db.models import User
from typing import List
from datetime import date
import asyncio

app = FastAPI(title="Cosmic Align API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ZODIAC ENGINE ---
def get_element(sign: str):
    elements = {
        "Fire": ["Aries", "Leo", "Sagittarius"],
        "Air": ["Gemini", "Libra", "Aquarius"],
        "Water": ["Cancer", "Scorpio", "Pisces"],
        "Earth": ["Taurus", "Virgo", "Capricorn"]
    }
    for element, signs in elements.items():
        if sign in signs: return element
    return "Unknown"

def calculate_love_score(sign1: str, sign2: str):
    elem1 = get_element(sign1)
    elem2 = get_element(sign2)
    if elem1 == "Unknown" or elem2 == "Unknown": return 50
    if elem1 == elem2: return 95
    pairs = [("Fire", "Air"), ("Water", "Earth")]
    if (elem1, elem2) in pairs or (elem2, elem1) in pairs: return 85
    return 60

# --- NUMEROLOGY ENGINE ---
def get_life_path_meaning(number: int):
    meanings = {
        1: "The Leader: Independent and ambitious.",
        2: "The Peacemaker: Diplomatic and sensitive.",
        3: "The Creative: Social and artistic.",
        4: "The Builder: Practical and grounded.",
        5: "The Adventurer: Freedom-loving and versatile.",
        6: "The Nurturer: Responsible and caring.",
        7: "The Seeker: Analytical and spiritual.",
        8: "The Powerhouse: Ambitious and efficient.",
        9: "The Humanitarian: Compassionate and generous."
    }
    return meanings.get(number, "The Mystery: A path yet to be revealed.")

# --- ENDPOINTS ---
@app.get("/")
def read_root():
    return {"message": "The Cosmic Server is Running!"}

@app.get("/users", response_model=List[User])
def read_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return users

@app.post("/users", response_model=User)
def create_user(user: User, session: Session = Depends(get_session)):
    if not user.email:
        clean_name = user.name.replace(" ", "").lower()
        user.email = f"{clean_name}@cosmic.com"
    if not user.dob:
        user.dob = date(2000, 1, 1)
    if not user.life_path_number:
        user.life_path_number = 7
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@app.get("/matches/{user_id}")
def get_matches(user_id: int, session: Session = Depends(get_session)):
    main_user = session.get(User, user_id)
    if not main_user: return {"error": "User not found"}
    results = []
    all_users = session.exec(select(User)).all()
    for other in all_users:
        if other.id != user_id:
            score = calculate_love_score(main_user.sun_sign, other.sun_sign)
            results.append({"name": other.name, "sign": other.sun_sign, "score": score})
    return sorted(results, key=lambda x: x["score"], reverse=True)

@app.get("/palm/{user_id}")
async def read_palm(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user: return {"error": "Star not found"}
    await asyncio.sleep(2) 
    meaning = get_life_path_meaning(user.life_path_number)
    return {
        "name": user.name,
        "life_path": user.life_path_number,
        "reading": meaning
    }

# --- NEW: DELETE USER ---
@app.delete("/users/{user_id}")
def delete_user(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(user)
    session.commit()
    return {"ok": True}