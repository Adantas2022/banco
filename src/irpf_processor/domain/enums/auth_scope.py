from enum import Enum


class AuthScope(str, Enum):
    DOCUMENTS_WRITE = "documents:write"
    DOCUMENTS_READ = "documents:read"
    SEARCH_READ = "search:read"
    ADMIN_KEYS = "admin:keys"

    @classmethod
    def all_scopes(cls) -> list[str]:
        return [scope.value for scope in cls]

    @classmethod
    def default_scopes(cls) -> list[str]:
        return [
            cls.DOCUMENTS_WRITE.value,
            cls.DOCUMENTS_READ.value,
            cls.SEARCH_READ.value,
        ]
