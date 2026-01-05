from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

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


@extend_schema(
    tags=["Authentication"],
    summary="Register a new user",
    description="""
    Create a new user account and receive authentication tokens.
    
    **Process:**
    1. Submit user registration details (email, password, first_name, last_name)
    2. System creates user account and establishes a session
    3. Returns user profile and JWT tokens (access and refresh)
    
    **Authentication:** None required (public endpoint)
    
    **Session Tracking:** A session is automatically created and linked to the tokens for security tracking.
    """,
    request=RegisterSerializer,
    responses={
        201: OpenApiResponse(
            response=UserSerializer,
            description="User successfully registered",
            examples=[
                OpenApiExample(
                    "Success Response",
                    value={
                        "user": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "email": "user@example.com",
                            "first_name": "John",
                            "last_name": "Doe",
                            "role": "analyst"
                        },
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Invalid input data (e.g., email already exists, weak password)"),
    }
)
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


@extend_schema(
    tags=["Authentication"],
    summary="Login user",
    description="""
    Authenticate a user and receive JWT tokens.
    
    **Process:**
    1. Submit credentials (email and password)
    2. System validates credentials and creates a new session
    3. Returns user profile and JWT tokens (access and refresh)
    
    **Authentication:** None required (public endpoint)
    
    **Token Usage:** 
    - Use the `access` token in the Authorization header: `Bearer <access_token>`
    - Access tokens expire in 15 minutes
    - Use the `refresh` token to obtain new access tokens
    
    **Security:** Each login creates a new session tracked by IP and user agent.
    """,
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(
            description="Login successful",
            examples=[
                OpenApiExample(
                    "Success Response",
                    value={
                        "user": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "email": "user@example.com",
                            "first_name": "John",
                            "last_name": "Doe",
                            "role": "analyst"
                        },
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Invalid credentials"),
        401: OpenApiResponse(description="Authentication failed"),
    }
)
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


@extend_schema(
    tags=["Authentication"],
    summary="Logout user",
    description="""
    Logout the current user and invalidate the session.
    
    **Process:**
    1. Extract session ID from the JWT token
    2. Mark the session as inactive
    3. Record logout timestamp
    
    **Authentication:** Required (Bearer token)
    
    **Security:** After logout, the refresh token associated with this session will no longer work. 
    The access token will continue to work until it expires (15 minutes), but the session will be marked as logged out.
    
    **Note:** This is a security best practice that allows tracking of active sessions and forced logout capabilities.
    """,
    request=None,
    responses={
        200: OpenApiResponse(
            description="Logout successful",
            examples=[
                OpenApiExample(
                    "Success Response",
                    value={"detail": "Logged out successfully"}
                )
            ]
        ),
        401: OpenApiResponse(description="Not authenticated"),
    }
)
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


@extend_schema(
    tags=["Authentication"],
    summary="Refresh access token",
    description="""
    Obtain a new access token using a refresh token.
    
    **Process:**
    1. Submit a valid refresh token
    2. System validates the token and checks session status
    3. Returns a new access token
    
    **Authentication:** None required, but valid refresh token must be provided
    
    **Token Lifecycle:**
    - Access tokens expire in 15 minutes
    - Refresh tokens expire in 7 days
    - Use this endpoint before the access token expires to maintain continuous access
    
    **Session Validation:** The system checks if the session is still active. 
    If the user has logged out, the refresh token will be rejected.
    """,
    request=RefreshTokenSerializer,
    responses={
        200: OpenApiResponse(
            description="Token refreshed successfully",
            examples=[
                OpenApiExample(
                    "Success Response",
                    value={"access": "eyJ0eXAiOiJKV1QiLCJhbGc..."}
                )
            ]
        ),
        401: OpenApiResponse(description="Invalid or expired refresh token, or session has been logged out"),
    }
)
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


@extend_schema(
    tags=["User Profile"],
    summary="Get or update user profile",
    description="""
    Retrieve or update the authenticated user's profile information.
    
    **GET Request:** Returns the current user's profile details including ID, email, name, and role.
    
    **PATCH/PUT Request:** Update profile information (first_name, last_name). 
    Email and role cannot be updated through this endpoint.
    
    **Authentication:** Required (Bearer token)
    
    **Audit Logging:** All profile updates are logged for security tracking.
    """,
    responses={
        200: OpenApiResponse(
            response=UserSerializer,
            description="Profile retrieved or updated successfully",
            examples=[
                OpenApiExample(
                    "User Profile",
                    value={
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "user@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "role": "analyst"
                    }
                )
            ]
        ),
        401: OpenApiResponse(description="Not authenticated"),
        400: OpenApiResponse(description="Invalid update data"),
    }
)
class UserProfileView(AuditLogMixin, generics.RetrieveUpdateAPIView):
    """Get or update current user profile."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
