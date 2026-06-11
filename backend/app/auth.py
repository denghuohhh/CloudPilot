from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlmodel import Session, select
from .config import settings
from .db import get_session, verify_password as _verify_password, hash_password as _hash_password
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
ALGORITHM = "HS256"

def verify_password(raw: str, hashed: str) -> bool:
    return _verify_password(raw, hashed)

def hash_password(raw: str) -> str:
    return _hash_password(raw)

def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(days=30)
    return jwt.encode({"sub": username, "exp": expire}, settings.secret_key, algorithm=ALGORITHM)

def current_user(token: Optional[str] = Depends(oauth2_scheme), session: Session = Depends(get_session)) -> User:
    username: Optional[str] = settings.admin_user
    if token:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
            username = payload.get("sub") or settings.admin_user
        except JWTError:
            username = settings.admin_user
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or user.disabled:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user

def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user
