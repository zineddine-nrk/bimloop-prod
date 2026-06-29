from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from auth_config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)
from auth_db import get_db
from auth_models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise _credentials_exception()
        try:
            user_id_int = int(user_id)
        except ValueError as exc:
            raise _credentials_exception() from exc
    except JWTError as exc:
        raise _credentials_exception() from exc
    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None:
        raise _credentials_exception()
    return user


def require_role(*roles: str):
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès interdit.",
            )
        return user

    return role_checker
