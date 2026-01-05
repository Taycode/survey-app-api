from django.forms.models import model_to_dict
from .models import AuditLog

class AuditLogMixin:
    """
    Mixin to automatically log Create, Update, and Delete actions in ViewSets.
    Assumes the ViewSet has `get_serializer`, `get_object`, and `request`.
    """

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _get_user_agent(self, request):
        return request.META.get('HTTP_USER_AGENT', '')[:500]

    def _log_action(self, action, instance, changes=None):
        user = self.request.user if self.request.user.is_authenticated else None
        
        # Determine resource type
        # Simple mapping based on model name, could be more robust
        model_name = instance._meta.model_name.lower()
        
        # Map model names to ResourceType choices if needed, or stick to generic string
        # The model uses TextChoices, so we try to match:
        resource_type_map = {
            'survey': AuditLog.ResourceType.SURVEY,
            'section': AuditLog.ResourceType.SECTION,
            'field': AuditLog.ResourceType.FIELD,
            'surveyresponse': AuditLog.ResourceType.RESPONSE,
            'user': AuditLog.ResourceType.USER,
        }
        resource_type = resource_type_map.get(model_name, model_name[:20])

        AuditLog.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=instance.pk,
            changes=changes,
            ip_address=self._get_client_ip(self.request),
            user_agent=self._get_user_agent(self.request)
        )

    def perform_create(self, serializer):
        instance = serializer.save()
        self._log_action(AuditLog.Action.CREATED, instance)

    def perform_update(self, serializer):
        # Capture state before update
        instance = self.get_object()
        
        # Simple dict conversion for diff
        # Note: model_to_dict doesn't serialize many-to-many or file fields well by default
        before_state = model_to_dict(instance)
        
        super().perform_update(serializer)
        
        # Capture state after update
        instance.refresh_from_db()
        after_state = model_to_dict(instance)
        
        # Calculate diff
        changes = {}
        for key, value in after_state.items():
            if key in before_state and before_state[key] != value:
                # Convert UUIDs/dates to strings for JSON serialization
                old_val = str(before_state[key]) if before_state[key] is not None else None
                new_val = str(value) if value is not None else None
                changes[key] = {'old': old_val, 'new': new_val}
        
        if changes:
            self._log_action(AuditLog.Action.UPDATED, instance, changes)

    def perform_destroy(self, instance):
        # Log before deleting, as we need the ID
        self._log_action(AuditLog.Action.DELETED, instance)
        super().perform_destroy(instance)
