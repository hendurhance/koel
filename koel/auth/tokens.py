from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

TOKEN_BYTES = 32  # 256 bits of entropy


@dataclass(frozen=True, slots=True)
class Token:
    raw: str
    hashed: str


def generate_token() -> Token:
    """Create a fresh URL-safe token plus its sha256 digest (hex)."""
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    return Token(raw=raw, hashed=hash_token(raw))


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
