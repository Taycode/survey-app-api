"""
Service layer for conditional logic, field dependencies validation, and analytics.

This module handles the evaluation of conditional rules and field dependencies
during survey submission to ensure data integrity and proper survey flow.
It also provides analytics services for survey response statistics.
"""
from typing import Dict, Set, List, Tuple
from django.db.models import Count, Q, Max
from django.core.cache import cache
from surveys.models import ConditionalRule, FieldDependency, Section, Field, Survey
from submissions.models import SurveyResponse, FieldAnswer


class ConditionalLogicService:
    """
    Service for evaluating conditional rules and field dependencies.
    
    This service provides methods to:
    - Determine which sections/fields should be visible based on answers
    - Filter field options based on dependencies
    - Validate submissions against conditional logic
    """
    
    def get_all_answers_for_response(self, survey_response: SurveyResponse) -> Dict[str, str]:
        """
        Get all answers for a survey response.
        
        Args:
            survey_response: The SurveyResponse object
            
        Returns:
            Dictionary mapping field_id (as string) -> answer value
            Example: {'field-uuid-1': 'yes', 'field-uuid-2': '25'}
        """
        # Query all answers for this response in one go
        answers = FieldAnswer.objects.filter(
            response=survey_response
        ).select_related('field')
        
        # Build dictionary: field_id -> value
        answers_dict = {}
        for answer in answers:
            field_id = str(answer.field_id)
            # Handle encrypted values: decrypt if field is sensitive
            if answer.field.is_sensitive and answer.encrypted_value:
                try:
                    value = answer.decrypted_value
                except Exception:
                    # If decryption fails, skip this answer (shouldn't happen in normal flow)
                    continue
            else:
                # Non-sensitive field: use plaintext value
                value = answer.value if answer.value else ''
            answers_dict[field_id] = value
        
        return answers_dict
    
    def evaluate_rule(self, rule: ConditionalRule, answers_dict: Dict[str, str]) -> bool:
        """
        Evaluate if a conditional rule's condition is met.
        
        Args:
            rule: The ConditionalRule object to evaluate
            answers_dict: Dictionary of field_id -> answer value
            
        Returns:
            True if condition is met, False otherwise
        """
        # Get the answer for the source field
        source_field_id = str(rule.source_field_id)
        answer_value = answers_dict.get(source_field_id, '')  # Default to empty if not answered
        
        # Handle empty/null answers
        if not answer_value:
            if rule.operator == ConditionalRule.Operator.IS_EMPTY:
                return True
            elif rule.operator == ConditionalRule.Operator.IS_NOT_EMPTY:
                return False
            else:
                return False  # Other operators require a value
        
        # Compare based on operator
        rule_value = rule.value or ''
        
        if rule.operator == ConditionalRule.Operator.EQUALS:
            return answer_value == rule_value
        
        elif rule.operator == ConditionalRule.Operator.NOT_EQUALS:
            return answer_value != rule_value
        
        elif rule.operator == ConditionalRule.Operator.GREATER_THAN:
            try:
                return float(answer_value) > float(rule_value)
            except (ValueError, TypeError):
                return False
        
        elif rule.operator == ConditionalRule.Operator.LESS_THAN:
            try:
                return float(answer_value) < float(rule_value)
            except (ValueError, TypeError):
                return False
        
        elif rule.operator == ConditionalRule.Operator.CONTAINS:
            return rule_value.lower() in answer_value.lower()
        
        elif rule.operator == ConditionalRule.Operator.IN:
            # rule_value is comma-separated list: "value1,value2,value3"
            allowed_values = [v.strip() for v in rule_value.split(',')]
            return answer_value in allowed_values
        
        elif rule.operator == ConditionalRule.Operator.IS_EMPTY:
            return not answer_value or answer_value == ''
        
        elif rule.operator == ConditionalRule.Operator.IS_NOT_EMPTY:
            return bool(answer_value and answer_value != '')
        
        return False  # Unknown operator
    
    def get_visible_sections(self, survey_response: SurveyResponse) -> Set[str]:
        """
        Determine which sections should be visible based on conditional rules.
        
        Args:
            survey_response: The SurveyResponse object
            
        Returns:
            Set of section IDs (as strings) that should be visible
        """
        # Get all answers
        answers_dict = self.get_all_answers_for_response(survey_response)
        
        # Get all sections in the survey
        all_sections = survey_response.survey.sections.all()
        visible_sections = {str(s.id) for s in all_sections}  # Start with all visible
        
        # Get all rules that target sections
        rules = ConditionalRule.objects.filter(
            source_field__section__survey=survey_response.survey,
            target_type=ConditionalRule.TargetType.SECTION
        ).select_related('source_field')
        
        # Evaluate each rule
        for rule in rules:
            condition_met = self.evaluate_rule(rule, answers_dict)
            
            if condition_met:
                target_id = str(rule.target_id)
                
                if rule.action == ConditionalRule.Action.HIDE:
                    # Remove from visible set
                    visible_sections.discard(target_id)
                elif rule.action == ConditionalRule.Action.SHOW:
                    # Add to visible set
                    visible_sections.add(target_id)
        
        return visible_sections
    
    def get_visible_fields(self, section: Section, survey_response: SurveyResponse) -> Set[str]:
        """
        Determine which fields in a section should be visible.
        
        Args:
            section: The Section object
            survey_response: The SurveyResponse object
            
        Returns:
            Set of field IDs (as strings) that should be visible
        """
        # Get all answers
        answers_dict = self.get_all_answers_for_response(survey_response)
        
        # Start with all fields in section visible
        all_fields = section.fields.all()
        visible_fields = {str(f.id) for f in all_fields}
        
        # Get all rules targeting fields in this section
        field_ids = [str(f.id) for f in all_fields]
        rules = ConditionalRule.objects.filter(
            source_field__section__survey=section.survey,
            target_type=ConditionalRule.TargetType.FIELD
        ).select_related('source_field')
        
        # Filter rules that target fields in this section
        for rule in rules:
            target_id = str(rule.target_id)
            if target_id not in field_ids:
                continue
            
            condition_met = self.evaluate_rule(rule, answers_dict)
            
            if condition_met:
                if rule.action == ConditionalRule.Action.HIDE:
                    visible_fields.discard(target_id)
                elif rule.action == ConditionalRule.Action.SHOW:
                    visible_fields.add(target_id)
        
        return visible_fields
    
    def get_field_options(self, field: Field, survey_response: SurveyResponse) -> List[Dict]:
        """
        Get available options for a field, considering dependencies.
        
        Args:
            field: The Field object
            survey_response: The SurveyResponse object
            
        Returns:
            List of option dictionaries [{"label": "...", "value": "..."}]
        """
        # If field has no dependencies, return default options
        if not field.has_dependencies:
            return [
                {"label": opt.label, "value": opt.value}
                for opt in field.options.all().order_by('order')
            ]
        
        # Get all answers
        answers_dict = self.get_all_answers_for_response(survey_response)
        
        # Get dependencies for this field
        dependencies = FieldDependency.objects.filter(
            dependent_field=field
        ).select_related('source_field')
        
        # Find matching dependency
        for dependency in dependencies:
            source_field_id = str(dependency.source_field_id)
            source_answer = answers_dict.get(source_field_id, '')
            
            # If source field answer matches dependency condition
            if source_answer == dependency.source_value:
                # Return dependent options
                return dependency.dependent_options
        
        # No matching dependency found, return default options
        return [
            {"label": opt.label, "value": opt.value}
            for opt in field.options.all().order_by('order')
        ]
    
    def validate_submission(
        self, 
        section: Section, 
        answers_data: List[Dict], 
        survey_response: SurveyResponse
    ) -> Tuple[bool, Dict]:
        """
        Validate a section submission against conditional rules.
        
        Args:
            section: Section being submitted
            answers_data: List of answers [{"field_id": "...", "value": "..."}]
            survey_response: The survey response object
            
        Returns:
            Tuple of (is_valid: bool, errors: dict)
        """
        errors = {}
        
        # 1. Check if section is visible
        visible_sections = self.get_visible_sections(survey_response)
        if str(section.id) not in visible_sections:
            errors['section'] = f"Section '{section.title}' is not available based on your previous answers."
            return False, errors
        
        # 2. Get visible fields for this section
        visible_fields = self.get_visible_fields(section, survey_response)
        
        # 3. Check each answer being submitted
        provided_field_ids = set()
        for answer in answers_data:
            field_id = str(answer['field_id'])
            provided_field_ids.add(field_id)
            value = answer.get('value', '')
            
            # Check if field is visible
            if field_id not in visible_fields:
                errors[field_id] = "This field is not available based on your previous answers."
                continue
            
            # Get the field object
            try:
                field = Field.objects.get(id=field_id, section=section)
            except Field.DoesNotExist:
                errors[field_id] = "Field does not belong to this section."
                continue
            
            # If field has dependencies, validate value against filtered options
            if field.has_dependencies:
                available_options = self.get_field_options(field, survey_response)
                option_values = [opt['value'] for opt in available_options]
                
                if value not in option_values:
                    option_labels = [opt['label'] for opt in available_options]
                    errors[field_id] = f"Invalid option selected. Available options: {', '.join(option_labels)}"
        
        # 4. Check required fields
        section_fields = section.fields.all()
        for field in section_fields:
            field_id = str(field.id)
            
            # Only check if field is visible and required
            if field_id in visible_fields and field.is_required:
                if field_id not in provided_field_ids:
                    errors[field_id] = "This field is required."
        
        # Return validation result
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def get_section_with_fields(
        self, 
        section: Section, 
        survey_response: SurveyResponse, 
        include_current_values: bool = False
    ) -> Dict:
        """
        Get section with visible fields and filtered options.
        
        Args:
            section: The Section object
            survey_response: The SurveyResponse object
            include_current_values: If True, include existing answers in field data
            
        Returns:
            Dictionary with section info and fields
        """
        # Get visible fields for this section
        visible_fields = self.get_visible_fields(section, survey_response)
        
        # Get existing answers if needed
        answers_dict = {}
        if include_current_values:
            answers_dict = self.get_all_answers_for_response(survey_response)
        
        # Build fields list
        fields_info = []
        for field in section.fields.all().order_by('order'):
            field_id = str(field.id)
            
            # Only include visible fields
            if field_id not in visible_fields:
                continue
            
            field_info = {
                'field_id': field.id,
                'label': field.label,
                'field_type': field.field_type,
                'is_required': field.is_required,
            }
            
            # Include current value if requested
            if include_current_values:
                current_value = answers_dict.get(field_id)
                if current_value:
                    field_info['current_value'] = current_value
            
            # If field has options (dropdown, radio, checkbox), include them
            if field.field_type in [Field.FieldType.DROPDOWN, Field.FieldType.RADIO, Field.FieldType.CHECKBOX]:
                options = self.get_field_options(field, survey_response)
                field_info['options'] = options
            
            fields_info.append(field_info)
        
        return {
            'section_id': section.id,
            'title': section.title,
            'order': section.order,
            'fields': fields_info
        }
    
    def get_current_section(self, survey_response: SurveyResponse) -> Dict:
        """
        Get the current section the user should complete.
        
        Args:
            survey_response: The SurveyResponse object
            
        Returns:
            Dictionary with current section info, or None if complete
            Format: {
                'section': {...section with fields...},
                'is_complete': False,
                'progress': {...}
            }
        """
        # Get visible sections
        visible_sections = self.get_visible_sections(survey_response)
        
        # Get all sections ordered by order
        all_sections = survey_response.survey.sections.all().order_by('order')
        
        # Get completed section IDs
        completed_sections = set(
            FieldAnswer.objects.filter(
                response=survey_response
            ).values_list('field__section_id', flat=True).distinct()
        )
        
        # Find first visible section that hasn't been completed
        for section in all_sections:
            section_id = str(section.id)
            
            # Skip if not visible
            if section_id not in visible_sections:
                continue
            
            # Skip if already completed
            if section.id in completed_sections:
                continue
            
            # Found the current section
            section_data = self.get_section_with_fields(section, survey_response)
            progress = self.get_survey_progress(survey_response)
            
            return {
                'current_section': section_data,
                'is_complete': False,
                'progress': progress
            }
        
        # No incomplete sections found - survey is complete
        progress = self.get_survey_progress(survey_response)
        return {
            'current_section': None,
            'is_complete': True,
            'progress': progress
        }
    
    def get_survey_progress(self, survey_response: SurveyResponse) -> Dict:
        """
        Calculate progress metrics for a survey response.
        
        Args:
            survey_response: The SurveyResponse object
            
        Returns:
            Dictionary with progress metrics:
            {
                'sections_completed': int,
                'total_sections': int,
                'sections_remaining': int,
                'percentage': float
            }
        """
        # Get visible sections
        visible_sections = self.get_visible_sections(survey_response)
        
        # Count total visible sections
        all_sections = survey_response.survey.sections.all()
        total_sections = sum(1 for s in all_sections if str(s.id) in visible_sections)
        
        # Get completed sections (sections that have at least one answer)
        completed_section_ids = set(
            FieldAnswer.objects.filter(
                response=survey_response
            ).values_list('field__section_id', flat=True).distinct()
        )
        
        # Count completed visible sections
        sections_completed = sum(
            1 for s in all_sections 
            if s.id in completed_section_ids and str(s.id) in visible_sections
        )
        
        sections_remaining = total_sections - sections_completed
        percentage = (sections_completed / total_sections * 100) if total_sections > 0 else 0
        
        return {
            'sections_completed': sections_completed,
            'total_sections': total_sections,
            'sections_remaining': sections_remaining,
            'percentage': round(percentage, 2)
        }
    
    def is_survey_complete(self, survey_response: SurveyResponse) -> bool:
        """
        Check if survey is complete (all visible sections have been answered).
        
        Args:
            survey_response: The SurveyResponse object
            
        Returns:
            True if survey is complete, False otherwise
        """
        current_section_data = self.get_current_section(survey_response)
        return current_section_data['is_complete']
    
    def get_section(self, section_id: str, survey_response: SurveyResponse) -> Dict | None:
        """
        Get a specific section with existing answers pre-filled (for navigation).
        
        Args:
            section_id: UUID string of the section
            survey_response: The SurveyResponse object
            
        Returns:
            Dictionary with section info and pre-filled answers
        """
        try:
            section = Section.objects.get(id=section_id, survey=survey_response.survey)
        except Section.DoesNotExist:
            return None
        
        # Check if section is visible
        visible_sections = self.get_visible_sections(survey_response)
        if str(section.id) not in visible_sections:
            return None  # Section is hidden
        
        # Get section with pre-filled values
        section_data = self.get_section_with_fields(section, survey_response, include_current_values=True)
        progress = self.get_survey_progress(survey_response)
        
        return {
            'section': section_data,
            'is_editable': True,
            'progress': progress
        }


class AnalyticsService:
    """
    Service for computing survey analytics and statistics.
    
    Provides methods to calculate:
    - Response counts (total, completed, in-progress)
    - Completion rates
    - Average completion time
    - Platform-wide summary statistics
    
    Results are cached for performance (60 second TTL).
    """
    
    CACHE_TTL = 60  # Cache analytics for 60 seconds
    
    def get_survey_analytics(self, survey_id: str, use_cache: bool = True) -> Dict | None:
        """
        Get analytics for a specific survey.
        
        Args:
            survey_id: UUID of the survey
            use_cache: Whether to use cached results (default: True)
            
        Returns:
            Dictionary with analytics metrics:
            {
                'survey_id': 'uuid',
                'survey_title': 'Survey Title',
                'total_responses': 150,
                'completed_responses': 120,
                'in_progress_responses': 30,
                'completion_rate': 80.0,
                'average_completion_time_seconds': 342,
                'last_response_at': datetime or None
            }
        """
        cache_key = f"survey_analytics_{survey_id}"
        
        # Try to get from cache
        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        
        # Get survey
        try:
            survey = Survey.objects.get(id=survey_id)
        except Survey.DoesNotExist:
            return None
        
        # Get response statistics using aggregation
        stats = SurveyResponse.objects.filter(survey_id=survey_id).aggregate(
            total_responses=Count('id'),
            completed_responses=Count('id', filter=Q(status=SurveyResponse.Status.COMPLETED)),
            in_progress_responses=Count('id', filter=Q(status=SurveyResponse.Status.IN_PROGRESS)),
            last_response_at=Max('started_at'),
        )
        
        # Calculate average completion time for completed responses
        # completion_time = completed_at - started_at
        completed_responses = SurveyResponse.objects.filter(
            survey_id=survey_id,
            status=SurveyResponse.Status.COMPLETED,
            completed_at__isnull=False
        )
        
        # Calculate average completion time manually (Django doesn't have ExtractEpoch)
        avg_completion_seconds = None
        if completed_responses.exists():
            total_seconds = 0
            count = 0
            for resp in completed_responses.only('started_at', 'completed_at'):
                if resp.completed_at and resp.started_at:
                    duration = resp.completed_at - resp.started_at
                    total_seconds += duration.total_seconds()
                    count += 1
            if count > 0:
                avg_completion_seconds = total_seconds / count
        
        avg_completion_time = {'avg_time': avg_completion_seconds}
        
        total = stats['total_responses'] or 0
        completed = stats['completed_responses'] or 0
        
        # Calculate completion rate
        completion_rate = (completed / total * 100) if total > 0 else 0.0
        
        result = {
            'survey_id': str(survey.id),
            'survey_title': survey.title,
            'total_responses': total,
            'completed_responses': completed,
            'in_progress_responses': stats['in_progress_responses'] or 0,
            'completion_rate': round(completion_rate, 2),
            'average_completion_time_seconds': (
                int(avg_completion_time['avg_time']) 
                if avg_completion_time['avg_time'] is not None 
                else None
            ),
            'last_response_at': stats['last_response_at'],
        }
        
        # Cache the result
        cache.set(cache_key, result, self.CACHE_TTL)
        
        return result
    
    def invalidate_survey_cache(self, survey_id: str) -> None:
        """
        Invalidate cached analytics for a specific survey.
        
        Call this when a new response is submitted or a response status changes.
        
        Args:
            survey_id: UUID of the survey
        """
        cache_key = f"survey_analytics_{survey_id}"
        cache.delete(cache_key)

