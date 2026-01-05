from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    SurveyViewSet,
    SectionViewSet,
    FieldViewSet,
    FieldOptionViewSet,
    ConditionalRuleViewSet,
    FieldDependencyViewSet,
)

# Main router for surveys
router = DefaultRouter()
router.register(r'surveys', SurveyViewSet, basename='survey')

# Nested router for sections under surveys
surveys_router = routers.NestedDefaultRouter(router, r'surveys', lookup='survey')
surveys_router.register(r'sections', SectionViewSet, basename='survey-sections')
surveys_router.register(r'rules', ConditionalRuleViewSet, basename='survey-rules')
surveys_router.register(r'dependencies', FieldDependencyViewSet, basename='survey-dependencies')

# Nested router for fields under sections
sections_router = routers.NestedDefaultRouter(surveys_router, r'sections', lookup='section')
sections_router.register(r'fields', FieldViewSet, basename='section-fields')

# Nested router for options under fields
fields_router = routers.NestedDefaultRouter(sections_router, r'fields', lookup='field')
fields_router.register(r'options', FieldOptionViewSet, basename='field-options')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(surveys_router.urls)),
    path('', include(sections_router.urls)),
    path('', include(fields_router.urls)),
]
