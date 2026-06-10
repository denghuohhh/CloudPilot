from sqlmodel import SQLModel, Session, create_engine, select
from hashlib import sha256
from .config import settings
from .models import User

engine = create_engine(f"sqlite:///{settings.db}", connect_args={"check_same_thread": False})

def hash_password(raw: str) -> str:
    return sha256(raw.encode("utf-8")).hexdigest()

def verify_password(raw: str, hashed: str) -> bool:
    return hash_password(raw) == hashed

def init_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.username == settings.admin_user)).first()
        if not existing:
            session.add(User(
                username=settings.admin_user,
                password_hash=hash_password(settings.admin_password),
                is_admin=True
            ))
            session.commit()

def get_session():
    with Session(engine) as session:
        yield session
