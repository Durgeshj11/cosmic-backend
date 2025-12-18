from sqlmodel import create_engine, Session

# Connection to your Docker Database
DATABASE_URL = "postgresql://cosmic_admin:secure_password_123@localhost:5432/cosmic_db"

engine = create_engine(DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session