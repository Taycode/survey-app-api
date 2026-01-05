"""
Custom exception handler for DRF to catch database and other unhandled errors.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError


def custom_exception_handler(exc, context):
    """
    Custom exception handler that catches database errors and returns JSON.
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    # If DRF handled it, return that response
    if response is not None:
        return response
    
    # Handle IntegrityError (duplicate key, constraint violations)
    if isinstance(exc, IntegrityError):
        error_message = str(exc)
        
        # Parse common constraint violations for user-friendly messages
        if 'duplicate key' in error_message.lower():
            if 'order' in error_message.lower():
                detail = "A record with this order already exists. Please use a different order value."
            else:
                detail = "A record with this value already exists. Please use a different value."
        elif 'violates foreign key constraint' in error_message.lower():
            detail = "Referenced record does not exist."
        elif 'violates not-null constraint' in error_message.lower():
            detail = "Required field is missing."
        else:
            detail = "Database constraint violation. Please check your data."
        
        return Response(
            {"detail": detail, "error_type": "integrity_error"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Handle other unhandled exceptions
    return Response(
        {"detail": "An unexpected error occurred.", "error_type": "server_error"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

