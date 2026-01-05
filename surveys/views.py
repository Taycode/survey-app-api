from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Survey, Section, Field, FieldOption, ConditionalRule, FieldDependency
from .serializers import (
    SurveyListSerializer,
    SurveyDetailSerializer,
    SurveyCreateSerializer,
    SectionSerializer,
    SectionCreateSerializer,
    FieldSerializer,
    FieldCreateSerializer,
    FieldOptionSerializer,
    ConditionalRuleSerializer,
    FieldDependencySerializer,
)
from audit.mixins import AuditLogMixin
from users.permissions import (
    CanCreateSurvey,
    CanEditSurvey,
    CanDeleteSurvey,
    CanPublishSurvey,
    CanViewResponses,
    user_has_permission,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Surveys"],
        summary="List surveys",
        description="""
        Retrieve a list of surveys based on user permissions.
        
        **Permission-based filtering:**
        - Users with `view_responses` permission can see all surveys
        - Other users only see surveys they created
        
        **Supports pagination** (default: 20 items per page)
        """
    ),
    create=extend_schema(
        tags=["Surveys"],
        summary="Create survey",
        description="""
        Create a new survey with title, description, and optional settings.
        
        **Required Permission:** `create_survey`
        
        **Next Steps:** After creation:
        1. Add sections to organize the survey
        2. Add fields to each section
        3. Configure conditional logic (optional)
        4. Publish the survey to make it available for submissions
        """
    ),
    retrieve=extend_schema(
        tags=["Surveys"],
        summary="Get survey details",
        description="""
        Retrieve complete survey details including all sections, fields, options, and conditional rules.
        
        **Access Control:**
        - Users with `view_responses` permission can view any survey
        - Survey creators can view their own surveys
        - Returns 403 for unauthorized access
        
        **Response includes:** Full nested structure with sections, fields, field options, conditional rules, and dependencies.
        """
    ),
    partial_update=extend_schema(
        tags=["Surveys"],
        summary="Update survey",
        description="""
        Update survey metadata (title, description, status).
        
        **Required Permission:** `edit_survey` or be the survey creator
        
        **Updatable Fields:**
        - title
        - description
        - status (draft/published/closed)
        
        **Note:** Use dedicated endpoints to manage sections, fields, and rules.
        """
    ),
    destroy=extend_schema(
        tags=["Surveys"],
        summary="Delete survey",
        description="""
        Permanently delete a survey and all associated data.
        
        **Required Permission:** `delete_survey` or be the survey creator
        
        **Warning:** This action:
        - Deletes all sections, fields, and options
        - Deletes all survey responses
        - Cannot be undone
        
        **Best Practice:** Consider closing the survey instead of deleting it to preserve historical data.
        """
    ),
)
class SurveyViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """ViewSet for managing surveys."""
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        """Return surveys based on user permissions and organization membership."""
        user = self.request.user
        
        # Get all organizations user belongs to
        user_orgs = user.organizations.all()
        
        # Filter surveys in those organizations
        queryset = Survey.objects.filter(organization__in=user_orgs)
        
        # Apply additional filters based on permissions
        if not user_has_permission(user, 'view_responses'):
            # If user doesn't have view_responses permission, only show their own surveys
            queryset = queryset.filter(created_by=user)
        
        return queryset

    def get_permissions(self):
        """Return appropriate permission classes based on action."""
        if self.action == 'create':
            return [IsAuthenticated(), CanCreateSurvey()]
        elif self.action == 'partial_update':
            return [IsAuthenticated(), CanEditSurvey()]
        elif self.action == 'destroy':
            return [IsAuthenticated(), CanDeleteSurvey()]
        elif self.action == 'publish':
            return [IsAuthenticated(), CanPublishSurvey()]
        elif self.action == 'close':
            return [IsAuthenticated(), CanEditSurvey()]
        elif self.action == 'retrieve':
            # Custom check in has_object_permission
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return SurveyListSerializer
        elif self.action == 'create':
            return SurveyCreateSerializer
        elif self.action in ['retrieve', 'partial_update']:
            return SurveyDetailSerializer
        return SurveyDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        """Check if user can view this survey."""
        survey = self.get_object()
        user = request.user
        
        # Check if user is a member of the survey's organization
        if not survey.organization.members.filter(id=user.id).exists():
            return Response(
                {'detail': 'You do not have permission to view this survey.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # User has view_responses permission or is the creator
        if user_has_permission(user, 'view_responses') or survey.created_by == user:
            return super().retrieve(request, *args, **kwargs)
        
        # User doesn't have permission
        return Response(
            {'detail': 'You do not have permission to view this survey.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    def perform_create(self, serializer):
        """Set organization when creating survey."""
        organization_id = self.request.data.get('organization')
        
        if not organization_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'organization': 'This field is required.'})
        
        # Validate user is member of this org
        organization = get_object_or_404(
            self.request.user.organizations,
            id=organization_id
        )
        
        instance = serializer.save(created_by=self.request.user, organization=organization)
        # Manually log the creation since we override perform_create
        from audit.models import AuditLog
        self._log_action(AuditLog.Action.CREATED, instance)

    @extend_schema(
        tags=["Surveys"],
        summary="Publish survey",
        description="""
        Change survey status to published, making it available for public submissions.
        
        **Required Permission:** `publish_survey`
        
        **Prerequisites:** Survey should have at least one section with fields configured.
        
        **Effect:** Once published, the survey becomes accessible via the public submission endpoints.
        """
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanPublishSurvey])
    def publish(self, request, pk=None):
        survey = self.get_object()
        if survey.status == Survey.Status.PUBLISHED:
            return Response({'detail': 'Survey is already published'}, status=status.HTTP_400_BAD_REQUEST)
        survey.status = Survey.Status.PUBLISHED
        survey.save()
        return Response({'detail': 'Survey published successfully'})

    @extend_schema(
        tags=["Surveys"],
        summary="Close survey",
        description="""
        Change survey status to closed, preventing new submissions.
        
        **Required Permission:** `edit_survey` or be the survey creator
        
        **Effect:** 
        - No new submissions will be accepted
        - Existing responses remain accessible
        - Survey can still be viewed and managed
        """
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanEditSurvey])
    def close(self, request, pk=None):
        survey = self.get_object()
        survey.status = Survey.Status.CLOSED
        survey.save()
        return Response({'detail': 'Survey closed successfully'})


class SectionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing sections within a survey."""
    permission_classes = [IsAuthenticated, CanEditSurvey]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        """Return sections based on user permissions."""
        survey_pk = self.kwargs.get('survey_pk')
        user = self.request.user
        
        # If user has edit_survey permission, show all sections for this survey
        if user_has_permission(user, 'edit_survey'):
            return Section.objects.filter(survey_id=survey_pk)
        
        # Otherwise, show only sections for surveys they created
        return Section.objects.filter(
            survey_id=survey_pk,
            survey__created_by=user
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return SectionCreateSerializer
        return SectionSerializer

    def perform_create(self, serializer):
        """Validate survey access before creating section."""
        survey_pk = self.kwargs['survey_pk']
        user = self.request.user
        
        # Check if user can edit this survey
        try:
            survey = Survey.objects.get(id=survey_pk)
            if not (user_has_permission(user, 'edit_survey') or survey.created_by == user):
                raise PermissionDenied('You do not have permission to edit this survey.')
        except Survey.DoesNotExist:
            raise NotFound('Survey not found.')
        
        survey = get_object_or_404(Survey, id=survey_pk)
        serializer.save(survey=survey)


class FieldViewSet(viewsets.ModelViewSet):
    """ViewSet for managing fields within a section."""
    permission_classes = [IsAuthenticated, CanEditSurvey]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        """Return fields based on user permissions."""
        section_pk = self.kwargs.get('section_pk')
        user = self.request.user
        
        # If user has edit_survey permission, show all fields for this section
        if user_has_permission(user, 'edit_survey'):
            return Field.objects.filter(section_id=section_pk)
        
        # Otherwise, show only fields for surveys they created
        return Field.objects.filter(
            section_id=section_pk,
            section__survey__created_by=user
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return FieldCreateSerializer
        return FieldSerializer

    def perform_create(self, serializer):
        """Validate section access before creating field."""
        section_pk = self.kwargs['section_pk']
        survey_pk = self.kwargs['survey_pk']
        user = self.request.user
        
        # Check if user can edit this survey
        try:
            section = Section.objects.select_related('survey').get(
                id=section_pk,
                survey_id=survey_pk
            )
            if not (user_has_permission(user, 'edit_survey') or section.survey.created_by == user):
                raise PermissionDenied('You do not have permission to edit this survey.')
        except Section.DoesNotExist:
            raise NotFound('Section not found.')
        
        section = get_object_or_404(Section, id=section_pk, survey_id=survey_pk)
        serializer.save(section=section)


class FieldOptionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing options within a field."""
    permission_classes = [IsAuthenticated, CanEditSurvey]
    serializer_class = FieldOptionSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        """Return field options based on user permissions."""
        field_pk = self.kwargs.get('field_pk')
        user = self.request.user
        
        # If user has edit_survey permission, show all options for this field
        if user_has_permission(user, 'edit_survey'):
            return FieldOption.objects.filter(field_id=field_pk)
        
        # Otherwise, show only options for surveys they created
        return FieldOption.objects.filter(
            field_id=field_pk,
            field__section__survey__created_by=user
        )

    def perform_create(self, serializer):
        """Validate field access before creating option."""
        field_pk = self.kwargs['field_pk']
        section_pk = self.kwargs['section_pk']
        survey_pk = self.kwargs['survey_pk']
        user = self.request.user
        
        # Check if user can edit this survey
        try:
            field = Field.objects.select_related('section__survey').get(
                id=field_pk,
                section_id=section_pk,
                section__survey_id=survey_pk
            )
            if not (user_has_permission(user, 'edit_survey') or field.section.survey.created_by == user):
                raise PermissionDenied('You do not have permission to edit this survey.')
        except Field.DoesNotExist:
            raise NotFound('Field not found.')
        
        field = get_object_or_404(
            Field,
            id=field_pk,
            section_id=section_pk,
            section__survey_id=survey_pk
        )
        serializer.save(field=field)


class ConditionalRuleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing conditional rules."""
    permission_classes = [IsAuthenticated, CanEditSurvey]
    serializer_class = ConditionalRuleSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        """Return conditional rules based on user permissions."""
        survey_pk = self.kwargs.get('survey_pk')
        user = self.request.user
        
        # If user has edit_survey permission, show all rules for this survey
        if user_has_permission(user, 'edit_survey'):
            return ConditionalRule.objects.filter(
                source_field__section__survey_id=survey_pk
            )
        
        # Otherwise, show only rules for surveys they created
        return ConditionalRule.objects.filter(
            source_field__section__survey_id=survey_pk,
            source_field__section__survey__created_by=user
        )

    def perform_create(self, serializer):
        """Validate survey access before creating rule."""
        survey_pk = self.kwargs['survey_pk']
        user = self.request.user
        source_field = serializer.validated_data.get('source_field')
        
        # Validate source_field belongs to this survey
        if str(source_field.section.survey_id) != str(survey_pk):
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({'source_field': 'Field does not belong to this survey'})
        
        # Check if user can edit this survey
        if not (user_has_permission(user, 'edit_survey') or source_field.section.survey.created_by == user):
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({'detail': 'You do not have permission to edit this survey.'})
        
        serializer.save()


class FieldDependencyViewSet(viewsets.ModelViewSet):
    """ViewSet for managing field dependencies."""
    permission_classes = [IsAuthenticated, CanEditSurvey]
    serializer_class = FieldDependencySerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        """Return field dependencies based on user permissions."""
        survey_pk = self.kwargs.get('survey_pk')
        user = self.request.user
        
        # If user has edit_survey permission, show all dependencies for this survey
        if user_has_permission(user, 'edit_survey'):
            return FieldDependency.objects.filter(
                source_field__section__survey_id=survey_pk
            )
        
        # Otherwise, show only dependencies for surveys they created
        return FieldDependency.objects.filter(
            source_field__section__survey_id=survey_pk,
            source_field__section__survey__created_by=user
        )

    def perform_create(self, serializer):
        """Validate survey access before creating dependency."""
        survey_pk = self.kwargs['survey_pk']
        user = self.request.user
        source_field = serializer.validated_data.get('source_field')
        dependent_field = serializer.validated_data.get('dependent_field')
        
        from rest_framework import serializers as drf_serializers

        # Validate both fields belong to this survey
        if str(source_field.section.survey_id) != str(survey_pk):
            raise drf_serializers.ValidationError({'source_field': 'Field does not belong to this survey'})
        if str(dependent_field.section.survey_id) != str(survey_pk):
            raise drf_serializers.ValidationError({'dependent_field': 'Field does not belong to this survey'})

        # Check if user can edit this survey
        if not (user_has_permission(user, 'edit_survey') or source_field.section.survey.created_by == user):
            raise drf_serializers.ValidationError({'detail': 'You do not have permission to edit this survey.'})

        # Mark dependent field as having dependencies
        dependent_field.has_dependencies = True
        dependent_field.save(update_fields=['has_dependencies'])

        serializer.save()
