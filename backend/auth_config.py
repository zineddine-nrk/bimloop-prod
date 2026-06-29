import os


def _get_int(name: str, default: str) -> int:
    raw = os.environ.get(name, default)
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


_DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(_DATA_DIR, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{os.path.join(_DATA_DIR, 'auth.db')}"
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-dev")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = _get_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
PUBLIC_URL = os.environ.get("PUBLIC_URL")


def require_auth_settings() -> None:
    pass
