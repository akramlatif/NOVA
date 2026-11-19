"""Authentication, Security Tokens, Rate Limiting, and Audit Logging for NOVA."""

import os
import hmac
import time
import json
import base64
import hashlib
import secrets
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("nova.auth")

DEFAULT_SECRET_KEY = secrets.token_hex(32)
TOKEN_TTL_SECONDS = 3600  # 1 hour short-lived access token


def _get_server_secret(data_dir: str) -> bytes:
    """Retrieve or generate persistent server HMAC secret."""
    secret_path = os.path.join(data_dir, "server_secret.key")
    if os.path.exists(secret_path):
        with open(secret_path, "rb") as f:
            return f.read().strip()
    secret = secrets.token_bytes(32)
    os.makedirs(data_dir, exist_ok=True)
    with open(secret_path, "wb") as f:
        f.write(secret)
    return secret


class TokenManager:
    """Issues and verifies cryptographically signed HMAC-SHA256 access tokens."""

    def __init__(self, secret: bytes):
        self.secret = secret

    def create_token(self, payload: Dict[str, Any], ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
        """Create a tamper-proof short-lived token."""
        header = {"alg": "HS256", "typ": "JWT"}
        exp = int(time.time()) + ttl_seconds
        full_payload = {**payload, "exp": exp, "iat": int(time.time())}

        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        p_b64 = base64.urlsafe_b64encode(json.dumps(full_payload).encode()).decode().rstrip("=")
        signing_input = f"{h_b64}.{p_b64}".encode()
        signature = hmac.new(self.secret, signing_input, hashlib.sha256).digest()
        s_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        return f"{h_b64}.{p_b64}.{s_b64}"

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify token signature and expiration."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            h_b64, p_b64, s_b64 = parts

            # Verify signature
            signing_input = f"{h_b64}.{p_b64}".encode()
            expected_sig = hmac.new(self.secret, signing_input, hashlib.sha256).digest()

            # Add padding back if necessary
            sig_padded = s_b64 + "=" * (-len(s_b64) % 4)
            actual_sig = base64.urlsafe_b64decode(sig_padded.encode())

            if not hmac.compare_digest(expected_sig, actual_sig):
                return None

            # Verify expiration
            payload_padded = p_b64 + "=" * (-len(p_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_padded.encode()).decode())
            if payload.get("exp", 0) < int(time.time()):
                return None  # Expired

            return payload
        except Exception as e:
            logger.debug(f"Token verification failed: {e}")
            return None


class PasswordHasher:
    """PBKDF2-HMAC-SHA256 password hasher with random salts."""

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100000,
        )
        return f"{salt}:{key.hex()}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        try:
            salt, key_hex = stored_hash.split(":")
            key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations=100000,
            )
            return hmac.compare_digest(key.hex(), key_hex)
        except Exception:
            return False


class RateLimiter:
    """Sliding-window in-memory rate limiter per client IP/key."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        if client_id not in self.requests:
            self.requests[client_id] = [now]
            return True

        # Clean old entries
        self.requests[client_id] = [t for t in self.requests[client_id] if t > window_start]
        if len(self.requests[client_id]) < self.max_requests:
            self.requests[client_id].append(now)
            return True
        return False


class AuditLogger:
    """Appends security-relevant events to logs/audit.jsonl."""

    def __init__(self, log_path: str):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(self, event: str, actor: str, client_ip: str, success: bool, details: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "actor": actor,
            "client_ip": client_ip,
            "success": success,
            "details": details or {},
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Audit log write failed: {e}")
