from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import hashlib
import secrets
import uuid


@dataclass
class ApiKey:
    tenant_id: str
    name: str
    key_hash: str
    scopes: list[str]
    api_key_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key_prefix: str = ""
    expires_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = None
    created_by: Optional[str] = None

    VALID_SCOPES = frozenset([
        "documents:write",
        "documents:read",
        "search:read",
        "admin:keys",
    ])

    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        raw_key = secrets.token_urlsafe(32)
        full_key = f"irpf_ak_{raw_key}"
        key_prefix = full_key[:16]
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        return full_key, key_prefix, key_hash

    @staticmethod
    def hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def create(
        cls,
        tenant_id: str,
        name: str,
        scopes: list[str],
        expires_at: Optional[datetime] = None,
        created_by: Optional[str] = None,
    ) -> tuple["ApiKey", str]:
        invalid_scopes = set(scopes) - cls.VALID_SCOPES
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {invalid_scopes}")

        full_key, key_prefix, key_hash = cls.generate_key()

        api_key = cls(
            tenant_id=tenant_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=scopes,
            expires_at=expires_at,
            created_by=created_by,
        )

        return api_key, full_key

    def is_valid(self) -> bool:
        if not self.is_active:
            return False

        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False

        return True

    def has_scope(self, required_scope: str) -> bool:
        return required_scope in self.scopes

    def has_any_scope(self, required_scopes: list[str]) -> bool:
        return bool(set(self.scopes) & set(required_scopes))

    def record_usage(self) -> None:
        self.last_used_at = datetime.now(timezone.utc)

    def revoke(self) -> None:
        self.is_active = False
