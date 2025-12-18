from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Field, Session, create_engine, select
from typing import List, Optional

# --- DATABASE SETUP ---
# Note: SQLite on Render clears every time you deploy.
# For permanent data later, you will need PostgreSQL.
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# --- MODELS (Data Structure) ---
# If your app has different fields (like 'age' or 'password'), add them here.
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str

# --- APP & CORS SETUP ---
app = FastAPI()

# 🟢 THIS IS THE FIX FOR YOUR ERROR 🟢
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # Allows Flutter Web to connect
    allow_credentials=True,
    allow_methods=["*"],    # Allows POST, GET, DELETE, etc.
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --- ROUTES ---

@app.get("/")
def read_root():
    return {"message": "Server is up and running!"}

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
        users = session.exec(select(User)).all()
        return users