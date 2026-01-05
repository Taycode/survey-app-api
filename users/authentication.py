from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.utils import timezone


class SessionJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that validates session_id from token.
    If session is inactive (logged out), reject the token.
    """

    def get_validated_token(self, raw_token):
        """Validate the token and check session status."""
        validated_token = super().get_validated_token(raw_token)
        
        # Get session_id from token
        session_id = validated_token.get('session_id')
        if not session_id:
            raise InvalidToken('Token missing session_id')
        
        # Check if session is still active
        from users.models import UserSession
        try:
            session = UserSession.objects.get(id=session_id)
            if not session.is_active:
                raise InvalidToken('Session has been logged out')
            
            # Update last activity
            session.last_activity = timezone.now()
            session.save(update_fields=['last_activity'])
            
        except UserSession.DoesNotExist:
            raise InvalidToken('Session not found')
        
        return validated_token
