from rest_framework import serializers
from .models import SurveyResponse, FieldAnswer


class FieldAnswerSerializer(serializers.Serializer):
    """
    Serializer for a single field answer.
    
    **Fields**:
    - `field_id` (UUID, required): The ID of the field being answered.
    - `value` (JSON, required): The answer value. Format depends on field type:
      - Text: `"text answer"`
      - Number: `42` or `"42"`
      - Date: `"2024-01-15"` (ISO format)
      - Radio/Dropdown: `"option_value"`
      - Checkbox: `["option1", "option2"]` (array of selected values)
    """
    field_id = serializers.UUIDField(help_text="UUID of the field being answered")
    value = serializers.JSONField(help_text="Answer value (format depends on field type)")


class SubmitSectionSerializer(serializers.Serializer):
    """
    Request serializer for submitting answers for a section.
    
    **Fields**:
    - `section_id` (UUID, required): The ID of the section being submitted.
    - `answers` (array, required): List of field answers. Must include all required visible fields.
    
    **Validation**:
    - Section must belong to the survey
    - Section must be visible (conditional logic)
    - All required fields must have answers
    - Answers must match field types and constraints
    """
    section_id = serializers.UUIDField(help_text="UUID of the section to submit")
    answers = FieldAnswerSerializer(many=True, help_text="List of field answers for this section")


class SubmissionStateSerializer(serializers.ModelSerializer):
    """Serializer for current submission state."""
    class Meta:
        model = SurveyResponse
        fields = ['id', 'status', 'last_section', 'completed_at']


class FinishSurveyResponseSerializer(serializers.Serializer):
    """Response serializer for finish survey endpoint."""
    message = serializers.CharField()
    completed_at = serializers.DateTimeField()


class VisibleFieldSerializer(serializers.Serializer):
    """
    Serializer for visible field information.
    
    Returned in `visible_sections` to help frontend render forms dynamically.
    """
    field_id = serializers.UUIDField(help_text="UUID of the field")
    label = serializers.CharField(help_text="Field label/question text")
    field_type = serializers.CharField(help_text="Field type: TEXT, NUMBER, DATE, DROPDOWN, RADIO, CHECKBOX")
    is_required = serializers.BooleanField(help_text="Whether this field is required")
    options = serializers.ListField(child=serializers.DictField(), required=False, help_text="Available options (for dropdown/radio/checkbox)")


class VisibleSectionSerializer(serializers.Serializer):
    """
    Serializer for visible section information.
    
    Returned in `visible_sections` to help frontend render sections dynamically.
    """
    section_id = serializers.UUIDField(help_text="UUID of the section")
    title = serializers.CharField(help_text="Section title")
    order = serializers.IntegerField(help_text="Section order (1-based)")
    visible_fields = VisibleFieldSerializer(many=True, help_text="List of visible fields in this section")


class ProgressSerializer(serializers.Serializer):
    """Serializer for survey progress information."""
    sections_completed = serializers.IntegerField(help_text="Number of sections completed")
    total_sections = serializers.IntegerField(help_text="Total number of visible sections")
    sections_remaining = serializers.IntegerField(help_text="Number of sections remaining")
    percentage = serializers.FloatField(help_text="Completion percentage (0-100)")


class FieldSerializer(serializers.Serializer):
    """Serializer for field information in section responses."""
    field_id = serializers.UUIDField(help_text="UUID of the field")
    label = serializers.CharField(help_text="Field label/question text")
    field_type = serializers.CharField(help_text="Field type: TEXT, NUMBER, DATE, DROPDOWN, RADIO, CHECKBOX")
    is_required = serializers.BooleanField(help_text="Whether this field is required")
    current_value = serializers.CharField(required=False, allow_null=True, help_text="Current answer value (for pre-filled forms)")
    options = serializers.ListField(child=serializers.DictField(), required=False, help_text="Available options (for dropdown/radio/checkbox)")


class SectionSerializer(serializers.Serializer):
    """Serializer for section information."""
    section_id = serializers.UUIDField(help_text="UUID of the section")
    title = serializers.CharField(help_text="Section title")
    order = serializers.IntegerField(help_text="Section order (1-based)")
    fields = FieldSerializer(many=True, help_text="List of fields in this section")


class CurrentSectionResponseSerializer(serializers.Serializer):
    """Response serializer for get current section endpoint."""
    current_section = SectionSerializer(allow_null=True, help_text="Current section to complete (null if survey is complete)")
    is_complete = serializers.BooleanField(help_text="Whether the survey is complete")
    progress = ProgressSerializer(help_text="Survey progress information")


class SectionResponseSerializer(serializers.Serializer):
    """Response serializer for get specific section endpoint (navigation)."""
    section = SectionSerializer(help_text="Section information with pre-filled answers")
    is_editable = serializers.BooleanField(help_text="Whether this section can be edited")
    progress = ProgressSerializer(help_text="Survey progress information")


class SubmitSectionResponseSerializer(serializers.Serializer):
    """
    Response serializer for submit section endpoint.
    
    **Fields**:
    - `status` (string): "success" if answers saved, "error" if validation failed.
    - `message` (string): Human-readable message.
    - `is_complete` (boolean): Whether the survey is complete after this submission.
    - `progress` (object): Progress information.
    """
    status = serializers.CharField(help_text="Status: 'success' or 'error'")
    message = serializers.CharField(help_text="Human-readable message")
    is_complete = serializers.BooleanField(help_text="Whether survey is complete")
    progress = ProgressSerializer(help_text="Survey progress information")


# ============ RESPONSE VIEWING SERIALIZERS ============

class SurveyBasicSerializer(serializers.Serializer):
    """Basic survey information for nested serialization."""
    id = serializers.UUIDField(help_text="Survey UUID")
    title = serializers.CharField(help_text="Survey title")
    description = serializers.CharField(help_text="Survey description", required=False, allow_blank=True, allow_null=True)


class RespondentSerializer(serializers.Serializer):
    """Respondent information (if authenticated)."""
    id = serializers.UUIDField(help_text="User UUID")
    email = serializers.EmailField(help_text="User email")


class FieldAnswerDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for field answer details in response viewing.
    
    Automatically decrypts sensitive fields for authorized users.
    """
    field_id = serializers.UUIDField(source='field.id', read_only=True, help_text="UUID of the field")
    field_label = serializers.CharField(source='field.label', read_only=True, help_text="Field label/question text")
    field_type = serializers.CharField(source='field.field_type', read_only=True, help_text="Field type: TEXT, NUMBER, DATE, DROPDOWN, RADIO, CHECKBOX")
    value = serializers.SerializerMethodField(help_text="Answer value (decrypted if sensitive)")
    is_sensitive = serializers.SerializerMethodField(help_text="Whether this field is sensitive/encrypted")
    
    class Meta:
        model = FieldAnswer
        fields = ['field_id', 'field_label', 'field_type', 'value', 'is_sensitive', 'answered_at']
    
    def get_value(self, obj):
        """Automatically decrypt if sensitive."""
        return obj.decrypted_value
    
    def get_is_sensitive(self, obj):
        """Check if field is sensitive."""
        return obj.field.is_sensitive


class SurveyResponseDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed survey response view.
    
    Includes all answers with decrypted sensitive fields.
    """
    survey = serializers.SerializerMethodField(help_text="Survey information")
    respondent = serializers.SerializerMethodField(help_text="Respondent information (if authenticated)", allow_null=True)
    answers = serializers.SerializerMethodField(help_text="List of all answers with decrypted values")
    
    class Meta:
        model = SurveyResponse
        fields = ['id', 'survey', 'respondent', 'status', 'started_at', 'completed_at', 'answers', 'session_token']
    
    def get_survey(self, obj):
        """Get survey information."""
        return SurveyBasicSerializer({
            'id': obj.survey.id,
            'title': obj.survey.title,
            'description': obj.survey.description
        }).data
    
    def get_respondent(self, obj):
        """Get respondent information."""
        if obj.respondent:
            return RespondentSerializer({
                'id': obj.respondent.id,
                'email': obj.respondent.email
            }).data
        return None
    
    def get_answers(self, obj):
        """Get all answers with decrypted values."""
        answers = obj.answers.select_related('field').order_by('field__section__order', 'field__order')
        return FieldAnswerDetailSerializer(answers, many=True).data


class SurveyResponseListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing survey responses.
    
    Lightweight serializer for list views with summary information.
    """
    survey = serializers.SerializerMethodField(help_text="Survey information")
    respondent = serializers.SerializerMethodField(help_text="Respondent information (if authenticated)", allow_null=True)
    answers_count = serializers.SerializerMethodField(help_text="Number of answers submitted")
    progress = serializers.SerializerMethodField(help_text="Completion percentage (0-100)")
    
    class Meta:
        model = SurveyResponse
        fields = ['id', 'survey', 'respondent', 'status', 'started_at', 'completed_at', 'answers_count', 'progress']
    
    def get_survey(self, obj):
        """Get survey information."""
        return SurveyBasicSerializer({
            'id': obj.survey.id,
            'title': obj.survey.title,
            'description': obj.survey.description
        }).data
    
    def get_respondent(self, obj):
        """Get respondent information."""
        if obj.respondent:
            return RespondentSerializer({
                'id': obj.respondent.id,
                'email': obj.respondent.email
            }).data
        return None
    
    def get_answers_count(self, obj):
        """Get count of answers."""
        return obj.answers.count()
    
    def get_progress(self, obj):
        """Calculate completion progress."""
        from submissions.services import ConditionalLogicService
        service = ConditionalLogicService()
        progress = service.get_survey_progress(obj)
        return progress.get('percentage', 0)


# ============ ANALYTICS SERIALIZERS ============

class SurveyAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for survey-level analytics.
    
    Returns aggregated statistics for a single survey including
    response counts, completion rates, and average completion time.
    """
    survey_id = serializers.UUIDField(help_text="UUID of the survey")
    survey_title = serializers.CharField(help_text="Survey title")
    total_responses = serializers.IntegerField(help_text="Total number of responses (completed + in progress)")
    completed_responses = serializers.IntegerField(help_text="Number of completed responses")
    in_progress_responses = serializers.IntegerField(help_text="Number of in-progress responses")
    completion_rate = serializers.FloatField(help_text="Completion rate percentage (0-100)")
    average_completion_time_seconds = serializers.IntegerField(
        allow_null=True, 
        help_text="Average time to complete survey in seconds (null if no completions)"
    )
    last_response_at = serializers.DateTimeField(
        allow_null=True, 
        help_text="Timestamp of most recent response (null if no responses)"
    )


# ============ INVITATION SERIALIZERS ============

class InvitationRequestSerializer(serializers.Serializer):
    """
    Request serializer for sending batch survey invitations.
    
    **Fields**:
    - `emails` (array, required): List of email addresses to send invitations to.
    
    **Validation**:
    - At least one email must be provided
    - Maximum 1000 emails per request
    - All emails must be valid email format
    """
    emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1,
        max_length=1000,
        help_text="List of email addresses to send invitations to (max 1000)"
    )
    
    def validate_emails(self, value):
        """Remove duplicates and normalize to lowercase."""
        return list(set(email.lower() for email in value))


class InvitationResponseSerializer(serializers.Serializer):
    """
    Response serializer for batch invitation endpoint.
    
    Returned with 202 Accepted status when invitations are queued.
    """
    message = serializers.CharField(help_text="Status message")
    survey = serializers.CharField(help_text="Survey title")
    recipient_count = serializers.IntegerField(help_text="Number of recipients queued for invitation")
