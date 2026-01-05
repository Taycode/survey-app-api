from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Survey, Section, Field, FieldOption, ConditionalRule, FieldDependency


class FieldOptionSerializer(serializers.ModelSerializer):
    """Serializer for field options (dropdown, checkbox, radio)."""

    class Meta:
        model = FieldOption
        fields = ['id', 'label', 'value', 'order']
        read_only_fields = ['id']


class FieldSerializer(serializers.ModelSerializer):
    """Serializer for survey fields."""
    options = FieldOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Field
        fields = [
            'id', 'label', 'field_type', 'is_required', 'is_sensitive',
            'order', 'config', 'has_dependencies', 'options'
        ]
        read_only_fields = ['id', 'has_dependencies']


class FieldCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating fields."""

    class Meta:
        model = Field
        fields = ['id', 'label', 'field_type', 'is_required', 'is_sensitive', 'order', 'config']
        read_only_fields = ['id']


class SectionSerializer(serializers.ModelSerializer):
    """Serializer for survey sections."""
    fields = FieldSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'title', 'description', 'order', 'created_at', 'fields']
        read_only_fields = ['id', 'created_at']


class SectionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating sections."""

    class Meta:
        model = Section
        fields = ['id', 'title', 'description', 'order']
        read_only_fields = ['id']


class ConditionalRuleSerializer(serializers.ModelSerializer):
    """Serializer for conditional rules."""
    source_field_label = serializers.CharField(source='source_field.label', read_only=True)

    class Meta:
        model = ConditionalRule
        fields = [
            'id', 'target_type', 'target_id', 'source_field', 'source_field_label',
            'operator', 'value', 'action'
        ]
        read_only_fields = ['id', 'source_field_label']


class FieldDependencySerializer(serializers.ModelSerializer):
    """Serializer for field dependencies."""
    dependent_field_label = serializers.CharField(source='dependent_field.label', read_only=True)
    source_field_label = serializers.CharField(source='source_field.label', read_only=True)

    class Meta:
        model = FieldDependency
        fields = [
            'id', 'dependent_field', 'dependent_field_label',
            'source_field', 'source_field_label', 'source_value', 'dependent_options'
        ]
        read_only_fields = ['id', 'dependent_field_label', 'source_field_label']


class SurveyListSerializer(serializers.ModelSerializer):
    """Serializer for listing surveys (minimal data)."""
    sections_count = serializers.SerializerMethodField()
    responses_count = serializers.SerializerMethodField()

    class Meta:
        model = Survey
        fields = ['id', 'title', 'description', 'status', 'created_at', 'updated_at', 'sections_count', 'responses_count']
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(serializers.IntegerField)
    def get_sections_count(self, obj):
        return obj.sections.count()

    @extend_schema_field(serializers.IntegerField)
    def get_responses_count(self, obj):
        return obj.responses.count()


class SurveyDetailSerializer(serializers.ModelSerializer):
    """Serializer for survey detail with sections, fields, rules embedded."""
    sections = SectionSerializer(many=True, read_only=True)
    conditional_rules = serializers.SerializerMethodField()
    field_dependencies = serializers.SerializerMethodField()

    class Meta:
        model = Survey
        fields = [
            'id', 'title', 'description', 'status', 'created_at', 'updated_at',
            'sections', 'conditional_rules', 'field_dependencies'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(ConditionalRuleSerializer(many=True))
    def get_conditional_rules(self, obj):
        # Get all rules for fields in this survey
        field_ids = Field.objects.filter(section__survey=obj).values_list('id', flat=True)
        rules = ConditionalRule.objects.filter(source_field__id__in=field_ids)
        return ConditionalRuleSerializer(rules, many=True).data

    @extend_schema_field(FieldDependencySerializer(many=True))
    def get_field_dependencies(self, obj):
        # Get all dependencies for fields in this survey
        field_ids = Field.objects.filter(section__survey=obj).values_list('id', flat=True)
        dependencies = FieldDependency.objects.filter(source_field__id__in=field_ids)
        return FieldDependencySerializer(dependencies, many=True).data


class SurveyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating surveys."""

    class Meta:
        model = Survey
        fields = ['id', 'title', 'description']
        read_only_fields = ['id']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
