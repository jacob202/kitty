"""Typed error hierarchy for the gateway.

Lane D: instead of every route raising ad-hoc ``HTTPException`` or
string ``RuntimeError`` messages, surface failures through named
classes that the route layer can translate to a consistent
HTTP shape. The contract is:

- Every error that should be shown to the caller (or logged in a
  structured way) is a ``KittyError`` subclass.
- The ``status_code`` is the HTTP status the gateway should return.
- The ``code`` is a short machine-readable token the frontend can
  switch on (e.g. ``storage.not_found``).
- The ``message`` is human-readable.

Anything that is genuinely unexpected (a programming bug, a
third-party library failure) should still raise the underlying
exception. ``KittyError`` is for the cases where the gateway knows
what went wrong and can describe it cleanly.
"""

from __future__ import annotations

from typing import Any


class KittyError(Exception):
    """Base class for every error the gateway describes on purpose."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body


class ConfigError(KittyError):
    """A required config value is missing or invalid at request time."""

    status_code = 500
    code = "config_error"


class StorageNotFound(KittyError):
    """A storage lookup returned no record."""

    status_code = 404
    code = "storage.not_found"


class StorageConflict(KittyError):
    """A storage write would violate a uniqueness or state constraint."""

    status_code = 409
    code = "storage.conflict"


class StorageUnavailable(KittyError):
    """A storage backend is unreachable, locked, or returned an error."""

    status_code = 503
    code = "storage.unavailable"


class ProviderError(KittyError):
    """An LLM provider returned an error or unreachable response."""

    status_code = 502
    code = "provider.error"


class ProviderTimeout(KittyError):
    """An LLM provider timed out."""

    status_code = 504
    code = "provider.timeout"


class AuthError(KittyError):
    """Authentication or authorization failed."""

    status_code = 401
    code = "auth.unauthorized"


class AuthForbidden(KittyError):
    """The caller is authenticated but lacks permission."""

    status_code = 403
    code = "auth.forbidden"


class ValidationError(KittyError):
    """A request failed the gateway's input validation."""

    status_code = 400
    code = "validation_error"
