from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import os

# --- DATABASE CONNECTION ---
# Render provides the DATABASE_URL environment variable
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- AUTOMATIC DATABASE MIGRATION ---
# This adds your new columns automatically without manual SQL terminal commands
def migrate_db(engine):
    with engine.connect() as conn:
        # Add columns for hidden physical traits
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS sensitive_traits TEXT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS body_type TEXT"))
        # Add columns for consent and security
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS nsfw_enabled TEXT DEFAULT 'false'"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_password TEXT"))
        # Add columns for life path and lifestyle
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS life_path INTEGER"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS diet TEXT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS pets TEXT"))
        conn.commit()

# Trigger migration on server startup
migrate_db(engine)

# --- DATABASE MODELS ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    life_path = Column(Integer)
    religion = Column(String, nullable=True)
    caste = Column(String, nullable=True)
    diet = Column(String, nullable=True)
    pets = Column(String, nullable=True)
    income = Column(String, nullable=True)
    job_status = Column(String, nullable=True)
    education = Column(String, nullable=True)
    politics = Column(String, nullable=True)
    phone_password = Column(String, nullable=True)
    nsfw_enabled = Column(String, default="false") #
    sensitive_traits = Column(String, nullable=True) # Hidden sizes
    body_type = Column(String, nullable=True) # Physical build
    palm_image_url = Column(String, nullable=True)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# --- PYDANTIC SCHEMAS (DATA VALIDATION) ---
class UserBase(BaseModel):
    name: str
    email: str
    life_path: int
    religion: Optional[str] = None
    caste: Optional[str] = None
    diet: Optional[str] = None
    pets: Optional[str] = None
    income: Optional[str] = None
    job_status: Optional[str] = None
    education: Optional[str] = None
    politics: Optional[str] = None
    phone_password: Optional[str] = None
    nsfw_enabled: Optional[str] = "false" #
    sensitive_traits: Optional[str] = None #
    body_type: Optional[str] = None #
    palm_image_url: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    class Config:
        from_attributes = True

# --- API ENDPOINTS ---
app = FastAPI(title="Cosmic Match Backend")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(**user.dict())
    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return db_user

@app.get("/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)