import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

SECRET = os.getenv('JWT_SECRET') or os.getenv('SECRET_KEY') or 'change-this-secret-in-env'
ALGORITHM = 'HS256'
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login')

PBKDF2_ITERATIONS = int(os.getenv('PASSWORD_ITERATIONS', '260000'))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))


def hash_password(password: str) -> str:
    if not password:
        raise ValueError('密码不能为空')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64(salt)}${_b64(digest)}'


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    # 兼容旧库 plain:123456：登录成功后 main.py 会自动升级为 PBKDF2 哈希。
    if hashed.startswith('plain:'):
        return hmac.compare_digest(plain, hashed.removeprefix('plain:'))
    try:
        algorithm, iter_text, salt_text, digest_text = hashed.split('$', 3)
        if algorithm != 'pbkdf2_sha256':
            return False
        iterations = int(iter_text)
        salt = _unb64(salt_text)
        expected = _unb64(digest_text)
        actual = hashlib.pbkdf2_hmac('sha256', plain.encode('utf-8'), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def is_legacy_hash(hashed: str) -> bool:
    return bool(hashed and hashed.startswith('plain:'))


def create_token(user: User) -> str:
    payload = {
        'sub': str(user.id), 'username': user.username, 'role': user.role,
        'direction': user.direction, 'exp': datetime.now(timezone.utc) + timedelta(hours=12)
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        user_id = int(payload.get('sub'))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='登录已失效')
    user = db.get(User, user_id)
    if not user or user.status != 'enabled':
        raise HTTPException(status_code=401, detail='用户不存在或已禁用')
    return user


def require_super(user: User = Depends(current_user)) -> User:
    if user.role != 'super_admin':
        raise HTTPException(status_code=403, detail='仅超级管理员可操作')
    return user
