import uuid
from rest_framework import viewsets, status, serializers, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import SurveyResponse, FieldAnswer
from .serializers import (
    SubmitSectionSerializer,
    FinishSurveyResponseSerializer,
    SubmitSectionResponseSerializer,
    CurrentSectionResponseSerializer,
    SectionResponseSerializer,
    SurveyResponseDetailSerializer,
    SurveyResponseListSerializer,
    SurveyAnalyticsSerializer,
    InvitationRequestSerializer,
    InvitationResponseSerializer,
)
from .services import ConditionalLogicService, AnalyticsService
from .tasks import export_responses_async, send_survey_invitations
from surveys.models import Survey, Section, Field
from users.permissions import CanViewResponses, CanExportResponses, CanViewAnalytics, CanPublishSurvey, user_has_permission
from audit.mixins import AuditLogMixin


class SubmissionViewSet(viewsets.GenericViewSet):
    """
    ViewSet for handling survey submissions (public/anonymous access).
    
    Flow:
    1. Start Survey -> Get session_token
    2. Submit Section -> Save answers using session_token
    3. Finish Survey -> Complete submission
    """
    authentication_classes = []  # No authentication for public survey submissions
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'submit_section':
            return SubmitSectionSerializer
        return serializers.Serializer

    @extend_schema(
        tags=["Survey Submission"],
        summary="Start a new survey session",
        description="""
        **Step 1: Initialize Survey Session**
        
        Creates a new survey response session for anonymous users. This endpoint:
        - Validates that the survey exists and is published
        - Generates a unique session token (UUID v4)
        - Creates a `SurveyResponse` record with `IN_PROGRESS` status
        - Captures IP address and user agent for analytics
        
        **Authentication**: None required (public endpoint)
        
        **URL Parameters**:
        - `survey_pk` (UUID): The ID of the survey to start. Survey must be published.
        
        **Next Steps**:
        1. Store the returned `session_token` securely
        2. Include it in the `X-Session-Token` header for all subsequent requests
        3. Call `GET /current-section/` to retrieve the first section to complete
        
        **Error Responses**:
        - `404`: Survey not found or not published
        
        **Example Request**:
        ```
        POST /api/v1/surveys/550e8400-e29b-41d4-a716-446655440000/submissions/start/
        ```
        
        **Example Response**:
        ```json
        {
          "session_token": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        }
        ```
        
        See `survey_submission_lifecycle.md` for complete flow documentation.
        """,
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'session_token': {
                        'type': 'string',
                        'format': 'uuid',
                        'description': 'Unique session token. Use in X-Session-Token header for all subsequent requests.'
                    }
                },
                'required': ['session_token']
            },
            404: {'description': 'Survey not found or not published'}
        }
    )
    @action(detail=False, methods=['post'], url_path='start')
    def start_survey(self, request, survey_pk=None):
        survey = get_object_or_404(Survey, id=survey_pk, status=Survey.Status.PUBLISHED)
        
        # Generate session token
        session_token = str(uuid.uuid4())
        
        # Create response record
        # Note: If user is authenticated, we could link it, but for now we treat as anonymous
        response = SurveyResponse.objects.create(
            survey=survey,
            session_token=session_token,
            status=SurveyResponse.Status.IN_PROGRESS,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        return Response({
            'session_token': session_token
        }, status=status.HTTP_201_CREATED)

    def _validate_answer(self, field, value):
        """
        Validate answer value against field type.
        Returns (is_valid, error_message).
        """
        if value is None or value == '':
            return True, None  # Empty values handled by is_required check

        if field.field_type == Field.FieldType.NUMBER:
            try:
                float(value)
            except (ValueError, TypeError):
                return False, f"Value '{value}' is not a valid number"
                
        elif field.field_type == Field.FieldType.DATE:
            # Simple assumption: value is ISO date string YYYY-MM-DD
            # In production, use dateparse
            pass 
            
        elif field.field_type in [Field.FieldType.DROPDOWN, Field.FieldType.RADIO]:
            # Check if value exists in options
            # This is an extra query, might want to optimize if many fields
            if not field.options.filter(value=value).exists():
                return False, f"Value '{value}' is not a valid option"
                
        return True, None

    @extend_schema(
        tags=["Survey Submission"],
        summary="Submit answers for a section",
        description="""
        **Step 2: Save Section Answers**
        
        Validates and saves answers for a specific section. This endpoint performs comprehensive validation:
        
        **Validation Layers**:
        1. **Session Validation**: Token exists and response is `IN_PROGRESS`
        2. **Section Validation**: Section belongs to the survey
        3. **Visibility Validation**: Section and fields are visible based on conditional logic
        4. **Required Field Validation**: All required visible fields have values
        5. **Type Validation**: Values match field types (number, date, text, etc.)
        6. **Option Validation**: Selected options exist for dropdown/radio fields
        7. **Dependency Validation**: Selected options are valid based on field dependencies
        
        **Authentication**: Session token required in `X-Session-Token` header
        
        **Answer Format**:
        - Text fields: `{"field_id": "uuid", "value": "text answer"}`
        - Number fields: `{"field_id": "uuid", "value": 42}`
        - Date fields: `{"field_id": "uuid", "value": "2024-01-15"}`
        - Radio/Dropdown: `{"field_id": "uuid", "value": "option_value"}`
        - Checkbox: `{"field_id": "uuid", "value": ["option1", "option2"]}`
        
        **Update Behavior**:
        - Uses `update_or_create()` - can submit same section multiple times
        - Existing answers are updated if section is resubmitted
        - Supports navigation/editing previous sections
        
        **Conditional Logic**:
        - After saving, conditional rules are re-evaluated
        - New sections may become visible based on answers
        - Field options may change based on dependencies
        
        **Response**:
        - `status`: "success" or "error"
        - `message`: Human-readable message
        - `is_complete`: Whether survey is complete after this submission
        - `progress`: Progress metrics (sections completed, total, remaining, percentage)
        
        **Error Responses**:
        - `400`: Validation errors (see `errors` object for field-level details)
        - `404`: Session or section not found
        
        **Example Request**:
        ```json
        {
          "section_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
          "answers": [
            {"field_id": "8c9e6679-7425-40de-944b-e07fc1f90ae7", "value": "Yes"},
            {"field_id": "9c9e6679-7425-40de-944b-e07fc1f90ae7", "value": 25}
          ]
        }
        ```
        
        **Example Success Response**:
        ```json
        {
          "status": "success",
          "message": "Section saved successfully",
          "is_complete": false,
          "progress": {
            "sections_completed": 2,
            "total_sections": 3,
            "sections_remaining": 1,
            "percentage": 66.67
          }
        }
        ```
        
        **Example Error Response**:
        ```json
        {
          "status": "error",
          "errors": {
            "8c9e6679-7425-40de-944b-e07fc1f90ae7": "This field is required.",
            "9c9e6679-7425-40de-944b-e07fc1f90ae7": "Value 'abc' is not a valid number."
          }
        }
        ```
        
        See `survey_submission_lifecycle.md` for detailed validation rules and conditional logic explanation.
        """,
        parameters=[
            OpenApiParameter(
                name='X-Session-Token',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.HEADER,
                required=True,
                description='Session token obtained from starting a survey. Required for all submission endpoints.'
            ),
        ],
        request=SubmitSectionSerializer,
        responses={
            200: SubmitSectionResponseSerializer,
            400: {
                'description': 'Validation error',
                'examples': {
                    'application/json': {
                        'status': 'error',
                        'errors': {
                            'field_id': 'This field is required.'
                        }
                    }
                }
            },
            404: {'description': 'Session or Section not found'}
        }
    )
    @action(detail=False, methods=['post'], url_path='submit-section')
    def submit_section(self, request):
        session_token = request.headers.get('X-Session-Token')
        if not session_token:
            return Response({'detail': 'X-Session-Token header required'}, status=status.HTTP_400_BAD_REQUEST)
            
        response = get_object_or_404(SurveyResponse, session_token=session_token, status=SurveyResponse.Status.IN_PROGRESS)

        serializer = SubmitSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        section = get_object_or_404(Section, id=serializer.validated_data['section_id'], survey=response.survey)
        
        # Validate and Process answers
        answers_data = serializer.validated_data['answers']
        validation_errors = {}
        
        # Conditional Logic Validation: Check if section/fields are visible and validate dependencies
        service = ConditionalLogicService()
        is_valid, conditional_errors = service.validate_submission(section, answers_data, response)
        
        if not is_valid:
            return Response({
                'status': 'error',
                'errors': conditional_errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create a map of provided answers for quick lookup
        provided_answers_map = {str(a['field_id']): a['value'] for a in answers_data}
        
        # 1. Check Required Fields
        section_fields = section.fields.all()
        for field in section_fields:
            if field.is_required:
                val = provided_answers_map.get(str(field.id))
                if val is None or val == '':
                     validation_errors[str(field.id)] = "This field is required."
        
        # 2. Check Types and Constraints
        for answer in answers_data:
            field_id = str(answer['field_id'])
            value = answer['value']
            
            # Verify field belongs to this section (security check)
            # Find field in pre-fetched section_fields list
            field = next((f for f in section_fields if str(f.id) == field_id), None)
            
            if not field:
                validation_errors[field_id] = "Field does not belong to this section."
                continue
                
            is_valid, error = self._validate_answer(field, value)
            if not is_valid:
                 validation_errors[field_id] = error

        if validation_errors:
             return Response({
                 'status': 'error',
                 'errors': validation_errors
             }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save answers
        for answer in answers_data:
            field_id = answer['field_id']
            value = answer['value']
            stored_value = str(value)
            
            FieldAnswer.objects.update_or_create(
                response=response,
                field_id=field_id,
                defaults={'value': stored_value}
            )
            
        # Update progress
        response.last_section = section
        response.updated_at = timezone.now()
        response.save()
        
        # Get progress and completion status
        progress = service.get_survey_progress(response)
        is_complete = service.is_survey_complete(response)
        
        return Response({
            'status': 'success',
            'message': 'Section saved successfully',
            'is_complete': is_complete,
            'progress': progress
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Survey Submission"],
        summary="Get current section to complete",
        description="""
        **Get Next Section**
        
        Retrieves the next section the user should complete. This endpoint:
        - Validates the session token
        - Evaluates conditional rules to determine visible sections
        - Finds the first incomplete visible section
        - Returns section with visible fields and filtered options
        - Includes progress information
        
        **Authentication**: Session token required in `X-Session-Token` header
        
        **Response**:
        - `current_section`: Section with fields to complete (null if survey is complete)
        - `is_complete`: Boolean indicating if survey is complete
        - `progress`: Progress metrics (sections completed, total, remaining, percentage)
        
        **Frontend Flow**:
        1. Call this endpoint after starting survey or submitting a section
        2. If `is_complete=false`, display `current_section` to user
        3. If `is_complete=true`, show completion screen
        
        **Error Responses**:
        - `400`: Missing `X-Session-Token` header
        - `404`: Session not found
        
        **Example Request**:
        ```
        GET /api/v1/submissions/current-section/
        Headers: X-Session-Token: 6ba7b810-9dad-11d1-80b4-00c04fd430c8
        ```
        
        **Example Response**:
        ```json
        {
          "current_section": {
            "section_id": "uuid",
            "title": "Section Title",
            "order": 1,
            "fields": [
              {
                "field_id": "uuid",
                "label": "Question?",
                "field_type": "text",
                "is_required": true,
                "options": []
              }
            ]
          },
          "is_complete": false,
          "progress": {
            "sections_completed": 1,
            "total_sections": 3,
            "sections_remaining": 2,
            "percentage": 33.33
          }
        }
        ```
        """,
        parameters=[
            OpenApiParameter(
                name='X-Session-Token',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.HEADER,
                required=True,
                description='Session token obtained from starting a survey. Required for all submission endpoints.'
            ),
        ],
        responses={
            200: CurrentSectionResponseSerializer,
            400: {'description': 'Missing X-Session-Token header'},
            404: {'description': 'Session not found'}
        }
    )
    @action(detail=False, methods=['get'], url_path='current-section')
    def get_current_section(self, request):
        session_token = request.headers.get('X-Session-Token')
        if not session_token:
            return Response({'detail': 'X-Session-Token header required'}, status=status.HTTP_400_BAD_REQUEST)
        
        response = get_object_or_404(SurveyResponse, session_token=session_token)
        
        service = ConditionalLogicService()
        result = service.get_current_section(response)
        
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Survey Submission"],
        summary="Get specific section for navigation/editing",
        description="""
        **Navigation: Get Section with Pre-filled Answers**
        
        Retrieves a specific section with existing answers pre-filled. This endpoint:
        - Validates the session token
        - Checks section visibility (cannot access hidden sections)
        - Retrieves existing answers for pre-filling
        - Returns section with `current_value` for each field
        
        **Authentication**: Session token required in `X-Session-Token` header
        
        **Use Cases**:
        - User wants to go back and edit previous answers
        - User navigates to a specific section
        - Pre-fill form with existing answers
        
        **Response**:
        - `section`: Section information with pre-filled answers
        - `is_editable`: Whether this section can be edited
        - `progress`: Current progress information
        
        **Error Responses**:
        - `400`: Missing `X-Session-Token` header
        - `404`: Session or section not found
        - `403`: Section is hidden (not visible based on conditional logic)
        
        **Example Request**:
        ```
        GET /api/v1/submissions/sections/{section_id}/
        Headers: X-Session-Token: 6ba7b810-9dad-11d1-80b4-00c04fd430c8
        ```
        
        **Example Response**:
        ```json
        {
          "section": {
            "section_id": "uuid",
            "title": "Section Title",
            "order": 1,
            "fields": [
              {
                "field_id": "uuid",
                "label": "Question?",
                "field_type": "text",
                "is_required": true,
                "current_value": "previous answer",
                "options": []
              }
            ]
          },
          "is_editable": true,
          "progress": {
            "sections_completed": 2,
            "total_sections": 3,
            "sections_remaining": 1,
            "percentage": 66.67
          }
        }
        ```
        """,
        parameters=[
            OpenApiParameter(
                name='X-Session-Token',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.HEADER,
                required=True,
                description='Session token obtained from starting a survey. Required for all submission endpoints.'
            ),
        ],
        responses={
            200: SectionResponseSerializer,
            400: {'description': 'Missing X-Session-Token header'},
            404: {'description': 'Session or section not found'},
            403: {'description': 'Section is hidden'}
        },
        auth=[],  # No authentication required for public submission endpoints
    )
    @action(detail=False, methods=['get'], url_path='sections/(?P<section_id>[^/.]+)/')
    def get_section(self, request, section_id=None):
        session_token = request.headers.get('X-Session-Token')
        if not session_token:
            return Response({'detail': 'X-Session-Token header required'}, status=status.HTTP_400_BAD_REQUEST)
        
        response = get_object_or_404(SurveyResponse, session_token=session_token)
        
        service = ConditionalLogicService()
        result = service.get_section(section_id, response)
        
        if result is None:
            return Response(
                {'detail': 'Section not found or not visible'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Survey Submission"],
        summary="Finish survey",
        description="""
        **Step 3: Complete Survey**
        
        Marks the survey response as completed. This endpoint:
        - Validates the session token
        - Changes status from `IN_PROGRESS` to `COMPLETED`
        - Records completion timestamp
        - Prevents further modifications (future: allow edits with permission)
        
        **Authentication**: Session token required in `X-Session-Token` header
        
        **Prerequisites**:
        - Survey response must be in `IN_PROGRESS` status
        - All required visible sections should be completed (not enforced here, but recommended)
        
        **Use Cases**:
        - Explicit completion by user
        - Final confirmation after last section submission
        - Mark survey as done even if some optional sections skipped
        
        **Post-Completion**:
        - Survey response cannot be modified (status = `COMPLETED`)
        - Session token remains valid for viewing results (if applicable)
        - Data is ready for analytics and reporting
        
        **Error Responses**:
        - `400`: Missing `X-Session-Token` header
        - `404`: Session not found
        - `400`: Survey already completed (status != `IN_PROGRESS`)
        
        **Example Request**:
        ```
        POST /api/v1/submissions/finish/
        Headers: X-Session-Token: 6ba7b810-9dad-11d1-80b4-00c04fd430c8
        ```
        
        **Example Response**:
        ```json
        {
          "message": "Survey completed successfully",
          "completed_at": "2024-01-15T10:30:00Z"
        }
        ```
        
        **Note**: In the new API flow, this endpoint may be optional if `submit_section` returns `is_complete: true` for the final section.
        """,
        parameters=[
            OpenApiParameter(
                name='X-Session-Token',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.HEADER,
                required=True,
                description='Session token obtained from starting a survey. Required for all submission endpoints.'
            ),
        ],
        responses={
            200: FinishSurveyResponseSerializer,
            400: {
                'description': 'Missing header or survey already completed',
                'examples': {
                    'application/json': {
                        'detail': 'X-Session-Token header required'
                    }
                }
            },
            404: {'description': 'Session not found'}
        }
    )
    @action(detail=False, methods=['post'], url_path='finish')
    def finish_survey(self, request):
        session_token = request.headers.get('X-Session-Token')
        if not session_token:
            return Response({'detail': 'X-Session-Token header required'}, status=status.HTTP_400_BAD_REQUEST)
            
        response = get_object_or_404(SurveyResponse, session_token=session_token, status=SurveyResponse.Status.IN_PROGRESS)
        
        response.status = SurveyResponse.Status.COMPLETED
        response.completed_at = timezone.now()
        response.save()
        
        return Response({
            'message': 'Survey completed successfully',
            'completed_at': response.completed_at
        })

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class ResponseViewSet(AuditLogMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for viewing survey responses (requires RBAC permissions).
    
    Endpoints:
    - GET /surveys/{survey_id}/responses/ - List responses for a survey
    - GET /responses/{response_id}/ - Get single response details
    - GET /surveys/{survey_id}/export/ - Export responses (CSV/JSON)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SurveyResponseListSerializer
    
    def get_queryset(self):
        """Return queryset based on user permissions, filtered by user's organizations."""
        user = self.request.user
        
        # Get user's organization IDs
        user_org_ids = user.organizations.values_list('id', flat=True)
        
        # Users with view_responses permission see responses in their organizations
        if user_has_permission(user, 'view_responses'):
            return SurveyResponse.objects.filter(
                survey__organization__in=user_org_ids
            ).select_related(
                'survey', 'respondent'
            ).prefetch_related(
                'answers__field'
            )
        
        # Otherwise, no access (shouldn't reach here due to permission check)
        return SurveyResponse.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return SurveyResponseDetailSerializer
        return SurveyResponseListSerializer
    
    def get_permissions(self):
        """Return appropriate permission classes based on action."""
        if self.action == 'export_responses':
            return [IsAuthenticated(), CanExportResponses()]
        if self.action == 'analytics':
            return [IsAuthenticated(), CanViewAnalytics()]
        if self.action == 'send_invitations':
            return [IsAuthenticated(), CanPublishSurvey()]
        return [IsAuthenticated(), CanViewResponses()]
    
    def _verify_survey_access(self, survey_pk):
        """
        Verify user has access to survey's organization.
        
        Returns the survey if access is granted, raises PermissionDenied otherwise.
        """
        user = self.request.user
        survey = get_object_or_404(Survey, id=survey_pk)
        
        if not survey.organization or not survey.organization.members.filter(id=user.id).exists():
            raise PermissionDenied("You don't have access to this survey's organization")
        
        return survey
    
    @extend_schema(
        tags=["Response Management"],
        summary="List responses for a survey",
        description="""
        List all responses for a specific survey.
        
        **Permission**: Requires `view_responses` permission (manager/viewer roles).
        
        **Features**:
        - Pagination (20 per page)
        - Filtering: status, date range
        - Ordering: started_at, completed_at
        - Automatic decryption of sensitive fields
        
        **Query Parameters**:
        - `status`: Filter by status (in_progress, completed)
        - `start_date`: Filter responses started after this date (ISO format)
        - `end_date`: Filter responses started before this date (ISO format)
        - `ordering`: Order by field (started_at, completed_at, -started_at, -completed_at)
        """,
        parameters=[
            OpenApiParameter(
                name='survey_pk',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description='UUID of the survey'
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter by status: in_progress or completed'
            ),
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter responses started after this date (YYYY-MM-DD)'
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter responses started before this date (YYYY-MM-DD)'
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Order by: started_at, completed_at, -started_at, -completed_at'
            ),
        ],
        responses={
            200: SurveyResponseListSerializer(many=True),
            403: {'description': 'Permission denied'},
            404: {'description': 'Survey not found'}
        }
    )
    def list(self, request, survey_pk=None):
        """List responses for a survey."""
        # Get survey_pk from URL or kwargs
        survey_pk = survey_pk or self.kwargs.get('survey_pk')
        if not survey_pk:
            return Response({'detail': 'Survey ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify user has access to survey's organization
        survey = self._verify_survey_access(survey_pk)
        
        # Filter by survey
        queryset = self.get_queryset().filter(survey=survey)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        start_date = request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(started_at__gte=start_date)
        
        end_date = request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(started_at__lte=end_date)
        
        # Apply ordering
        ordering = request.query_params.get('ordering', '-started_at')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        tags=["Response Management"],
        summary="Get single response details",
        description="""
        Get detailed information about a specific survey response.
        
        **Permission**: Requires `view_responses` permission.
        
        **Features**:
        - Full response details with all answers
        - Automatic decryption of sensitive fields
        - Includes survey and respondent information
        """,
        responses={
            200: SurveyResponseDetailSerializer,
            403: {'description': 'Permission denied'},
            404: {'description': 'Response not found'}
        }
    )
    def retrieve(self, request, pk=None):
        """Get single response details."""
        response = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(response)
        return Response(serializer.data)
    
    @extend_schema(
        tags=["Response Management"],
        summary="Export responses as CSV or JSON",
        description="""
        Export survey responses as CSV or JSON file.
        
        **Permission**: Requires `export_responses` permission (manager role).
        
        **Formats**:
        - CSV: One row per response, columns for each field
        - JSON: Array of response objects with nested structure
        
        **Query Parameters**:
        - `format`: csv or json (default: csv)
        - `status`: Filter by status (optional)
        - `start_date`, `end_date`: Date range filter (optional)
        
        **CSV Format**:
        - Headers: Response ID, Survey, Respondent, Status, Started At, Completed At, [Field Labels...]
        - One row per response
        - Sensitive fields are decrypted
        
        **JSON Format**:
        - Pretty-printed JSON
        - Includes metadata (export_date, total_count)
        - Full response structure with nested answers
        
        **Response**:
        - Returns HTTP 202 Accepted with confirmation message
        - Export file will be sent to your email address when ready
        - No polling or status checking required
        """,
        parameters=[
            OpenApiParameter(
                name='survey_pk',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description='UUID of the survey'
            ),
            OpenApiParameter(
                name='format',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Export format: csv or json (default: csv)'
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter by status: in_progress or completed'
            ),
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter responses started after this date (YYYY-MM-DD)'
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter responses started before this date (YYYY-MM-DD)'
            ),
        ],
        responses={
            202: {'description': 'Export request received - File will be sent via email'},
            403: {'description': 'Permission denied'},
            404: {'description': 'Survey not found'}
        }
    )
    def export_responses(self, request, survey_pk=None):
        """Export responses as CSV or JSON (always async, sent via email)."""
        
        # Get survey_pk from URL or kwargs
        survey_pk = survey_pk or self.kwargs.get('survey_pk')
        if not survey_pk:
            return Response({'detail': 'Survey ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify user has access to survey's organization
        survey = self._verify_survey_access(survey_pk)
        
        # Get queryset
        queryset = self.get_queryset().filter(survey=survey)
        
        # Apply filters
        filters = {}
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            filters['status'] = status_filter
        
        start_date = request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(started_at__gte=start_date)
            filters['start_date'] = start_date
        
        end_date = request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(started_at__lte=end_date)
            filters['end_date'] = end_date
        
        # Get format
        export_format = request.query_params.get('format', 'csv').lower()
        
        # Get response count for confirmation message
        response_count = queryset.count()
        
        # Always trigger async task
        export_responses_async.delay(
            survey_id=str(survey.id),
            user_id=str(request.user.id),
            export_format=export_format,
            filters=filters
        )
        
        return Response({
            'message': f'Export request received. The export file will be sent to {request.user.email} when ready.',
            'email': request.user.email,
            'survey': survey.title,
            'response_count': response_count
        }, status=status.HTTP_202_ACCEPTED)
    
    @extend_schema(
        tags=["Analytics"],
        summary="Get survey analytics",
        description="""
        Get aggregated analytics for a specific survey.
        
        **Permission**: Requires `view_analytics` permission.
        
        **Metrics returned**:
        - `total_responses`: Total number of responses
        - `completed_responses`: Number of completed responses
        - `in_progress_responses`: Number of in-progress responses
        - `completion_rate`: Percentage of completed responses (0-100)
        - `average_completion_time_seconds`: Average time to complete the survey
        - `last_response_at`: Timestamp of the most recent response
        
        **Caching**: Results are cached for 60 seconds.
        """,
        parameters=[
            OpenApiParameter(
                name='survey_pk',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description='UUID of the survey'
            ),
        ],
        responses={
            200: SurveyAnalyticsSerializer,
            403: {'description': 'Permission denied'},
            404: {'description': 'Survey not found'}
        }
    )
    def analytics(self, request, survey_pk=None):
        """Get analytics for a specific survey."""
        survey_pk = survey_pk or self.kwargs.get('survey_pk')
        if not survey_pk:
            return Response({'detail': 'Survey ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify user has access to survey's organization
        self._verify_survey_access(survey_pk)
        
        # Get analytics
        service = AnalyticsService()
        analytics = service.get_survey_analytics(str(survey_pk))
        
        if analytics is None:
            return Response({'detail': 'Survey not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SurveyAnalyticsSerializer(analytics)
        return Response(serializer.data)
    
    @extend_schema(
        tags=["Response Management"],
        summary="Send batch survey invitations",
        description="""
        Send survey invitations to a list of email addresses.
        
        **Permission**: Requires `publish_survey` permission or survey ownership.
        
        **Features**:
        - Emails are sent asynchronously via Celery
        - Duplicate emails are automatically removed
        - Creates audit trail with Invitation records
        - Maximum 1000 recipients per request
        
        **Request Body**:
        ```json
        {
          "emails": ["user1@example.com", "user2@example.com"]
        }
        ```
        
        **Response** (202 Accepted):
        ```json
        {
          "message": "Sending invitations to 50 recipients",
          "survey": "Customer Feedback",
          "recipient_count": 50
        }
        ```
        
        **Notes**:
        - Invitations are queued and processed in batches of 50
        - Each invitation creates an audit record
        - Email delivery is best-effort (no tracking of bounces)
        """,
        parameters=[
            OpenApiParameter(
                name='survey_pk',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description='UUID of the survey to send invitations for'
            ),
        ],
        request=InvitationRequestSerializer,
        responses={
            202: InvitationResponseSerializer,
            400: {'description': 'Invalid request body'},
            403: {'description': 'Permission denied'},
            404: {'description': 'Survey not found'}
        }
    )
    def send_invitations(self, request, survey_pk=None):
        """Send batch survey invitations."""
        survey_pk = survey_pk or self.kwargs.get('survey_pk')
        if not survey_pk:
            return Response({'detail': 'Survey ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify user has access to survey's organization
        survey = self._verify_survey_access(survey_pk)
        
        # Validate request
        serializer = InvitationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        emails = serializer.validated_data['emails']
        
        # Queue the task
        send_survey_invitations.delay(
            survey_id=str(survey.id),
            emails=emails,
            sent_by_user_id=str(request.user.id)
        )
        
        # Return response
        response_data = {
            'message': f'Sending invitations to {len(emails)} recipients',
            'survey': survey.title,
            'recipient_count': len(emails)
        }
        
        return Response(
            InvitationResponseSerializer(response_data).data,
            status=status.HTTP_202_ACCEPTED
        )
