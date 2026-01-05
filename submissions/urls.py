from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubmissionViewSet, ResponseViewSet

router = DefaultRouter()
router.register(r'submissions', SubmissionViewSet, basename='submissions')
router.register(r'responses', ResponseViewSet, basename='responses')

urlpatterns = [
    path('surveys/<uuid:survey_pk>/submissions/', include([
        path('start/', SubmissionViewSet.as_view({'post': 'start_survey'}), name='survey-submissions-start'),
    ])),
    path('surveys/<uuid:survey_pk>/responses/', ResponseViewSet.as_view({'get': 'list'}), name='survey-responses-list'),
    path('surveys/<uuid:survey_pk>/responses/export/', ResponseViewSet.as_view({'get': 'export_responses'}), name='survey-responses-export'),
    path('surveys/<uuid:survey_pk>/responses/analytics/', ResponseViewSet.as_view({'get': 'analytics'}), name='survey-responses-analytics'),
    path('surveys/<uuid:survey_pk>/invitations/', ResponseViewSet.as_view({'post': 'send_invitations'}), name='survey-invitations'),
    path('', include(router.urls)),
]
