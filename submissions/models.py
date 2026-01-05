import uuid
from django.db import models
from django.conf import settings
from surveys.models import Survey, Section, Field


class SurveyResponse(models.Model):
    """
    A single user's submission (complete or partial) to a survey.
    Supports resumable sessions for partial responses.
    """
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='survey_responses',
        help_text='Authenticated user (if logged in)'
    )
    session_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text='For anonymous/resumable sessions'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text='For resuming partial responses'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'survey_responses'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['survey']),
            models.Index(fields=['respondent']),
            models.Index(fields=['session_token']),
            models.Index(fields=['status']),
        ]
        constraints = [
            # At least one of respondent or session_token must be set
            models.CheckConstraint(
                condition=~models.Q(respondent__isnull=True, session_token__isnull=True),
                name='response_has_identifier'
            )
        ]

    def __str__(self):
        identifier = self.respondent.email if self.respondent else (self.session_token[:8] if self.session_token else 'unknown')
        return f'{self.survey.title} - {identifier}'


class FieldAnswer(models.Model):
    """
    Individual answers to fields within a response.
    Supports encryption for sensitive fields.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.ForeignKey(
        SurveyResponse,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    # For non-sensitive fields
    value = models.TextField(
        blank=True,
        null=True,
        help_text='Plaintext value (for non-sensitive fields)'
    )
    # For sensitive fields (encrypted)
    encrypted_value = models.BinaryField(
        blank=True,
        null=True,
        help_text='Encrypted value (for sensitive fields)'
    )
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'field_answers'
        unique_together = ['response', 'field']
        indexes = [
            models.Index(fields=['response']),
            models.Index(fields=['field']),
        ]

    def __str__(self):
        return f'{self.field.label}: {self.value or "[encrypted]"}'

    def _encrypt_value(self, plaintext: str) -> bytes:
        """
        Encrypt a plaintext value.
        
        Args:
            plaintext: String value to encrypt
            
        Returns:
            bytes: Encrypted data
        """
        from .encryption import EncryptionService
        return EncryptionService.encrypt(plaintext)
    
    def _decrypt_value(self, encrypted_data: bytes) -> str:
        """
        Decrypt an encrypted value.
        
        Args:
            encrypted_data: Encrypted bytes
            
        Returns:
            str: Decrypted plaintext
        """
        from .encryption import EncryptionService
        return EncryptionService.decrypt(encrypted_data)
    
    @property
    def decrypted_value(self) -> str:
        """
        Get decrypted value for sensitive fields.
        
        Returns:
            str: Decrypted value if encrypted, otherwise plaintext value
        """
        if self.encrypted_value:
            return self._decrypt_value(self.encrypted_value)
        return self.value or ''
    
    def save(self, *args, **kwargs):
        """
        Override save to automatically encrypt sensitive fields.
        
        If field.is_sensitive is True and value is provided:
        - Encrypts value and stores in encrypted_value
        - Clears value field
        
        If field.is_sensitive is False:
        - Stores value in plaintext
        - Clears encrypted_value
        """
        # Only encrypt if field is loaded and is_sensitive is True
        if hasattr(self, 'field') and self.field and self.field.is_sensitive:
            if self.value:
                # Encrypt and store in encrypted_value
                self.encrypted_value = self._encrypt_value(self.value)
                self.value = None  # Clear plaintext
            elif self.encrypted_value and not self.value:
                # Already encrypted, keep as is
                pass
        elif hasattr(self, 'field') and self.field and not self.field.is_sensitive:
            # Non-sensitive field: store plaintext, clear encrypted
            if self.value:
                self.encrypted_value = None
        
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        # Ensure exactly one of value or encrypted_value is set
        if self.value and self.encrypted_value:
            raise ValidationError('Cannot have both value and encrypted_value')
        if not self.value and not self.encrypted_value:
            raise ValidationError('Either value or encrypted_value must be set')


class Invitation(models.Model):
    """
    Tracks survey invitations sent to recipients.
    Used for audit trail of batch invitation campaigns.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    email = models.EmailField(
        db_index=True,
        help_text='Email address invitation was sent to'
    )
    sent_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the invitation email was sent'
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_invitations',
        help_text='User who triggered the invitation'
    )

    class Meta:
        db_table = 'invitations'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['survey']),
            models.Index(fields=['email']),
            models.Index(fields=['sent_at']),
        ]

    def __str__(self):
        return f'{self.survey.title} -> {self.email}'
