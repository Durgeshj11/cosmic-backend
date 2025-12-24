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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

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

# --- 3. DATABASE MODELS (Expanded for Robust Compatibility) ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    mobile: str
    birthday: date 
    birth_time: str
    birth_place: str
    
    # Lifestyle Habit Features
    food_habit: str = Field(default="Veg") # Veg, Non-Veg, Vegan
    smoke_habit: bool = Field(default=False)
    drink_habit: str = Field(default="Never") # Never, Occasional, Regular
    
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
def calculate_match(
    dob: str, 
    time: str, 
    place: str, 
    p_dob: Optional[str] = None, 
    p_time: Optional[str] = None, 
    p_place: Optional[str] = None
):
    """Robust Traditional Soul Match Algorithm."""
    try:
        # User 1 Profile
        d1 = date.fromisoformat(dob)
        lp1 = calculate_life_path(d1)
        t1_hour = int(time.split(":")[0]) if ":" in time else 12
        loc_val1 = len(place) # Proxy for coordinate influence

        if p_dob and p_time and p_place:
            # PARTNER COMPARISON LOGIC
            d2 = date.fromisoformat(p_dob)
            lp2 = calculate_life_path(d2)
            t2_hour = int(p_time.split(":")[0]) if ":" in p_time else 12
            loc_val2 = len(p_place)

            # 1. Foundation: Life Path Harmony
            lp_diff = abs(lp1 - lp2)
            foundation = 100 - (lp_diff * 7)

            # 2. Communication: Birth Time Alignment (Traditional Hour Cycles)
            time_sync = 100 - (abs(t1_hour - t2_hour) * 2)
            comm_score = max(60, time_sync)

            # 3. Loyalty Index: Numerological Resonance
            loyalty = 85 + ((lp1 + lp2) % 15)

            # 4. Finance & Family: Location/Place Influence
            finance = 70 + ((loc_val1 + loc_val2) % 25)

            score = (foundation + comm_score + loyalty + finance) / 4
            label = "TRADITIONAL SOUL MATCH"
        else:
            # COSMIC SELF-ALIGNMENT (Single User)
            foundation = 85 + (lp1 % 10)
            comm_score = 80 + (t1_hour % 15)
            loyalty = 90 + (lp1 % 9)
            finance = 75 + (loc_val1 % 20)
            score = (foundation + comm_score + loyalty + finance) / 4
            label = "COSMIC SELF-ALIGNMENT"

        return {
            "score": int(score),
            "label": label,
            "pillars": {
                "Foundation (Soul)": f"{int(foundation)}%",
                "Communication (Mind)": f"{int(comm_score)}%",
                "Loyalty Index": f"{int(loyalty)}%",
                "Finance & Family": f"{int(finance)}%"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/analyze-palm")
async def analyze_palm(file: UploadFile = File(...)):
    try:
        img_data = await file.read()
        img = Image.open(io.BytesIO(img_data))
        prompt = "Analyze the lines of this palm for a symbolic marriage destiny reading. Focus on loyalty and financial stability. Strictly keep to astrological interpretation."
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