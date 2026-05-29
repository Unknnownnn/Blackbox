import hmac
import hashlib
import os

def _master_secret() -> bytes:
    return os.environ.get("FLAG_HMAC_SECRET", "change-me-in-env").encode()

def _challenge_key(challenge_id: int) -> bytes:
    """Derive a unique key per challenge via HKDF-lite (HMAC-based)."""
    return hmac.new(
        _master_secret(),
        f"challenge:{challenge_id}".encode(),
        hashlib.sha256
    ).digest()

def generate_hmac_flag(challenge_id: int, team_id: int | None, user_id: int | None, prefix: str = "CYS") -> str:
    identifier = f"team_{team_id}" if team_id else f"user_{user_id}"
    msg = identifier.encode()
    digest = hmac.new(_challenge_key(challenge_id), msg, hashlib.sha256).hexdigest()
    return f"{prefix}{{{digest}}}"

def verify_hmac_flag(submitted: str, challenge_id: int, team_id: int | None, user_id: int | None, prefix: str = "CYS") -> bool:
    expected = generate_hmac_flag(challenge_id, team_id, user_id, prefix)
    return hmac.compare_digest(expected, submitted.strip())