from main import Base, engine

print("⚠️  Warning: This will delete all current users and messages.")
print("Dropping old tables...")

# This deletes the 'user' and 'messages' tables completely
Base.metadata.drop_all(bind=engine)

print("Creating new tables with 'palm_score'...")
# This recreates them with the NEW columns
Base.metadata.create_all(bind=engine)

print("✅ Database reset complete! You can now start the server.")