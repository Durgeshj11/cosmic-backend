from sqlmodel import create_engine, Session

# 1. Setup the database file name
sqlite_file_name = "cosmic.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# 2. Create the ENGINE (This was likely missing or private before!)
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)

# 3. Session Generator (Used by endpoints)
def get_session():
    with Session(engine) as session:
        yield session