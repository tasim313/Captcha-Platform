"""
Encryption service for securing sensitive data.
Uses Fernet symmetric encryption from the cryptography library.
"""

import base64
import hashlib
from typing import Optional, Union
from functools import wraps

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from structlog import get_logger

logger = get_logger(__name__)


class EncryptionService:
    """
    Centralized encryption service for sensitive data.
    
    Features:
    - Fernet symmetric encryption
    - Key derivation from master key
    - Automatic key caching
    - Type-safe encrypt/decrypt operations
    """
    
    _instance: Optional['EncryptionService'] = None
    _fernet: Optional[Fernet] = None
    
    def __new__(cls) -> 'EncryptionService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if self._fernet is None:
            self._initialize_fernet()
    
    def _initialize_fernet(self) -> None:
        """Initialize Fernet cipher from configured encryption key."""
        encryption_key = settings.PLATFORM_CONFIG.get('encryption', {}).get('key', '')
        
        if not encryption_key:
            raise ImproperlyConfigured(
                "ENCRYPTION_KEY must be set in environment variables. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        
        try:
            # Validate key format
            if not encryption_key.startswith('gAAAA'):
                # Derive proper Fernet key from custom key
                encryption_key = self._derive_fernet_key(encryption_key)
            
            self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            logger.info("encryption_service_initialized")
        except Exception as e:
            raise ImproperlyConfigured(f"Failed to initialize encryption: {e}")
    
    def _derive_fernet_key(self, master_key: str) -> str:
        """Derive a valid Fernet key from a custom master key."""
        salt = b'captcha_platform_salt_v1'  # Static salt for deterministic derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return key.decode()
    
    def encrypt(self, plaintext: Union[str, bytes]) -> str:
        """
        Encrypt plaintext value.
        
        Args:
            plaintext: Value to encrypt (string or bytes)
            
        Returns:
            Encrypted string (Fernet token)
            
        Raises:
            ValueError: If plaintext is empty
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty value")
        
        try:
            if isinstance(plaintext, str):
                plaintext = plaintext.encode('utf-8')
            
            encrypted = self._fernet.encrypt(plaintext)
            return encrypted.decode('utf-8')
        except Exception as e:
            logger.error("encryption_failed", error=str(e))
            raise EncryptionError(f"Failed to encrypt value: {e}")
    
    def decrypt(self, ciphertext: Union[str, bytes]) -> str:
        """
        Decrypt ciphertext value.
        
        Args:
            ciphertext: Encrypted Fernet token
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            ValueError: If ciphertext is empty
            DecryptionError: If decryption fails
        """
        if not ciphertext:
            raise ValueError("Cannot decrypt empty value")
        
        try:
            if isinstance(ciphertext, str):
                ciphertext = ciphertext.encode('utf-8')
            
            decrypted = self._fernet.decrypt(ciphertext)
            return decrypted.decode('utf-8')
        except InvalidToken:
            logger.error("decryption_failed_invalid_token")
            raise DecryptionError("Invalid encryption token - may be corrupted or wrong key")
        except Exception as e:
            logger.error("decryption_failed", error=str(e))
            raise DecryptionError(f"Failed to decrypt value: {e}")
    
    def is_encrypted(self, value: str) -> bool:
        """Check if a value appears to be encrypted (Fernet token format)."""
        if not value or len(value) < 50:
            return False
        try:
            # Fernet tokens are base64 encoded and start with specific bytes
            decoded = base64.urlsafe_b64decode(value)
            return decoded[0:1] == b'\x80'
        except Exception:
            return False
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None
        cls._fernet = None


class EncryptionError(Exception):
    """Raised when encryption fails."""
    pass


class DecryptionError(Exception):
    """Raised when decryption fails."""
    pass


# Convenience functions
def encrypt_value(value: Union[str, bytes]) -> str:
    """Encrypt a value using the singleton EncryptionService."""
    return EncryptionService().encrypt(value)


def decrypt_value(value: Union[str, bytes]) -> str:
    """Decrypt a value using the singleton EncryptionService."""
    return EncryptionService().decrypt(value)


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive value for display, showing only first/last characters.
    
    Args:
        value: Value to mask
        visible_chars: Number of characters to show at start and end
        
    Returns:
        Masked string like 'abcd...xyz'
    """
    if not value or len(value) <= visible_chars * 2:
        return '****'
    return f"{value[:visible_chars]}{'*' * (len(value) - visible_chars * 2)}{value[-visible_chars:]}"