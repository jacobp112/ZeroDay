from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from pydantic import BaseModel

from brokerage_parser.config import settings
from brokerage_parser.db import get_db
from brokerage_parser.models.admin import AdminUser
from brokerage_parser.core.security import verify_password

router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/token")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class AdminUserResponse(BaseModel):
    id: str
    email: str
    role: str
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.ADMIN_JWT_SECRET, algorithm="HS256")
    return encoded_jwt

def get_current_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.ADMIN_JWT_SECRET, algorithms=["HS256"])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = db.query(AdminUser).filter(AdminUser.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Set Admin Context for RLS Bypass
    try:
        from sqlalchemy import text, event
        # 1. Set for current transaction
        # Use set_config to allow arbitrary variables without postgresql.conf definition
        db.execute(text("SELECT set_config('app.is_admin', 'true', true)"))

        # 2. Set for future transactions (e.g. after commit/refresh) on this session
        @event.listens_for(db, "after_begin")
        def receive_after_begin(session, transaction, connection):
             connection.execute(text("SELECT set_config('app.is_admin', 'true', true)"))

    except Exception as e:
        # Log error
        import traceback
        print("❌ FAILED TO SET ADMIN CONTEXT:")
        traceback.print_exc()
        pass

    return user

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter(AdminUser.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    access_token_expires = timedelta(minutes=1440) # 24 hours
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=AdminUserResponse)
async def read_users_me(current_user: AdminUser = Depends(get_current_admin)):
    return current_user
