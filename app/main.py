import google.generativeai as genai
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, SQLModel, Field, create_engine
from typing import Optional, List
from datetime import date
import os, random, re, io
from PIL import Image

# --- 1. APP & AI INITIALIZATION ---
app = FastAPI(title="Cosmic Match Pro AI API")

# SECURITY: Set GEMINI_API_KEY in Render Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --- 3. DATABASE MODELS ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    mobile: str
    birthday: date 
    birth_time: str
    birth_place: str
    life_path: Optional[int] = None
    is_verified: bool = Field(default=False)
    consent_given: bool = Field(default=False)

# --- 4. UTILITY FUNCTIONS ---
def get_db():
    with Session(engine) as session:
        yield session

def calculate_life_path(dob: date) -> int:
    digits = f"{dob.year}{dob.month:02d}{dob.day:02d}"
    lp = sum(int(d) for d in digits)
    while lp > 9 and lp not in [11, 22, 33]:
        lp = sum(int(d) for d in str(lp))
    return lp

# --- 5. API ENDPOINTS ---

@app.post("/request-otp")
async def request_otp(contact: str):
    otp = str(random.randint(1000, 9999))
    print(f"--- [SECURITY] OTP for {contact}: {otp} ---")
    return {"status": "OTP_SENT"}

@app.get("/calculate-match")
def calculate_match(dob: str):
    """Calculates 4 pillars: Foundation, Communication, Loyalty, and Finance."""
    try:
        birth_date = date.fromisoformat(dob)
        lp = calculate_life_path(birth_date)
        
        # Deterministic scores based on Life Path
        foundation = 85 + (lp % 10)
        comm = 80 + (lp * 2 % 15)
        loyalty = 90 + (lp % 9)
        finance = 75 + (lp * 3 % 20) # 4th Pillar: Financial Compatibility
        
        return {
            "score": int((foundation + comm + loyalty + finance) / 4),
            "pillars": {
                "Foundation": f"{foundation}%",
                "Communication": f"{comm}%",
                "Loyalty Index": f"{loyalty}%",
                "Financial Compatibility": f"{finance}%"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid date format")

@app.post("/analyze-palm")
async def analyze_palm(file: UploadFile = File(...)):
    """AI Image Analysis for Symbolic Loyalty/Financial Reading."""
    try:
        img_data = await file.read()
        img = Image.open(io.BytesIO(img_data))
        prompt = "Analyze the lines of this palm for a symbolic marriage destiny reading. Focus on loyalty and financial stability."
        response = ai_model.generate_content([prompt, img])
        return {"ai_report": response.text, "status": "Success"}
    except Exception as e:
        return {"error": str(e), "status": "Failed"}

@app.post("/signup", response_model=User)
def signup(user: User, db: Session = Depends(get_db)):
    user.life_path = calculate_life_path(user.birthday)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user