import uuid
from django.db import models
from django.conf import settings


class Survey(models.Model):
    """
    The parent entity representing a complete survey.
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        CLOSED = 'closed', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='surveys'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'surveys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_by']),
        ]

    def __str__(self):
        return self.title


class Section(models.Model):
    """
    Logical groupings within a survey.
    Each survey contains multiple sections.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='sections'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sections'
        ordering = ['order']
        unique_together = ['survey', 'order']
        indexes = [
            models.Index(fields=['survey', 'order']),
        ]

    def __str__(self):
        return f'{self.survey.title} - {self.title}'


class Field(models.Model):
    """
    Individual questions/inputs within a section.
    Supports multiple field types with configurable options.
    """
    class FieldType(models.TextChoices):
        TEXT = 'text', 'Text'
        NUMBER = 'number', 'Number'
        DATE = 'date', 'Date'
        DROPDOWN = 'dropdown', 'Dropdown'
        CHECKBOX = 'checkbox', 'Checkbox'
        RADIO = 'radio', 'Radio'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='fields'
    )
    label = models.CharField(max_length=500)
    field_type = models.CharField(
        max_length=20,
        choices=FieldType.choices
    )
    is_required = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(
        default=False,
        help_text='If True, value will be encrypted when stored'
    )
    order = models.PositiveIntegerField()
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional configuration (placeholder, min/max, etc.)'
    )
    # Quick reference for dependency checking
    has_dependencies = models.BooleanField(
        default=False,
        help_text='True if this field options depend on another field'
    )

    class Meta:
        db_table = 'fields'
        ordering = ['order']
        indexes = [
            models.Index(fields=['section', 'order']),
        ]

    def __str__(self):
        return f'{self.section.title} - {self.label}'


class FieldOption(models.Model):
    """
    Predefined options for dropdown, checkbox, and radio fields.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name='options'
    )
    label = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    order = models.PositiveIntegerField()

    class Meta:
        db_table = 'field_options'
        ordering = ['order']
        unique_together = ['field', 'value']
        indexes = [
            models.Index(fields=['field', 'order']),
        ]

    def __str__(self):
        return f'{self.field.label} - {self.label}'


class ConditionalRule(models.Model):
    """
    Rules that control visibility of sections or fields based on previous answers.
    Example: Show Section 3 only if Field 'employed' equals 'yes'
    """
    class TargetType(models.TextChoices):
        SECTION = 'section', 'Section'
        FIELD = 'field', 'Field'

    class Operator(models.TextChoices):
        EQUALS = 'equals', 'Equals'
        NOT_EQUALS = 'not_equals', 'Not Equals'
        GREATER_THAN = 'greater_than', 'Greater Than'
        LESS_THAN = 'less_than', 'Less Than'
        CONTAINS = 'contains', 'Contains'
        IN = 'in', 'In'
        IS_EMPTY = 'is_empty', 'Is Empty'
        IS_NOT_EMPTY = 'is_not_empty', 'Is Not Empty'

    class Action(models.TextChoices):
        SHOW = 'show', 'Show'
        HIDE = 'hide', 'Hide'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(
        max_length=20,
        choices=TargetType.choices
    )
    target_id = models.UUIDField(
        help_text='ID of the section or field to show/hide'
    )
    source_field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name='triggers_rules',
        help_text='The field whose answer triggers this rule'
    )
    operator = models.CharField(
        max_length=20,
        choices=Operator.choices
    )
    value = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Value to compare against (null for is_empty/is_not_empty)'
    )
    action = models.CharField(
        max_length=10,
        choices=Action.choices,
        default=Action.SHOW
    )

    class Meta:
        db_table = 'conditional_rules'
        indexes = [
            models.Index(fields=['target_type', 'target_id']),
            models.Index(fields=['source_field']),
        ]

    def __str__(self):
        return f'{self.action} {self.target_type} if {self.source_field.label} {self.operator} {self.value}'


class FieldDependency(models.Model):
    """
    Rules that change the available options in a field based on another field's answer.
    Example: When 'country' = 'USA', show American departments in the 'department' field.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dependent_field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name='depends_on_rules',
        help_text='The field whose options change'
    )
    source_field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name='controls_options_for',
        help_text='The field that triggers the change'
    )
    source_value = models.CharField(
        max_length=255,
        help_text='When source field equals this value...'
    )
    dependent_options = models.JSONField(
        help_text='...show these options. Format: [{"label": "...", "value": "..."}]'
    )

    class Meta:
        db_table = 'field_dependencies'
        indexes = [
            models.Index(fields=['dependent_field']),
            models.Index(fields=['source_field', 'source_value']),
        ]

    def __str__(self):
        return f'{self.dependent_field.label} depends on {self.source_field.label}={self.source_value}'
