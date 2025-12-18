from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Field, Session, create_engine, select
from typing import List, Optional
import os

# --- DATABASE SETUP ---
# Uses the Render Environment Variable we set up
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cosmic_db_8iio_user:DN2KPuhDRzOUZqQlMqZSt49mJbUzoJL9@dpg-d51tjdjuibrs739i2ceg-a/cosmic_db_8iio")

# SQLAlchemy requires 'postgresql://' instead of 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# --- MODELS ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: Optional[str] = None
    birthday: Optional[str] = None
    life_path: Optional[int] = None

# --- NUMEROLOGY LOGIC ---
def calculate_life_path(dob: str):
    if not dob: return None
    # Example: "1995-05-20" -> 1+9+9+5+0+5+2+0 = 31 -> 3+1 = 4
    digits = [int(d) for d in dob if d.isdigit()]
    total = sum(digits)
    while total > 9 and total not in [11, 22, 33]: # Keep Master Numbers
        total = sum(int(d) for d in str(total))
    return total

# --- APP SETUP ---
app = FastAPI(title="Cosmic Connections API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --- ROUTES ---

@app.get("/users", response_model=List[User])
def read_users():
    with Session(engine) as session:
        return session.exec(select(User)).all()

@app.post("/users", response_model=User)
def create_user(user: User):
    # Calculate Life Path before saving to PostgreSQL
    if user.birthday:
        user.life_path = calculate_life_path(user.birthday)
    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        session.delete(user)
        session.commit()
        return {"ok": True}