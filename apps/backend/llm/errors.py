"""Shared LLM errors.

Roadmap: used by provider config resolution so callers can distinguish
"configuration" vs "authentication" problems.

Epic 3 / Task 3.2 expects missing OpenAI key to raise AuthError.
"""


class LLMError(Exception):
    """Base error for LLM subsystem."""


class ConfigError(LLMError, ValueError):
    """Invalid or missing configuration (non-auth)."""


class AuthError(LLMError):
    """Authentication/credential problem (missing key, invalid token, etc.)."""
