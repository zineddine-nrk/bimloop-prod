from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, func

from auth_db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(320), unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String(20), nullable=False, default="user")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
