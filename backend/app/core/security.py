import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the subject (user id) if the token is valid, else None."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# AES-GCM token encryption (for OAuth tokens at rest)
# ---------------------------------------------------------------------------
def _encryption_key() -> bytes:
    """Return a 32-byte key. Prefer the configured key; otherwise derive a
    deterministic dev key from the JWT secret (NOT for production)."""
    if settings.token_encryption_key:
        return base64.b64decode(settings.token_encryption_key)
    return hashlib.sha256(settings.jwt_secret.encode()).digest()


def encrypt_token(plaintext: str | None) -> bytes | None:
    if plaintext is None:
        return None
    aesgcm = AESGCM(_encryption_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    # Store nonce prepended to ciphertext.
    return nonce + ciphertext


def decrypt_token(blob: bytes | None) -> str | None:
    if blob is None:
        return None
    aesgcm = AESGCM(_encryption_key())
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
