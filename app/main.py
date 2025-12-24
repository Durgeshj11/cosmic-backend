import google.generativeai as genai
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, SQLModel, Field, create_engine
from typing import Optional, List
from datetime import date
import os, random, io, json
from PIL import Image

# --- 1. CONFIGURATION ---
app = FastAPI(title="Cosmic Match Pro AI API")

# Automated Cloudinary Config from Render Environment Variables
cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_NAME"),
    api_key = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

# CORS Security: Allows communication with your Flutter frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI Setup: Gemini 1.5 Flash for palm analysis
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

# --- 3. MODELS (Full Robust Feature Set) ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    mobile: str
    birthday: date 
    birth_time: str
    birth_place: str
    
    # Lifestyle Habits
    food_habit: str = Field(default="Veg")
    smoke_habit: bool = Field(default=False)
    drink_habit: str = Field(default="Never")
    
    # Gallery: Stores a JSON string of Cloudinary URLs
    photos_json: str = Field(default="[]") 
    
    life_path: Optional[int] = None

# --- 4. ROBUST CALCULATION UTILITIES ---
def calculate_life_path(dob: date) -> int:
    """Calculates Numerology Life Path (1-9, 11, 22, 33)."""
    digits = f"{dob.year}{dob.month:02d}{dob.day:02d}"
    lp = sum(int(d) for d in digits)
    while lp > 9 and lp not in [11, 22, 33]:
        lp = sum(int(d) for d in str(lp))
    return lp

def get_synastry_match(u1, u2):
    """Calculates compatibility using traditional Numerology, Time, and Place."""
    lp1, lp2 = calculate_life_path(u1.birthday), calculate_life_path(u2.birthday)
    
    # Foundation: Life Path Harmony
    foundation = 100 - (abs(lp1 - lp2) * 7)
    
    # Communication: Birth Time Alignment (Traditional Hour Cycles)
    # Uses exact birth hour as a differentiator
    t1 = int(u1.birth_time.split(":")[0]) if ":" in u1.birth_time else 12
    t2 = int(u2.birth_time.split(":")[0]) if ":" in u2.birth_time else 12
    comm = max(60, 100 - (abs(t1 - t2) * 2))
    
    # Loyalty Index: Numerological Resonance
    loyalty = 85 + ((lp1 + lp2) % 15)
    
    # Finance: Location influence proxy using birth place string length
    finance = 70 + ((len(u1.birth_place) + len(u2.birth_place)) % 25)
    
    return {
        "score": int((foundation + comm + loyalty + finance) / 4),
        "pillars": {
            "Foundation": f"{int(foundation)}%",
            "Communication": f"{int(comm)}%",
            "Loyalty Index": f"{int(loyalty)}%",
            "Finance & Family": f"{int(finance)}%"
        }
    }

# --- 5. API ENDPOINTS ---

@app.post("/signup-full")
async def signup_full(user_data: str = Form(...), files: List[UploadFile] = File(...)):
    """Uploads photos to Cloudinary and creates a robust user profile."""
    data = json.loads(user_data)
    with Session(engine) as session:
        # Prevent duplicate signups
        existing = session.exec(select(User).where(User.email == data['email'])).first()
        if existing: raise HTTPException(status_code=400, detail="Email already exists")

        # Permanent Image Hosting via Cloudinary
        photo_urls = []
        for file in files:
            result = cloudinary.uploader.upload(file.file)
            photo_urls.append(result['secure_url'])

        new_user = User(
            name=data['name'],
            email=data['email'],
            mobile=data['mobile'],
            birthday=date.fromisoformat(data['birthday']),
            birth_time=data['birth_time'],
            birth_place=data['birth_place'],
            food_habit=data.get('food_habit', "Veg"),
            smoke_habit=data.get('smoke_habit', False),
            drink_habit=data.get('drink_habit', "Never"),
            photos_json=json.dumps(photo_urls),
            life_path=calculate_life_path(date.fromisoformat(data['birthday']))
        )
        session.add(new_user)
        session.commit()
        return {"status": "success", "photos": photo_urls}

@app.get("/get-match-feed")
def get_match_feed(email: str):
    """Calculates real-time matches against all users in the feed."""
    with Session(engine) as session:
        me = session.exec(select(User).where(User.email == email)).first()
        if not me: raise HTTPException(status_code=404, detail="User not found")
        
        # Fetch all other potential partners from the database
        others = session.exec(select(User).where(User.email != email)).all()
        feed = []
        for other in others:
            res = get_synastry_match(me, other)
            feed.append({
                "name": other.name,
                "habits": f"{other.food_habit} | Smoke: {'Yes' if other.smoke_habit else 'No'} | Drink: {other.drink_habit}",
                "photos": json.loads(other.photos_json),
                "match": res
            })
        return feed

@app.post("/request-otp")
async def request_otp(contact: str):
    """Simulates OTP sending; code is printed in Render Logs."""
    otp = str(random.randint(1000, 9999))
    print(f"--- [SECURITY] OTP for {contact}: {otp} ---")
    return {"status": "OTP_SENT"}

@app.post("/analyze-palm")
async def analyze_palm(file: UploadFile = File(...)):
    """AI Palm Reading using Gemini 1.5 Flash."""
    try:
        img_data = await file.read()
        img = Image.open(io.BytesIO(img_data))
        prompt = "Analyze the lines of this palm for a symbolic marriage destiny reading. Focus on loyalty and financial stability."
        response = ai_model.generate_content([prompt, img])
        return {"ai_report": response.text, "status": "Success"}
    except Exception as e:
        return {"error": str(e), "status": "Failed"}