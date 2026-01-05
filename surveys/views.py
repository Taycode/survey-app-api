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
    list=extend_schema(summary="List surveys", description="Get all surveys. Users with view_responses permission see all surveys, others see only their own."),
    create=extend_schema(summary="Create survey", description="Create a new survey. Requires create_survey permission."),
    retrieve=extend_schema(summary="Get survey", description="Get survey details with sections, fields, and rules. Users with view_responses permission or survey creators can view."),
    partial_update=extend_schema(summary="Update survey", description="Update survey title, description, or status. Requires edit_survey permission or be the creator."),
    destroy=extend_schema(summary="Delete survey", description="Delete a survey and all its data. Requires delete_survey permission or be the creator."),
)
class SurveyViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """ViewSet for managing surveys."""
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        """Return surveys based on user permissions."""
        user = self.request.user
        # If user has view_responses permission, show all surveys
        if user_has_permission(user, 'view_responses'):
            return Survey.objects.all()
        # Otherwise, show only surveys they created
        return Survey.objects.filter(created_by=user)

    def get_permissions(self):
        """Return appropriate permission classes based on action."""
        if self.action == 'create':
            return [IsAuthenticated(), CanCreateSurvey()]
        elif self.action == 'partial_update':
            return [IsAuthenticated(), CanEditSurvey()]
        elif self.action == 'destroy':
            return [IsAuthenticated(), CanDeleteSurvey()]
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
        
        # User has view_responses permission
        if user_has_permission(user, 'view_responses'):
            return super().retrieve(request, *args, **kwargs)
        
        # User is the creator
        if survey.created_by == user:
            return super().retrieve(request, *args, **kwargs)
        
        # User doesn't have permission
        return Response({'detail': 'You do not have permission to view this survey.'}, status=status.HTTP_403_FORBIDDEN)

    @extend_schema(summary="Publish survey", description="Change survey status to published. Requires publish_survey permission.")
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanPublishSurvey])
    def publish(self, request, pk=None):
        survey = self.get_object()
        if survey.status == Survey.Status.PUBLISHED:
            return Response({'detail': 'Survey is already published'}, status=status.HTTP_400_BAD_REQUEST)
        survey.status = Survey.Status.PUBLISHED
        survey.save()
        return Response({'detail': 'Survey published successfully'})

    @extend_schema(summary="Close survey", description="Change survey status to closed. Requires edit_survey permission or be the creator.")
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
