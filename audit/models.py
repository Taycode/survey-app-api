import uuid
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """
    Tracks all user actions for compliance and security.
    Records actions like survey creation, edits, data access, and exports.
    """
    class Action(models.TextChoices):
        CREATED = 'created', 'Created'
        UPDATED = 'updated', 'Updated'
        DELETED = 'deleted', 'Deleted'
        VIEWED = 'viewed', 'Viewed'
        EXPORTED = 'exported', 'Exported'

    class ResourceType(models.TextChoices):
        SURVEY = 'survey', 'Survey'
        SECTION = 'section', 'Section'
        FIELD = 'field', 'Field'
        RESPONSE = 'response', 'Response'
        USER = 'user', 'User'
        ROLE = 'role', 'Role'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
        help_text='User who performed the action'
    )
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        db_index=True
    )
    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.choices
    )
    resource_id = models.UUIDField(
        help_text='ID of the affected resource'
    )
    changes = models.JSONField(
        blank=True,
        null=True,
        help_text='Before/after values for updates. Format: {"before": {...}, "after": {...}}'
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        help_text='Client IP address'
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text='Client user agent'
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else 'System'
        return f'{user_str} {self.action} {self.resource_type} {self.resource_id}'
