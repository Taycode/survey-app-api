from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.utils import timezone

from .models import User, UserSession
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
    get_tokens_for_user_with_session,
)
from audit.mixins import AuditLogMixin


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class RegisterView(generics.CreateAPIView):
    """User registration endpoint."""
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Create session
        session = UserSession.objects.create(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )

        # Generate tokens
        tokens = get_tokens_for_user_with_session(user, session)

        return Response({
            'user': UserSerializer(user).data,
            'access': tokens['access'],
            'refresh': tokens['refresh'],
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """User login endpoint."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # Create session
        session = UserSession.objects.create(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )

        # Generate tokens
        tokens = get_tokens_for_user_with_session(user, session)

        return Response({
            'user': UserSerializer(user).data,
            'access': tokens['access'],
            'refresh': tokens['refresh'],
        })


class LogoutView(APIView):
    """User logout endpoint - deactivates the session."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Get session_id from the token
        session_id = request.auth.get('session_id') if request.auth else None
        
        if session_id:
            try:
                session = UserSession.objects.get(id=session_id)
                session.is_active = False
                session.logged_out_at = timezone.now()
                session.save()
            except UserSession.DoesNotExist:
                pass

        return Response({'detail': 'Logged out successfully'})


class RefreshTokenView(APIView):
    """Refresh access token endpoint."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh = RefreshToken(serializer.validated_data['refresh'])
            
            # Check if session is still active
            session_id = refresh.get('session_id')
            if session_id:
                try:
                    session = UserSession.objects.get(id=session_id)
                    if not session.is_active:
                        return Response(
                            {'detail': 'Session has been logged out'},
                            status=status.HTTP_401_UNAUTHORIZED
                        )
                except UserSession.DoesNotExist:
                    return Response(
                        {'detail': 'Session not found'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )

            return Response({
                'access': str(refresh.access_token),
            })
        except TokenError as e:
            return Response({'detail': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


class UserProfileView(AuditLogMixin, generics.RetrieveUpdateAPIView):
    """Get or update current user profile."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
