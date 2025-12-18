from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import date

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    dob: date

    # Cosmic Data
    sun_sign: str
    life_path_number: int
    hand_element: str = "Unknown"
    dominant_mount: str = "Unknown"
    heart_line_type: str = "Unknown"

    # Match Score (for caching)
    match_score: Optional[int] = None