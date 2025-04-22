from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import hashlib
import os
from main import User, Base

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_admin_user(username, password):
    # Connect to the database
    DATABASE_URL = os.environ.get("DATABASE_URL")
    engine = create_engine(DATABASE_URL)
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Create a session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Check if the admin already exists
    admin = db.query(User).filter(User.username == username).first()
    
    if admin:
        print(f"Администратор с именем '{username}' уже существует.")
        return
    
    # Create an admin user
    new_admin = User(
        username=username,
        password=hash_password(password),
        is_admin=True
    )
    
    # Add and commit
    db.add(new_admin)
    db.commit()
    
    print(f"Администратор '{username}' успешно создан.")

if __name__ == "__main__":
    create_admin_user("root", "2344gr")