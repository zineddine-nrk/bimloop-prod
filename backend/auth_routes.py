from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth_config import ACCESS_TOKEN_EXPIRE_MINUTES
from auth_db import get_db
from auth_models import User
from auth_schemas import RoleUpdate, Token, UserCreate, UserLogin, UserOut
from auth_security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)


auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email déjà utilisé.",
        )
    user = User(email=email, password_hash=hash_password(payload.password), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@auth_router.post("/login", response_model=Token)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@auth_router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@auth_router.get(
    "/users",
    response_model=list[UserOut],
    dependencies=[Depends(require_role("admin"))],
)
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id.asc()).all()


@auth_router.patch(
    "/users/{user_id}/role",
    response_model=UserOut,
    dependencies=[Depends(require_role("admin"))],
)
def update_user_role(user_id: int, payload: RoleUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user
