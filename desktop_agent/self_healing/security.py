from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Tuple


class ProtectedArea(Enum):
    BROKER_TRADING = "broker_trading"
    SECRET_STORAGE = "secret_storage"
    AUTHENTICATION = "authentication"
    PERMISSIONS = "permissions"
    MEMORY_SECURITY = "memory_security"
    SYSTEM_POWER = "system_power"
    CREDENTIAL_HANDLING = "credential_handling"
    FINANCIAL_EXECUTION = "financial_execution"


@dataclass(frozen=True)
class SecurityViolation:
    area: ProtectedArea
    description: str
    proposed_action: str
    blocked: bool
    timestamp: float


_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"TAVILY_API_KEY", re.IGNORECASE),
    re.compile(r"(?:password|passwd|pwd)\s*=", re.IGNORECASE),
    re.compile(r"(?:token|access_token|refresh_token)\s*=", re.IGNORECASE),
    re.compile(r"(?:secret|secret_key|SECRET)\s*=", re.IGNORECASE),
    re.compile(r"(?:API_KEY|api_key|apikey)\s*=", re.IGNORECASE),
    re.compile(r"bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
]

_DANGEROUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\b__import__\s*\("),
    re.compile(r"\bos\.system\s*\("),
    re.compile(r"\bsubprocess\b.*\bshell\s*=\s*True"),
    re.compile(r"\bpickle\.load(?:s)?\s*\("),
    re.compile(r"\byaml\.load\s*\([^)]*\)(?!\s*,\s*.*Loader\s*=\s*yaml\.SafeLoader)"),
]

_PROTECTED_PATHS: list[str] = [
    "server_paths.ts",
    "secrets.json",
    ".env",
]

_PROTECTED_PATH_SUBSTRINGS: list[str] = [
    "api_key",
    "apikey",
    "secret",
    "credential",
    "token",
    "password",
]


def _file_in_protected_area(file_path: str) -> Tuple[bool, ProtectedArea | None]:
    lower = file_path.lower().replace("\\", "/")
    for pp in _PROTECTED_PATHS:
        if lower.endswith(pp) or f"/{pp}" in lower:
            return True, ProtectedArea.SECRET_STORAGE
    for sub in _PROTECTED_PATH_SUBSTRINGS:
        if sub in lower:
            return True, ProtectedArea.CREDENTIAL_HANDLING
    return False, None


class SecurityGate:
    _instance: SecurityGate | None = None
    _lock_class = threading.Lock()
    _MAX_VIOLATIONS = 100

    def __new__(cls) -> SecurityGate:
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_fields()
            return cls._instance

    def _init_fields(self) -> None:
        self._lock = threading.Lock()
        self._violations: list[SecurityViolation] = []

    def check_proposal(
        self,
        proposed_changes: dict[str, str],
        target_files: list[str],
    ) -> Tuple[bool, list[SecurityViolation]]:
        violations: list[SecurityViolation] = []
        now = time.time()

        for fp in target_files:
            is_protected, area = _file_in_protected_area(fp)
            if is_protected and area is not None:
                v = SecurityViolation(
                    area=area,
                    description=f"Target file '{fp}' is in a protected area ({area.value})",
                    proposed_action="modify_protected_file",
                    blocked=True,
                    timestamp=now,
                )
                violations.append(v)

        for fname, code in proposed_changes.items():
            secret_hits = self.scan_code_for_secrets(code)
            for hit in secret_hits:
                v = SecurityViolation(
                    area=ProtectedArea.SECRET_STORAGE,
                    description=f"Secret pattern detected in '{fname}': {hit}",
                    proposed_action="introduce_secret",
                    blocked=True,
                    timestamp=now,
                )
                violations.append(v)

            danger_hits = self.scan_code_for_dangerous_patterns(code)
            for hit in danger_hits:
                v = SecurityViolation(
                    area=ProtectedArea.SYSTEM_POWER,
                    description=f"Dangerous pattern in '{fname}': {hit}",
                    proposed_action="dangerous_code",
                    blocked=True,
                    timestamp=now,
                )
                violations.append(v)

        with self._lock:
            for v in violations:
                if len(self._violations) >= self._MAX_VIOLATIONS:
                    self._violations.pop(0)
                self._violations.append(v)

        blocked = any(v.blocked for v in violations)
        return (not blocked), violations

    def check_file_access(self, file_path: str, mode: str) -> bool:
        is_protected, _ = _file_in_protected_area(file_path)
        if is_protected and mode in ("w", "a", "x"):
            return False
        return True

    def scan_code_for_secrets(self, code: str) -> list[str]:
        hits: list[str] = []
        for pat in _SECRET_PATTERNS:
            for m in pat.finditer(code):
                hits.append(m.group().strip())
        return hits

    def scan_code_for_dangerous_patterns(self, code: str) -> list[str]:
        hits: list[str] = []
        for pat in _DANGEROUS_PATTERNS:
            for m in pat.finditer(code):
                hits.append(m.group().strip())
        return hits

    def is_modification_allowed(self, file_path: str) -> Tuple[bool, str]:
        is_protected, area = _file_in_protected_area(file_path)
        if is_protected and area is not None:
            return False, f"File is in protected area: {area.value}"
        return True, "modification_allowed"

    def get_violation_history(self) -> list[SecurityViolation]:
        with self._lock:
            return list(self._violations)

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock_class:
            if cls._instance is not None:
                cls._instance._violations.clear()
                cls._instance = None
