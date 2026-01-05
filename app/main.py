import os
import io
import random
import hashlib
import json
import asyncio
import cloudinary
import cloudinary.uploader
import redis.asyncio as aioredis
import redis.exceptions 
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import google.generativeai as genai
from dotenv import load_dotenv

# Firebase Admin SDK for Push Notifications
import firebase_admin
from firebase_admin import credentials, messaging

load_dotenv()

# --- AI, Media & Notification Configuration ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
ai_model = genai.GenerativeModel('gemini-1.5-flash')

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

if not firebase_admin._apps:
    try:
        fb_creds = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON"))
        cred = credentials.Certificate(fb_creds)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Firebase Init Warning: {e}")

# --- 🧠 ADAPTIVE TRIPLE-SCIENCE ENGINE PATH FIX ---
TRUTH_DICTIONARY = {}
current_dir = os.path.dirname(os.path.abspath(__file__))
# Dynamic pathing for Render.com deployment
file_path = os.path.join(current_dir, 'sentient_3600_truths.json')

try:
    with open(file_path, 'r') as f:
        TRUTH_DICTIONARY = json.load(f)
    print("SUCCESS: 3,600 Layman Truths ready for 12 cards.")
except Exception as e:
    # Fallback to local root if pathing differs
    try:
        with open('sentient_3600_truths.json', 'r') as f:
            TRUTH_DICTIONARY = json.load(f)
        print("SUCCESS: Database Loaded from local root.")
    except:
        print(f"Billionaire Engine Error: Ensure sentient_3600_truths.json exists. {e}")

# --- Database Setup ---
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Models ---
class User(Base):
    __tablename__ = "cosmic_profiles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    birthday = Column(Date, nullable=False)
    palm_signature = Column(String)  
    photos = Column(String)          
    birth_time = Column(String)
    birth_location = Column(String)
    full_legal_name = Column(String)
    methods = Column(String)         
    fcm_token = Column(String) 

class Match(Base):
    __tablename__ = "cosmic_matches"
    id = Column(Integer, primary_key=True, index=True)
    user_a = Column(String, index=True) 
    user_b = Column(String, index=True) 
    is_mutual = Column(Boolean, default=False)
    is_unlocked = Column(Boolean, default=False) 
    user_a_accepted = Column(Boolean, default=False)
    user_b_accepted = Column(Boolean, default=False)
    request_initiated_by = Column(String) 
    user_a_typing = Column(Boolean, default=False)
    user_b_typing = Column(Boolean, default=False)

class ChatMessage(Base):
    __tablename__ = "cosmic_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String)
    receiver = Column(String)
    content = Column(String)
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# --- REDIS MANAGER (Billionaire Scale Protocol) ---
class RedisConnectionManager:
    def __init__(self, redis_url: str):
        if not redis_url:
            self.redis = None
            self.local_connections = {}
            return
        try:
            self.redis = aioredis.from_url(redis_url, decode_responses=True)
            self.local_connections = {}
        except Exception as e:
            print(f"Redis Setup Error: {e}")
            self.redis = None

    async def connect(self, email: str, websocket: WebSocket):
        await websocket.accept()
        if not self.redis: return
        self.local_connections[email] = websocket
        asyncio.create_task(self._redis_listener(email, websocket))

    async def _redis_listener(self, email: str, websocket: WebSocket):
        if not self.redis: return
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(email)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])
        except Exception: pass
        finally:
            try: await pubsub.unsubscribe(email)
            except: pass

    async def publish_update(self, email: str, data: dict):
        if self.redis:
            try: await self.redis.publish(email, json.dumps(data))
            except Exception as e: print(f"Redis Broadcast Fail: {e}")

manager = RedisConnectionManager(os.getenv("UPSTASH_REDIS_URL"))

# --- SCIENTIFIC CALCULATION ENGINES ---

def get_astrology_score(sign_a: str, sign_b: str) -> int:
    elements = {"Fire": ["Aries", "Leo", "Sagittarius"], "Earth": ["Taurus", "Virgo", "Capricorn"], "Air": ["Gemini", "Libra", "Aquarius"], "Water": ["Cancer", "Scorpio", "Pisces"]}
    def find_el(s): return next(k for k, v in elements.items() if s in v)
    el_a, el_b = find_el(sign_a), find_el(sign_b)
    if el_a == el_b: return 95 
    harmonies = [("Fire", "Air"), ("Earth", "Water")]
    if (el_a, el_b) in harmonies or (el_b, el_a) in harmonies: return 85
    return 45 

def get_numerology_harmony(name_a: str, name_b: str) -> int:
    def calc_destiny(name):
        val_map = {c: (i % 9) + 1 for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}
        total = sum(val_map.get(char.lower(), 0) for char in name if char.isalpha())
        while total > 9: total = sum(int(d) for d in str(total))
        return total
    d1, d2 = calc_destiny(name_a), calc_destiny(name_b)
    diff = abs(d1 - d2)
    return 98 if diff == 0 else 80 if diff in [2, 4, 6] else 40

def get_palm_variance(sig_a: str, sig_b: str) -> int:
    val_a = int(sig_a[:4], 16) if sig_a and sig_a != "NONE" else 0
    val_b = int(sig_b[:4], 16) if sig_b and sig_b != "NONE" else 0
    diff = abs(val_a - val_b) % 100
    return 100 - diff

# --- UTILS ---
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def get_sun_sign(day: int, month: int) -> str:
    zodiac_data = [(19, "Aquarius"), (18, "Pisces"), (20, "Aries"), (19, "Taurus"), (20, "Gemini"), (20, "Cancer"), (22, "Leo"), (22, "Virgo"), (22, "Libra"), (22, "Scorpio"), (21, "Sagittarius"), (21, "Capricorn")]
    idx = month - 1
    return zodiac_data[idx][1] if day > zodiac_data[idx][0] else zodiac_data[(idx - 1) % 12][1]

def get_life_path(dob_str):
    nums = [int(d) for d in dob_str if d.isdigit()]
    total = sum(nums)
    while total > 9: total = sum(int(d) for d in str(total))
    return total

async def send_push_notification(token: str, title: str, body: str):
    if not token or token == "NONE": return
    try:
        message = messaging.Message(notification=messaging.Notification(title=title, body=body), token=token)
        messaging.send(message)
    except Exception as e: print(f"Push Error: {e}")

# --- 🚀 ADAPTIVE TRIPLE-SCIENCE LAYMAN ENGINE ---
def fetch_adaptive_layman_truth(factor: str, score: int, user: User):
    try:
        active = json.loads(user.methods) if user.methods else {"Numerology": True, "Astrology": True, "Palmistry": True}
        factor_db = TRUTH_DICTIONARY.get(factor, {})
        entry = factor_db.get(str(score), {})
        
        lines = []
        # 1. Numerology (Name Dependent)
        if active.get("Numerology") and user.name:
            lines.append(entry.get("Numerology", "Numerology resonance active."))
        # 2. Astrology (Birth Time/Location Dependent)
        if active.get("Astrology") and user.birth_time and user.birth_location:
            lines.append(entry.get("Astrology", "Cosmic alignment verified."))
        # 3. Palmistry (Biometric Signature Dependent)
        if active.get("Palmistry") and user.palm_signature and user.palm_signature != "NONE":
            lines.append(entry.get("Palmistry", "Biometric signature confirmed."))
        
        return "\n\n".join(lines) if lines else f"Calculated via {factor} frequency."
    except:
        return f"Calculated via {factor} frequency."

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- ENDPOINTS ---

@app.websocket("/ws/{email}")
async def websocket_endpoint(websocket: WebSocket, email: str):
    await manager.connect(email.lower().strip(), websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.local_connections.pop(email.lower().strip(), None)

@app.api_route("/nuke-database", methods=["GET", "POST"])
def nuke_database(db: Session = Depends(get_db)):
    db.execute(text("DROP TABLE IF EXISTS cosmic_profiles, cosmic_matches, cosmic_messages CASCADE;"))
    db.commit()
    Base.metadata.create_all(bind=engine)
    return {"status": "success", "message": "Database synchronized."}

@app.post("/signup-full")
async def signup(name: str = Form(...), email: str = Form(...), birthday: str = Form(...), palm_signature: str = Form(...), full_legal_name: str = Form(None), birth_time: str = Form(None), birth_location: str = Form(None), methods: str = Form("{}"), fcm_token: str = Form("NONE"), photos: List[UploadFile] = File(None), db: Session = Depends(get_db)):
    clean_email = email.strip().lower()
    photo_urls = []
    if photos:
        for photo in photos:
            try: 
                res = cloudinary.uploader.upload(await photo.read())
                photo_urls.append(res['secure_url'])
            except: pass
    date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
    user = db.query(User).filter(User.email == clean_email).first() or User(email=clean_email)
    if not user.id: db.add(user)
    user.name, user.birthday, user.palm_signature, user.full_legal_name = name, date_obj, palm_signature, full_legal_name
    user.birth_time, user.birth_location, user.methods, user.photos, user.fcm_token = birth_time, birth_location, methods, ",".join(photo_urls), fcm_token
    db.commit()
    return {"message": "Success", "signature": palm_signature}

@app.get("/feed")
async def get_feed(current_email: str, db: Session = Depends(get_db)):
    clean_me = current_email.strip().lower()
    if clean_me in ["ping", "warmup"]: return {"status": "ready"}
    me = db.query(User).filter(User.email == clean_me).first()
    if not me: raise HTTPException(status_code=404)
    
    factor_labels = ["Health", "Power", "Creativity", "Social", "Emotional", "Mental", "Lifestyle", "Spiritual", "Sexual", "Family", "Economic", "Foundation"]
    results = []
    my_sign = get_sun_sign(me.birthday.day, me.birthday.month)
    my_path = get_life_path(str(me.birthday))
    
    results.append({
        "name": "YOUR DESTINY", "percentage": "100%", "is_self": True, "email": me.email, 
        "photos": me.photos.split(",") if me.photos else [], "sun_sign": my_sign, "life_path": my_path, 
        "factors": {f: {"score": f"{random.randint(90,99)}%", "why": f"Core {f} alignment."} for f in factor_labels}, 
        "reading": f"Optimized {my_sign} blueprint."
    })
    
    others = db.query(User).filter(User.email != me.email).all()
    for o in others:
        o_sign = get_sun_sign(o.birthday.day, o.birthday.month)
        astro = get_astrology_score(my_sign, o_sign)
        num = get_numerology_harmony(me.full_legal_name or me.name, o.full_legal_name or o.name)
        palm = get_palm_variance(me.palm_signature, o.palm_signature)
        
        match_score = int((astro * 0.4) + (num * 0.3) + (palm * 0.3))
        tier = "MARRIAGE MATERIAL" if match_score >= 85 else "INTENSE FLING" if match_score >= 65 else "KARMIC LESSON"
        match_rec = db.query(Match).filter(((Match.user_a == me.email) & (Match.user_b == o.email)) | ((Match.user_b == me.email) & (Match.user_a == o.email))).first()
        
        reading = f"Destiny Tier: {tier}. Resonance: {match_score}%."
        try:
            ai_res = ai_model.generate_content(f"Explain why a {my_sign} and {o_sign} have {match_score}% compatibility in one short sentence.")
            reading = ai_res.text.strip()
        except: pass

        processed_factors = {}
        for f in factor_labels:
            f_score = min(99, max(1, match_score + random.randint(-10, 10))) 
            processed_factors[f] = {
                "score": f"{f_score}%",
                "why": fetch_adaptive_layman_truth(f, f_score, me) # Dynamic Adaptation
            }

        results.append({
            "name": o.name, "email": o.email, "is_self": False, 
            "is_matched": match_rec.is_mutual if match_rec else False, 
            "has_liked": db.query(Match).filter(Match.user_a == me.email, Match.user_b == o.email).first() is not None, 
            "percentage": f"{match_score}%", "tier": tier, "photos": o.photos.split(",") if o.photos else [], 
            "sun_sign": o_sign, "life_path": get_life_path(str(o.birthday)), 
            "factors": processed_factors, 
            "reading": reading
        })
    return results

# --- PRESERVED ENDPOINTS (NO REMOVAL) ---
@app.post("/like-profile")
async def like_profile(my_email: str = Form(...), target_email: str = Form(...), db: Session = Depends(get_db)):
    my, target = my_email.lower().strip(), target_email.lower().strip()
    existing = db.query(Match).filter(Match.user_a == target, Match.user_b == my).first()
    if existing:
        existing.is_mutual = True; db.commit(); return {"status": "match"}
    if not db.query(Match).filter(Match.user_a == my, Match.user_b == target).first():
        db.add(Match(user_a=my, user_b=target, is_mutual=False, request_initiated_by=my)); db.commit()
    return {"status": "liked"}

@app.get("/chat-status")
async def chat_status(me: str, them: str, db: Session = Depends(get_db)):
    me, them = me.lower().strip(), them.lower().strip()
    match = db.query(Match).filter(((Match.user_a == me) & (Match.user_b == them)) | ((Match.user_b == me) & (Match.user_a == them))).first()
    other_typing = False
    if match: other_typing = match.user_b_typing if match.user_a == me else match.user_a_typing
    engaged = db.query(Match).filter(((Match.user_a == me) & (Match.user_a_accepted == True)) | ((Match.user_b == me) & (Match.user_b_accepted == True))).count()
    return {"accepted": match.user_a_accepted or match.user_b_accepted if match else False, "engaged_count": engaged, "is_paid": match.is_unlocked if match else False, "is_typing": other_typing}

@app.post("/set-typing")
async def set_typing(me: str = Form(...), them: str = Form(...), status: str = Form(...), db: Session = Depends(get_db)):
    me, them = me.lower().strip(), them.lower().strip()
    match = db.query(Match).filter(((Match.user_a == me) & (Match.user_b == them)) | ((Match.user_b == me) & (Match.user_a == them))).first()
    if match:
        is_typing = status.lower() == "true"
        if match.user_a == me: match.user_a_typing = is_typing
        else: match.user_b_typing = is_typing
        db.commit(); await manager.publish_update(them, {"type": "typing", "status": is_typing})
    return {"status": "ok"}

@app.post("/mark-read")
async def mark_read(me: str = Form(...), them: str = Form(...), db: Session = Depends(get_db)):
    me, them = me.lower().strip(), them.lower().strip()
    db.query(ChatMessage).filter(ChatMessage.receiver == me, ChatMessage.sender == them, ChatMessage.is_read == False).update({"is_read": True})
    db.commit(); await manager.publish_update(them, {"type": "read_receipt", "from": me})
    return {"status": "ok"}

@app.post("/accept-chat")
async def accept_chat(me: str = Form(...), them: str = Form(...), is_paid: str = Form("false"), db: Session = Depends(get_db)):
    me, them, paid = me.lower().strip(), them.lower().strip(), is_paid.lower() == "true"
    match = db.query(Match).filter(((Match.user_a == me) & (Match.user_b == them)) | ((Match.user_b == me) & (Match.user_a == them))).first()
    if not match: raise HTTPException(status_code=404)
    engaged = db.query(Match).filter(((Match.user_a == me) & (Match.user_a_accepted == True)) | ((Match.user_b == me) & (Match.user_b_accepted == True))).count()
    if engaged >= 2 and not paid and not (match.user_a_accepted or match.user_b_accepted): return {"status": "payment_required"}
    if match.user_a == me: match.user_a_accepted = True
    else: match.user_b_accepted = True
    if paid: match.is_unlocked = True
    db.commit(); return {"status": "accepted"}

@app.get("/messages")
async def get_messages(me: str, them: str, db: Session = Depends(get_db)):
    me, them = me.lower().strip(), them.lower().strip()
    msgs = db.query(ChatMessage).filter(((ChatMessage.sender == me) & (ChatMessage.receiver == them)) | ((ChatMessage.sender == them) & (ChatMessage.receiver == me))).order_by(ChatMessage.timestamp.asc()).all()
    return [{"sender": m.sender, "content": m.content, "time": m.timestamp.isoformat(), "is_read": m.is_read} for m in msgs]

@app.post("/send-message")
async def send_message(sender: str = Form(...), receiver: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    s, r = sender.lower().strip(), receiver.lower().strip()
    match = db.query(Match).filter(((Match.user_a == s) & (Match.user_b == r) & (Match.is_mutual == True)) | ((Match.user_b == s) & (Match.user_a == r) & (Match.is_mutual == True))).first()
    if not match: raise HTTPException(status_code=403)
    if not match.is_unlocked:
        try:
            ai_check = ai_model.generate_content(f"Reply ONLY 'LEAK' or 'SAFE': {content}")
            if "LEAK" in ai_check.text.strip().upper():
                db.delete(match); db.commit(); raise HTTPException(status_code=403)
        except Exception as e: print(f"AI Safety Bypass: {e}")
    db.add(ChatMessage(sender=s, receiver=r, content=content))
    db.commit()
    msg_payload = {"sender": s, "content": content, "is_read": False, "time": datetime.utcnow().isoformat()}
    await manager.publish_update(r, msg_payload)
    receiver_user = db.query(User).filter(User.email == r).first()
    if receiver_user: asyncio.create_task(send_push_notification(receiver_user.fcm_token, f"New Message from {s}", content))
    return {"status": "sent"}

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    e = email.strip().lower()
    db.query(User).filter(User.email == e).delete(); db.query(Match).filter((Match.user_a == e) | (Match.user_b == e)).delete(); db.commit()
    return {"message": "Deleted"}