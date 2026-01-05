from django.contrib import admin
from .models import Survey, Section, Field, FieldOption, ConditionalRule, FieldDependency


class SectionInline(admin.TabularInline):
    model = Section
    extra = 1
    ordering = ('order',)


class FieldInline(admin.TabularInline):
    model = Field
    extra = 1
    ordering = ('order',)


class FieldOptionInline(admin.TabularInline):
    model = FieldOption
    extra = 3
    ordering = ('order',)


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_by', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'description')
    date_hierarchy = 'created_at'
    inlines = [SectionInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'survey', 'order', 'created_at')
    list_filter = ('survey',)
    search_fields = ('title', 'survey__title')
    inlines = [FieldInline]


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ('label', 'section', 'field_type', 'is_required', 'is_sensitive', 'order')
    list_filter = ('field_type', 'is_required', 'is_sensitive')
    search_fields = ('label', 'section__title')
    inlines = [FieldOptionInline]


@admin.register(FieldOption)
class FieldOptionAdmin(admin.ModelAdmin):
    list_display = ('label', 'value', 'field', 'order')
    list_filter = ('field__section__survey',)
    search_fields = ('label', 'value')


@admin.register(ConditionalRule)
class ConditionalRuleAdmin(admin.ModelAdmin):
    list_display = ('target_type', 'target_id', 'source_field', 'operator', 'value', 'action')
    list_filter = ('target_type', 'operator', 'action')
    search_fields = ('source_field__label',)


@admin.register(FieldDependency)
class FieldDependencyAdmin(admin.ModelAdmin):
    list_display = ('dependent_field', 'source_field', 'source_value')
    search_fields = ('dependent_field__label', 'source_field__label')
