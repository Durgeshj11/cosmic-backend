from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, SQLModel
from app.db.session import get_session, engine
from app.db.models import User
from typing import List
from datetime import date
from contextlib import asynccontextmanager

# --- DATABASE SETUP ---
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="Cosmic Align API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # Allow ALL origins
    allow_credentials=False, # <--- CHANGE THIS TO FALSE (Fixes the bug)
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 🧠 THE LOGIC BRAIN ---

def calculate_sun_sign(dob: date) -> str:
    """Returns the Zodiac sign based on Day and Month."""
    day = dob.day
    month = dob.month
    
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

def calculate_life_path(dob: date) -> int:
    """Sums all digits of the birth date until a single digit remains."""
    # Convert 2000-01-01 -> "20000101"
    digits = f"{dob.year}{dob.month:02d}{dob.day:02d}"
    
    total = sum(int(d) for d in digits)
    
    # Keep summing until single digit (e.g., 25 -> 7)
    while total > 9:
        total = sum(int(d) for d in str(total))
        
    return total

def get_numerology_compatibility(lp1: int, lp2: int) -> int:
    """Returns a score (0-100) based on Life Path compatibility."""
    # Simple compatibility chart (Example logic)
    # Natural Matches are high, Challenges are lower
    natural_matches = {
        1: [1, 5, 7], 2: [2, 4, 8], 3: [3, 6, 9],
        4: [2, 4, 8], 5: [1, 5, 7], 6: [3, 6, 9],
        7: [1, 5, 7], 8: [2, 4, 8], 9: [3, 6, 9]
    }
    
    if lp2 in natural_matches.get(lp1, []):
        return 95  # Perfect Numerology Match
    elif (lp1 + lp2) % 3 == 0:
        return 80  # Good Vibration
    else:
        return 60  # Neutral

# --- ENDPOINTS ---

@app.get("/")
def read_root():
    return {"message": "Cosmic Brain is Active with Numerology!"}

@app.get("/users", response_model=List[User])
def read_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()

@app.post("/users", response_model=User)
def create_user(user: User, session: Session = Depends(get_session)):
    # 1. AUTO-CALCULATE DATA (The Upgrade)
    if user.dob:
        user.sun_sign = calculate_sun_sign(user.dob)
        user.life_path_number = calculate_life_path(user.dob)
    
    # 2. Fill generic email if missing
    if not user.email:
        clean_name = user.name.replace(" ", "").lower()
        user.email = f"{clean_name}@cosmic.com"
        
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
            # Combined Score: 50% Numerology + 50% Random/Zodiac Logic
            num_score = get_numerology_compatibility(main_user.life_path_number, other.life_path_number)
            
            # Simple Zodiac check (Element match)
            zodiac_score = 70 # Default base
            if main_user.sun_sign == other.sun_sign: zodiac_score = 90
            
            final_score = (num_score + zodiac_score) // 2
            
            results.append({
                "name": other.name, 
                "sign": other.sun_sign,
                "life_path": other.life_path_number,
                "score": final_score
            })
            
    return sorted(results, key=lambda x: x["score"], reverse=True)

@app.delete("/users/{user_id}")
def delete_user(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(user)
    session.commit()
    return {"ok": True}