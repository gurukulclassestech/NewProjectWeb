"""Simple JWT-based admin authentication for NJ Edu-Hub."""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Header
from passlib.context import CryptContext
from pydantic import BaseModel

JWT_SECRET = os.environ.get('JWT_SECRET', 'nj-eduhub-default-secret-change-me')
JWT_ALGO = 'HS256'
JWT_TTL_HOURS = 12

pwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')


def hash_pw(pw: str) -> str:
    return pwd_ctx.hash(pw)


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return pwd_ctx.verify(pw, hashed)
    except Exception:
        return False


def issue_token(username: str) -> str:
    payload = {
        'sub': username,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        return None


# ------- Pydantic models -------
class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class TokenOut(BaseModel):
    token: str
    username: str
    expires_in_hours: int = JWT_TTL_HOURS


# ------- DB helpers -------
async def ensure_default_admin(db):
    """Seed a default admin (admin / admin@123) on first run."""
    if await db.admins.count_documents({}) == 0:
        await db.admins.insert_one({
            'id': str(uuid.uuid4()),
            'username': os.environ.get('ADMIN_USERNAME', 'admin'),
            'password_hash': hash_pw(os.environ.get('ADMIN_PASSWORD', 'admin@123')),
            'created_at': datetime.utcnow().isoformat(),
        })


# ------- FastAPI dependency -------
def require_admin(authorization: Optional[str] = Header(None)) -> str:
    """Validates the Bearer token. Returns username; raises 401 otherwise."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Missing or invalid Authorization header')
    token = authorization.split(' ', 1)[1].strip()
    payload = decode_token(token)
    if not payload or not payload.get('sub'):
        raise HTTPException(status_code=401, detail='Invalid or expired token')
    return payload['sub']
