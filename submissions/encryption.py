"""
Encryption service for sensitive field answers.

Uses AES-256-GCM encryption for secure storage of sensitive data.
"""
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class EncryptionError(Exception):
    """Raised when encryption fails."""
    pass


class DecryptionError(Exception):
    """Raised when decryption fails."""
    pass


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive field values.
    
    Uses AES-256-GCM (Galois/Counter Mode) for authenticated encryption.
    """
    
    @staticmethod
    def _get_encryption_key() -> bytes:
        """
        Get encryption key from settings.
        
        Returns:
            bytes: 32-byte encryption key
            
        Raises:
            ImproperlyConfigured: If key is missing or invalid length
        """
        key_str = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
        
        if not key_str:
            raise ImproperlyConfigured(
                'FIELD_ENCRYPTION_KEY must be set in environment variables. '
                'Generate a key using: python manage.py generate_encryption_key'
            )
        
        # Try to decode base64 first (if key is base64 encoded)
        try:
            key = base64.b64decode(key_str)
        except Exception:
            # If not base64, try using the string directly (must be exactly 32 bytes)
            key = key_str.encode('utf-8')
        
        if len(key) != 32:
            raise ImproperlyConfigured(
                f'FIELD_ENCRYPTION_KEY must be exactly 32 bytes (256 bits). '
                f'Current length: {len(key)} bytes. '
                f'Generate a key using: python manage.py generate_encryption_key'
            )
        
        return key
    
    @staticmethod
    def encrypt(plaintext: str) -> bytes:
        """
        Encrypt plaintext using AES-256-GCM.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            bytes: Encrypted data (nonce + ciphertext + auth_tag)
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty plaintext")
        
        try:
            key = EncryptionService._get_encryption_key()
            aesgcm = AESGCM(key)
            
            # Generate random 12-byte nonce (required for GCM)
            nonce = secrets.token_bytes(12)
            
            # Encrypt (returns ciphertext + auth_tag)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            
            # Format: nonce (12 bytes) + ciphertext + auth_tag (16 bytes)
            encrypted_data = nonce + ciphertext
            
            return encrypted_data
        except ImproperlyConfigured:
            raise
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {str(e)}")
    
    @staticmethod
    def decrypt(encrypted_data: bytes) -> str:
        """
        Decrypt encrypted data using AES-256-GCM.
        
        Args:
            encrypted_data: Encrypted data (nonce + ciphertext + auth_tag)
            
        Returns:
            str: Decrypted plaintext
            
        Raises:
            DecryptionError: If decryption fails (invalid data, tampering, etc.)
        """
        if not encrypted_data:
            raise DecryptionError("Cannot decrypt empty data")
        
        if len(encrypted_data) < 28:  # Minimum: 12 bytes nonce + 16 bytes auth_tag
            raise DecryptionError("Encrypted data too short")
        
        try:
            key = EncryptionService._get_encryption_key()
            aesgcm = AESGCM(key)
            
            # Extract nonce (first 12 bytes) and ciphertext (rest)
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            # Decrypt (includes auth_tag verification)
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext_bytes.decode('utf-8')
        except ImproperlyConfigured:
            raise
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {str(e)}")
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new encryption key (base64 encoded).
        
        Returns:
            str: Base64-encoded 32-byte key suitable for environment variable
            
        Example:
            >>> key = EncryptionService.generate_key()
            >>> # Use in .env: FIELD_ENCRYPTION_KEY={key}
        """
        key_bytes = secrets.token_bytes(32)
        return base64.b64encode(key_bytes).decode('utf-8')

