from django.contrib import admin
from .models import SurveyResponse, FieldAnswer


class FieldAnswerInline(admin.TabularInline):
    model = FieldAnswer
    extra = 0
    readonly_fields = ('field', 'display_value', 'answered_at')
    can_delete = False
    
    def display_value(self, obj):
        """Display value or [ENCRYPTED] for sensitive fields."""
        if obj.field.is_sensitive and obj.encrypted_value:
            return '[ENCRYPTED]'
        return obj.value or '-'
    display_value.short_description = 'Value'  # type: ignore[attr-defined]


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ('survey', 'respondent', 'status', 'started_at', 'completed_at')
    list_filter = ('status', 'survey', 'started_at')
    search_fields = ('survey__title', 'respondent__email', 'session_token')
    date_hierarchy = 'started_at'
    readonly_fields = ('started_at', 'completed_at')
    inlines = [FieldAnswerInline]


@admin.register(FieldAnswer)
class FieldAnswerAdmin(admin.ModelAdmin):
    list_display = ('field', 'response', 'display_value', 'answered_at')
    list_filter = ('response__survey', 'field__field_type', 'field__is_sensitive')
    search_fields = ('field__label', 'value')
    readonly_fields = ('answered_at', 'encrypted_value', 'display_value')
    
    def display_value(self, obj):
        """Display value or [ENCRYPTED] for sensitive fields."""
        if obj.field.is_sensitive and obj.encrypted_value:
            return '[ENCRYPTED]'
        return obj.value or '-'
    display_value.short_description = 'Value'  # type: ignore[attr-defined]
