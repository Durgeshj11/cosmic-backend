from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Field, Session, create_engine, select
from typing import List, Optional
import os

# --- DATABASE SETUP ---
# We use your Internal URL here. 
# Added a .replace() fix to ensure compatibility with SQLAlchemy.
raw_url = "postgresql://cosmic_db_8iio_user:DN2KPuhDRzOUZqQlMqZSt49mJbUzoJL9@dpg-d51tjdjuibrs739i2ceg-a/cosmic_db_8iio"
if raw_url.startswith("postgres://"):
    raw_url = raw_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(raw_url, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# --- MODELS ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: Optional[str] = None
    life_path: Optional[int] = None

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
@app.get("/")
def read_root():
    return {"message": "Cosmic Backend is Live on PostgreSQL!"}

@app.post("/users", response_model=User)
def create_user(user: User):
    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

@app.get("/users", response_model=List[User])
def read_users():
    with Session(engine) as session:
        return session.exec(select(User)).all()