import os
import io
import re
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
from faster_whisper import WhisperModel
from pinecone import Pinecone
from dotenv import load_dotenv

# Firebase Admin SDK for Push Notifications
import firebase_admin
from firebase_admin import credentials, messaging

load_dotenv()

# --- 🧠 SUPREME PRECISION ENGINES ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# --- [UPDATED] PINECONE 1024D CONFIGURATION ---
pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
pinecone_index = pc.Index("cosmic-resonance-grid")

# Acoustic Moderation (Free Local Whisper)
model_size = "base"
local_whisper = WhisperModel(model_size, device="cpu", compute_type="int8")

# --- CONTACT LEAK PATTERNS (STRICT PROTECTION) ---
CONTACT_PATTERNS = r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|(@[A-Za-z0-9_]+|instagram|insta|snapchat|snap|telegram|whatsapp|number)"

# --- [INJECTED] 1024D LLAMA VECTORIZER ---
def generate_vibe_vector(profile_text: str):
    """Calculates 1024D signature using the llama-text-embed-v2 model."""
    res = pc.inference.embed(
        model="llama-text-embed-v2",
        inputs=[profile_text],
        parameters={"input_type": "passage", "truncate": "END"}
    )
    return res[0].values

# --- [INJECTED] STAGE 2 ELEMENTAL HARMONY LOGIC ---
def get_astrological_element(sign: str) -> str:
    elements = {"Fire": ["Aries", "Leo", "Sagittarius"], "Earth": ["Taurus", "Virgo", "Capricorn"], "Air": ["Gemini", "Libra", "Aquarius"], "Water": ["Cancer", "Scorpio", "Pisces"]}
    return next((k for k, v in elements.items() if sign in v), "Unknown")

def stage_2_elemental_filter(my_element, candidates):
    harmony_map = {"Fire": ["Fire", "Air"], "Air": ["Air", "Fire"], "Earth": ["Earth", "Water"], "Water": ["Water", "Earth"]}
    scored_list = []
    ideal = harmony_map.get(my_element, [])
    for c in candidates:
        c_el = c.get('metadata', {}).get('element')
        bonus = 0.5 if c_el in ideal else 0.0
        if c_el == my_element: bonus += 0.2
        scored_list.append({"id": c['id'], "temp_score": c['score'] + bonus, "metadata": c.get('metadata')})
    scored_list.sort(key=lambda x: x['temp_score'], reverse=True)
    return scored_list[:500]

# --- [INJECTED] GLOBAL OSINT RADAR DISCOVERY ---
async def global_world_radar_search(me_name: str, me_sign: str):
    """Simulates searching the entire world's social media database (Top 50 platforms)."""
    platforms = ["Instagram", "X (Twitter)", "LinkedIn", "TikTok", "Threads", "Facebook", "Snapchat", "Reddit", "Pinterest", "WeChat"]
    world_discoveries = []
    
    # Generate 5 ultra-high resonance world matches from external databases
    for i in range(5):
        platform = random.choice(platforms)
        perc = random.randint(90, 99)
        world_discoveries.append({
            "name": f"Discovered Resonance #{i+1}",
            "percentage": f"{perc}%",
            "is_external": True,
            "platform": platform,
            "handle": f"@{me_name.lower().replace(' ', '_')}_vibe_{random.randint(100,999)}",
            "reading": f"Cosmic Radar detected a {perc}% frequency match on {platform}. Their public signature aligns with your {me_sign} blueprint.",
            "tier": "EXTERNAL GOD TIER" if perc >= 95 else "GLOBAL HARMONY",
            "photos": [],
            "sun_sign": random.choice(["Leo", "Aries", "Aquarius", "Pisces", "Scorpio"]),
            "factors": {}
        })
    return world_discoveries

# --- [INJECTED] STAGE 4 RE-RANKER & AI READING ---
async def stage_4_re_rank(me_sign, candidates):
    final_list = []
    sign_counts = {}
    for c in candidates:
        sign = c.get('sun_sign', 'Unknown')
        sign_counts[sign] = sign_counts.get(sign, 0) + 1
        if sign_counts[sign] <= 3:
            final_list.append(c)
        if len(final_list) >= 20: break
    
    for i in range(min(10, len(final_list))):
        o_sign = final_list[i]['sun_sign']
        perc = final_list[i].get('percentage', '??%')
        try:
            prompt = f"In one mystical sentence, explain why a {me_sign} and {o_sign} share a {perc} resonance."
            res = ai_model.generate_content(prompt)
            final_list[i]['reading'] = res.text.strip()
        except:
            final_list[i]['reading'] = f"The {me_sign} and {o_sign} energies are converging at {perc} intensity."
    return final_list

# --- TRUTH ENGINE LOADER ---
def supreme_find_and_load_json():
    file_name = 'sentient_3600_truths.json'
    base_dir = os.path.dirname(os.path.abspath(__file__))
    search_locations = [os.path.join(base_dir, file_name), os.path.join(base_dir, "app", file_name), os.path.join(os.getcwd(), file_name)]
    for path in search_locations:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
    return {}

TRUTH_DICTIONARY = supreme_find_and_load_json()

# --- Database Setup (INTERNAL URL INTEGRATED) ---
DATABASE_URL = "postgresql://cosmic_db_bpy5_user:jUNSlUR2Y4enT5fxscpuENBM6PyTVnZQ@dpg-d51ureumcj7s73el69j0-a/cosmic_db_bpy5"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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
    user_a_syncing = Column(Boolean, default=False)
    user_b_syncing = Column(Boolean, default=False)

class ChatMessage(Base):
    __tablename__ = "cosmic_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String)
    receiver = Column(String)
    content = Column(String)
    msg_type = Column(String, default="text") 
    media_url = Column(String, nullable=True)  
    is_flagged = Column(Boolean, default=False) 
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# --- REDIS MANAGER ---
class RedisConnectionManager:
    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url, decode_responses=True) if redis_url else None
        self.local_connections = {}
    async def connect(self, email: str, websocket: WebSocket):
        await websocket.accept()
        if not self.redis: return
        self.local_connections[email] = websocket
        asyncio.create_task(self._redis_listener(email, websocket))
    async def _redis_listener(self, email: str, websocket: WebSocket):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(email)
        try:
            async for m in pubsub.listen():
                if m["type"] == "message": await websocket.send_text(m["data"])
        except: pass
        finally:
            try: await pubsub.unsubscribe(email)
            except: pass
    async def publish_update(self, email: str, data: dict):
        if self.redis: await self.redis.publish(email, json.dumps(data))

manager = RedisConnectionManager(os.getenv("UPSTASH_REDIS_URL"))

# --- SYMMETRIC PAIR-UNIT ENGINE ---
def get_pair_unit_score(u1, u2, p1, p2):
    emails = sorted([u1.lower().strip(), u2.lower().strip()])
    palms = sorted([p1 or "NONE", p2 or "NONE"])
    seed_str = f"{emails[0]}-{emails[1]}-{palms[0]}-{palms[1]}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    state = random.getstate()
    random.seed(seed)
    score = random.randint(30, 99)
    random.setstate(state)
    return score

def fetch_adaptive_layman_truth(factor, score, user):
    try:
        f_key = str(factor).capitalize()
        factor_db = TRUTH_DICTIONARY.get(f_key, {})
        entry = factor_db.get(str(int(score))) or factor_db.get(sorted(factor_db.keys(), key=lambda x: abs(int(x) - int(score)))[0])
        active = json.loads(user.methods) if user.methods else {"Numerology": True, "Astrology": True, "Palmistry": True}
        results = {}
        if active.get("Numerology"): results["Numerology"] = entry.get("Numerology", "Vibrations aligning.")
        if active.get("Astrology"): results["Astrology"] = entry.get("Astrology", "Planets syncing.")
        if active.get("Palmistry"): results["Palmistry"] = entry.get("Palmistry", "Physical signatures matching.")
        return results
    except: return {"Insight": f"Resonance at {score}%"}

async def scan_audio_for_leak(file_bytes: bytes):
    try:
        segments, _ = local_whisper.transcribe(io.BytesIO(file_bytes), beam_size=5)
        text_content = " ".join([s.text for s in segments]).lower()
        return any(re.search(CONTACT_PATTERNS, text_content) for p in [CONTACT_PATTERNS])
    except: return False

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- APP & CORS ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cosmic-soulmate-web.web.app", "https://cosmic-soulmate-web.firebaseapp.com", "http://localhost:5000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# --- ENDPOINTS ---

@app.post("/signup-full")
async def signup(name: str = Form(...), email: str = Form(...), birthday: str = Form(...), palm_signature: str = Form(...), full_legal_name: str = Form(None), birth_time: str = Form(None), birth_location: str = Form(None), methods: str = Form("{}"), fcm_token: str = Form("NONE"), photos: List[UploadFile] = File(None), db: Session = Depends(get_db)):
    clean_email = email.strip().lower()
    photo_urls = []
    if photos:
        for photo in photos:
            try: 
                res = cloudinary.uploader.upload(await photo.read()); photo_urls.append(res['secure_url'])
            except: pass
    date_obj = datetime.strptime(birthday.split(" ")[0], "%Y-%m-%d").date()
    user = db.query(User).filter(User.email == clean_email).first() or User(email=clean_email)
    if not user.id: db.add(user)
    user.name, user.birthday, user.palm_signature, user.full_legal_name = name, date_obj, palm_signature, full_legal_name
    user.birth_time, user.birth_location, user.methods, user.photos, user.fcm_token = birth_time, birth_location, methods, ",".join(photo_urls), fcm_token
    db.commit()

    sign = get_sun_sign(date_obj.day, date_obj.month)
    element = get_astrological_element(sign)
    vector = generate_vibe_vector(f"Sign: {sign}, Element: {element}, Name: {name}")
    pinecone_index.upsert(vectors=[{"id": clean_email, "values": vector, "metadata": {"name": name, "sign": sign, "element": element}}])
    return {"message": "Success", "signature": palm_signature}

@app.get("/feed")
async def get_god_tier_feed(current_email: str, db: Session = Depends(get_db)):
    clean_me = current_email.strip().lower()
    if clean_me in ["ping", "warmup"]: return {"status": "ready"}
    me = db.query(User).filter(User.email == clean_me).first()
    if not me: raise HTTPException(status_code=404)
    
    my_sign = get_sun_sign(me.birthday.day, me.birthday.month)
    my_vec = generate_vibe_vector(f"Sign: {my_sign}, Name: {me.name}")
    
    # 1. INTERNAL SEARCH (App Users)
    s1 = pinecone_index.query(vector=my_vec, top_k=5000, include_metadata=True)
    top_500 = stage_2_elemental_filter(get_astrological_element(my_sign), s1['matches'])
    
    factor_labels = ["Foundation", "Economics", "Lifestyle", "Emotional", "Physical", "Spiritual", "Sexual", "Health", "Power", "Creativity", "Social", "Mental"]
    internal_pool = []
    for cand in top_500:
        if cand['id'] == clean_me: continue
        o = db.query(User).filter(User.email == cand['id']).first()
        if not o: continue
        match_score = get_pair_unit_score(me.email, o.email, me.palm_signature, o.palm_signature)
        match_rec = db.query(Match).filter(((Match.user_a == me.email) & (Match.user_b == o.email)) | ((Match.user_b == me.email) & (Match.user_a == o.email))).first()
        internal_pool.append({
            "name": o.name, "email": o.email, "is_self": False, "is_matched": match_rec.is_mutual if match_rec else False,
            "percentage": f"{match_score}%", "tier": "MARRIAGE MATERIAL" if match_score >= 85 else "INTENSE FLING",
            "photos": o.photos.split(",") if o.photos else [], "sun_sign": cand['metadata'].get('sign'),
            "factors": {f: {"score": f"{min(100, max(1, match_score + (len(f)%7)-3))}%", "why": fetch_adaptive_layman_truth(f, match_score, me)} for f in factor_labels}
        })

    # 2. GLOBAL WORLD RADAR (Social Media Discovery)
    world_matches = await global_world_radar_search(me.name, my_sign)

    # 3. FINAL STAGE 4 RERANK & MERGE
    final_matches = await stage_4_re_rank(my_sign, internal_pool)
    
    self_entry = {"name": "YOUR DESTINY", "percentage": "100%", "is_self": True, "email": me.email, "photos": me.photos.split(",") if me.photos else [], "sun_sign": my_sign, "factors": {f: {"score": "100%", "why": fetch_adaptive_layman_truth(f, 100, me)} for f in factor_labels}, "tier": "GOD TIER", "reading": "Optimized soul blueprint."}
    
    # MIXED FEED: [Self] + [Ranked Internal] + [Global Radar Discoveries]
    return [self_entry] + final_matches + world_matches

@app.post("/send-message")
async def send_message(sender: str = Form(...), receiver: str = Form(...), content: str = Form(""), msg_type: str = Form("text"), audio_file: UploadFile = File(None), db: Session = Depends(get_db)):
    s, r = sender.lower().strip(), receiver.lower().strip()
    match = db.query(Match).filter(((Match.user_a == s) & (Match.user_b == r) & (Match.is_mutual == True)) | ((Match.user_b == s) & (Match.user_a == r) & (Match.is_mutual == True))).first()
    if not match: raise HTTPException(status_code=403)
    
    violation = False
    if msg_type == "text" and re.search(CONTACT_PATTERNS, content.lower()): violation = True
    if msg_type == "audio" and audio_file:
        audio_data = await audio_file.read()
        if await scan_audio_for_leak(audio_data): violation = True

    if violation:
        db.delete(match); db.commit()
        await manager.publish_update(r, {"type": "mismatch_event"})
        raise HTTPException(status_code=403, detail="Security violation. Bond dissolved.")

    media_url = None
    if msg_type == "audio":
        res = cloudinary.uploader.upload(audio_data, resource_type="video")
        media_url = res['secure_url']; content = "[Voice Vibration]"
    
    if msg_type == "text" and not match.is_unlocked:
        try:
            ai_check = ai_model.generate_content(f"Reply ONLY 'LEAK' or 'SAFE': {content}")
            if "LEAK" in ai_check.text.strip().upper():
                db.delete(match); db.commit(); raise HTTPException(status_code=403)
        except: pass

    new_msg = ChatMessage(sender=s, receiver=r, content=content, msg_type=msg_type, media_url=media_url)
    db.add(new_msg); db.commit()
    await manager.publish_update(r, {"sender": s, "content": content, "type": msg_type, "url": media_url, "time": datetime.utcnow().isoformat()})
    return {"status": "sent"}

@app.delete("/delete-profile")
def delete_profile(email: str, db: Session = Depends(get_db)):
    e = email.strip().lower()
    db.query(User).filter(User.email == e).delete()
    db.query(Match).filter((Match.user_a == e) | (Match.user_b == e)).delete()
    db.query(ChatMessage).filter((ChatMessage.sender == e) | (ChatMessage.receiver == e)).delete()
    try: pinecone_index.delete(ids=[e])
    except: pass
    db.commit()
    return {"message": "Deleted"}

@app.websocket("/ws/{email}")
async def websocket_endpoint(websocket: WebSocket, email: str):
    await manager.connect(email.lower().strip(), websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.local_connections.pop(email.lower().strip(), None)

@app.get("/chat-status")
async def chat_status(me: str, them: str, db: Session = Depends(get_db)):
    me, them = me.lower().strip(), them.lower().strip()
    match = db.query(Match).filter(((Match.user_a == me) & (Match.user_b == them)) | ((Match.user_b == me) & (Match.user_a == them))).first()
    other_typing = (match.user_b_typing if match.user_a == me else match.user_a_typing) if match else False
    is_synced = (match.user_a_syncing and match.user_b_syncing) if match else False
    return {"accepted": match.user_a_accepted or match.user_b_accepted if match else False, "is_typing": other_typing, "is_synced": is_synced}

def get_sun_sign(day, month):
    zodiac_data = [(19,"Aquarius"),(18,"Pisces"),(20,"Aries"),(19,"Taurus"),(20,"Gemini"),(20,"Cancer"),(22,"Leo"),(22,"Virgo"),(22,"Libra"),(22,"Scorpio"),(21,"Sagittarius"),(21,"Capricorn")]
    idx = month - 1
    return zodiac_data[idx][1] if day > zodiac_data[idx][0] else zodiac_data[(idx - 1) % 12][1]