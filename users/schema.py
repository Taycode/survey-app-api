"""
OpenAPI schema extensions for drf-spectacular.
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    OpenAPI authentication extension for SessionJWTAuthentication.
    This tells drf-spectacular how to document our custom JWT auth.
    """
    target_class = "users.authentication.SessionJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT access token. Get it from /api/v1/auth/login/",
        }

