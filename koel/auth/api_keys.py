from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

KEY_PREFIX_LENGTH = 8
KEY_SECRET_BYTES = 24  # token_urlsafe(24) yields 32 chars


@dataclass(frozen=True, slots=True)
class ApiKeyMaterial:
    raw: str  # "koel_<prefix>_<secret>" — shown once, never stored
    prefix: str  # 8 chars, safe to display
    hashed: str  # sha256(raw), hex — stored


def _random_prefix() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(KEY_PREFIX_LENGTH))


def generate_api_key() -> ApiKeyMaterial:
    prefix = _random_prefix()
    secret = secrets.token_urlsafe(KEY_SECRET_BYTES)
    raw = f"koel_{prefix}_{secret}"
    return ApiKeyMaterial(raw=raw, prefix=prefix, hashed=hash_api_key(raw))


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_prefix(raw: str) -> str | None:
    """Best-effort prefix extraction for logs. Returns ``None`` on malformed input."""
    if not raw.startswith("koel_"):
        return None
    parts = raw.split("_", 2)
    if len(parts) < 3:
        return None
    prefix = parts[1]
    if len(prefix) != KEY_PREFIX_LENGTH:
        return None
    return prefix
