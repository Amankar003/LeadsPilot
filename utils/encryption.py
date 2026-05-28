"""
utils/encryption.py — Lightweight Fernet encryption wrapper for MailForge sender passwords.
"""
import os
import base64
from cryptography.fernet import Fernet, InvalidToken
from utils.logging_utils import get_logger

logger = get_logger(__name__)

_fernet_instance = None


def _get_fernet() -> Fernet:
    """Lazily initialises and caches a Fernet instance using the env key."""
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    key = os.getenv("MAILFORGE_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "MAILFORGE_ENCRYPTION_KEY is not set in .env. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    _fernet_instance = Fernet(key.encode())
    return _fernet_instance


def encrypt_value(plain_text: str) -> str:
    """Encrypt a plain-text string and return a URL-safe base64 token."""
    if not plain_text:
        return ""
    f = _get_fernet()
    return f.encrypt(plain_text.encode()).decode()


def decrypt_value(cipher_text: str) -> str:
    """Decrypt a Fernet token back to plain-text."""
    if not cipher_text:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(cipher_text.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt value — invalid token or wrong key.")
        return ""
