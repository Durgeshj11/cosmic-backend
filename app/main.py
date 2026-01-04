import os
import io
import random
import hashlib
import json
import asyncio
import cloudinary
import cloudinary.uploader
import redis.asyncio as aioredis
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
ai_model = genai.GenerativeModel('gemini-1.5-flash-latest')

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Initialize Firebase Admin for Billionaire Scale Notifications
if not firebase_admin._apps:
    try:
        fb_creds = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON"))
        cred = credentials.Certificate(fb_creds)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Firebase Init Warning: {e}. Notifications will be skipped.")

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

# --- REDIS SCALING MANAGER ---
class RedisConnectionManager:
    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.local_connections: dict[str, WebSocket] = {}

    async def connect(self, email: str, websocket: WebSocket):
        await websocket.accept()
        self.local_connections[email] = websocket
        asyncio.create_task(self._redis_listener(email, websocket))

    async def _redis_listener(self, email: str, websocket: WebSocket):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(email)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])
        except Exception:
            pass
        finally:
            await pubsub.unsubscribe(email)

    async def publish_update(self, email: str, data: dict):
        await self.redis.publish(email, json.dumps(data))

manager = RedisConnectionManager(os.getenv("UPSTASH_REDIS_URL"))

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app = FastAPI()

# --- UPDATED HIGH STABILITY CORS (EXPLICIT FOR FIREBASE WEB) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://cosmic-soulmate-web.web.app",
        "https://cosmic-soulmate-web.firebaseapp.com",
        "http://localhost:8080"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600, 
)

# --- UTILS ---
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
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
        )
        messaging.send(message)
    except Exception as e:
        print(f"Push Error: {e}")

# --- ENDPOINTS ---

@app.websocket("/ws/{email}")
async def websocket_endpoint(websocket: WebSocket, email: str):
    await manager.connect(email.lower().strip(), websocket)
    try:
        while True:
            await websocket.receive_text()
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
            try: res = cloudinary.uploader.upload(await photo.read()); photo_urls.append(res['secure_url'])
            except: pass
    date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
    user = db.query(User).filter(User.email == clean_email).first() or User(email=clean_email)
    if not user.id: db.add(user)
    user.name, user.birthday, user.palm_signature, user.full_legal_name = name, date_obj, palm_signature, full_legal_name
    user.birth_time, user.birth_location, user.methods, user.photos = birth_time, birth_location, methods, ",".join(photo_urls)
    user.fcm_token = fcm_token
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
    my_sign = get_sun_sign(me.birthday.day, me.birthday.month); my_path = get_life_path(str(me.birthday))
    random.seed(int(hashlib.md5((str(me.birthday) + (me.palm_signature or "S")).encode()).hexdigest(), 16))
    results.append({"name": "YOUR DESTINY", "percentage": "100%", "is_self": True, "email": me.email, "photos": me.photos.split(",") if me.photos else [], "sun_sign": my_sign, "life_path": my_path, "factors": {f: {"score": f"{random.randint(85,99)}%", "why": f"Your {f} is amplified."} for f in factor_labels}, "reading": f"Blueprint optimized for {my_sign} manifestation."})
    others = db.query(User).filter(User.email != me.email).all()
    for o in others:
        pair_emails = sorted([me.email, o.email]); pair_palms = sorted([me.palm_signature or "P1", o.palm_signature or "P2"])
        pair_seed = hashlib.md5(("".join(pair_emails) + "".join(pair_palms)).encode()).hexdigest()
        random.seed(int(pair_seed, 16)); match_score = random.randint(50, 98)
        tier = "MARRIAGE MATERIAL" if match_score >= 90 else "INTENSE FLING" if match_score >= 75 else "JUST FRIENDS"
        match_rec = db.query(Match).filter(((Match.user_a == me.email) & (Match.user_b == o.email)) | ((Match.user_b == me.email) & (Match.user_a == o.email))).first()
        results.append({"name": o.name, "email": o.email, "is_self": False, "is_matched": match_rec.is_mutual if match_rec else False, "has_liked": db.query(Match).filter(Match.user_a == me.email, Match.user_b == o.email).first() is not None, "percentage": f"{match_score}%", "tier": tier, "photos": o.photos.split(",") if o.photos else [], "sun_sign": get_sun_sign(o.birthday.day, o.birthday.month), "life_path": get_life_path(str(o.birthday)), "factors": {f: {"score": f"{random.randint(50,98)}%", "why": f"Locked biometric signatures."} for f in factor_labels}, "reading": f"Destiny Tier: {tier}."})
    return results

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
        if "LEAK" in ai_model.generate_content(f"Reply ONLY 'LEAK' or 'SAFE': {content}").text.strip().upper():
            db.delete(match); db.commit(); raise HTTPException(status_code=403)
            
    db.add(ChatMessage(sender=s, receiver=r, content=content))
    db.commit()
    
    # CRITICAL FIX: BROADCAST TO THE RECEIVER (r) CHANNEL
    msg_payload = {"sender": s, "content": content, "is_read": False, "time": datetime.utcnow().isoformat()}
    await manager.publish_update(r, msg_payload)
    
    receiver_user = db.query(User).filter(User.email == r).first()
    if receiver_user:
        asyncio.create_task(send_push_notification(receiver_user.fcm_token, f"New Message from {s}", content))

    return {"status": "sent"}

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    e = email.strip().lower()
    db.query(User).filter(User.email == e).delete(); db.query(Match).filter((Match.user_a == e) | (Match.user_b == e)).delete(); db.commit()
    return {"message": "Deleted"}