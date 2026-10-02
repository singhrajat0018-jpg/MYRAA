"""
MYRAA Groww Trading Advisor — Authentication Handler

Supports:
- Direct access token
- API Key + Secret (checksum-based)
- TOTP-based authentication

Security: Never stores passwords, API secrets, or auth tokens in Memory 2.0.
Tokens expire daily at 6:00 AM IST.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

GROWW_BASE_URL = "https://api.groww.in/v1"
TOKEN_EXPIRY_HOUR = 6  # 6:00 AM IST


@dataclass
class GrowwAuthConfig:
    access_token: str = ""
    api_key: str = ""
    api_secret: str = ""
    totp_secret: str = ""
    credential_file: str = ""

    @classmethod
    def from_env(cls) -> "GrowwAuthConfig":
        return cls(
            access_token=os.environ.get("GROWW_ACCESS_TOKEN", ""),
            api_key=os.environ.get("GROWW_API_KEY", ""),
            api_secret=os.environ.get("GROWW_API_SECRET", ""),
            totp_secret=os.environ.get("GROWW_TOTP_SECRET", ""),
            credential_file=os.environ.get("GROWW_CREDENTIAL_FILE", ""),
        )

    @classmethod
    def from_file(cls, path: str) -> "GrowwAuthConfig":
        p = Path(path)
        if not p.exists():
            return cls()
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                access_token=data.get("access_token", ""),
                api_key=data.get("api_key", ""),
                api_secret=data.get("api_secret", ""),
                totp_secret=data.get("totp_secret", ""),
                credential_file=path,
            )
        except Exception:
            return cls()

    def has_token(self) -> bool:
        return bool(self.access_token)

    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def has_totp(self) -> bool:
        return bool(self.totp_secret)


@dataclass
class GrowwAuthState:
    authenticated: bool = False
    token_expiry: Optional[datetime] = None
    last_auth_attempt: Optional[datetime] = None
    last_error: str = ""
    auth_method: str = "none"

    def is_token_valid(self) -> bool:
        if not self.authenticated or self.token_expiry is None:
            return False
        return datetime.utcnow() < self.token_expiry


class GrowwAuthenticator:
    """Handles Groww API authentication with credential boundary."""

    def __init__(self, config: Optional[GrowwAuthConfig] = None):
        self._config = config or GrowwAuthConfig.from_env()
        self._state = GrowwAuthState()
        self._token: str = ""
        if self._config.credential_file and not self._config.has_token():
            file_config = GrowwAuthConfig.from_file(self._config.credential_file)
            if file_config.has_token():
                self._config = file_config
        if self._config.has_token():
            self._token = self._config.access_token
            self._state.authenticated = True
            self._state.auth_method = "direct_token"
            self._state.token_expiry = self._compute_expiry()

    def get_token(self) -> str:
        return self._token

    def get_headers(self) -> Dict[str, str]:
        if not self._token:
            return {}
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "X-API-VERSION": "1.0",
        }

    def is_authenticated(self) -> bool:
        return self._state.is_token_valid()

    def get_state(self) -> Dict[str, Any]:
        return {
            "authenticated": self._state.authenticated,
            "auth_method": self._state.auth_method,
            "token_valid": self._state.is_token_valid(),
            "token_expiry": self._state.token_expiry.isoformat() if self._state.token_expiry else None,
            "last_error": self._state.last_error,
        }

    def authenticate_with_api_key(self, api_key: str, api_secret: str) -> bool:
        """Authenticate using API Key + Secret checksum flow."""
        self._state.last_auth_attempt = datetime.utcnow()
        try:
            timestamp = str(int(time.time()))
            checksum = hashlib.sha256((api_secret + timestamp).encode()).hexdigest()
            payload = json.dumps({
                "key_type": "approval",
                "checksum": checksum,
                "timestamp": timestamp,
            }).encode()
            req = Request(
                f"{GROWW_BASE_URL}/token/api/access",
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            token = data.get("access_token", "")
            if token:
                self._token = token
                self._state.authenticated = True
                self._state.auth_method = "api_key"
                self._state.token_expiry = self._compute_expiry()
                self._state.last_error = ""
                return True
            self._state.last_error = "No access_token in response"
            return False
        except Exception as exc:
            self._state.last_error = str(exc)
            self._state.authenticated = False
            return False

    def authenticate_with_totp(self, api_key: str, totp_secret: str) -> bool:
        """Authenticate using TOTP flow."""
        self._state.last_auth_attempt = datetime.utcnow()
        try:
            try:
                import pyotp
            except ImportError:
                self._state.last_error = "pyotp not installed"
                return False
            totp = pyotp.TOTP(totp_secret)
            payload = json.dumps({
                "key_type": "totp",
                "totp": totp.now(),
            }).encode()
            req = Request(
                f"{GROWW_BASE_URL}/token/api/access",
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            token = data.get("access_token", "")
            if token:
                self._token = token
                self._state.authenticated = True
                self._state.auth_method = "totp"
                self._state.token_expiry = self._compute_expiry()
                self._state.last_error = ""
                return True
            self._state.last_error = "No access_token in response"
            return False
        except Exception as exc:
            self._state.last_error = str(exc)
            self._state.authenticated = False
            return False

    def refresh_if_needed(self) -> bool:
        """Attempt re-authentication if token is expired or about to expire."""
        if self._state.is_token_valid():
            return True
        if self._config.has_totp() and self._config.has_api_key():
            return self.authenticate_with_totp(self._config.api_key, self._config.totp_secret)
        if self._config.has_api_key():
            return self.authenticate_with_api_key(self._config.api_key, self._config.api_secret)
        return False

    def _compute_expiry(self) -> datetime:
        now = datetime.utcnow()
        if now.hour >= TOKEN_EXPIRY_HOUR:
            expiry = now.replace(hour=TOKEN_EXPIRY_HOUR, minute=0, second=0, microsecond=0)
            from datetime import timedelta
            expiry += timedelta(days=1)
        else:
            expiry = now.replace(hour=TOKEN_EXPIRY_HOUR, minute=0, second=0, microsecond=0)
        return expiry
