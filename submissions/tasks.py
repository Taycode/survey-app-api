"""
Celery tasks for asynchronous operations.

This module contains Celery tasks for handling long-running operations
like data exports and report generation.
"""
import os
import csv
import json
from datetime import datetime
from typing import Optional
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage

from .models import SurveyResponse, Invitation
from surveys.models import Survey, Field
from users.models import User


@shared_task(bind=True, name='submissions.export_responses_async')
def export_responses_async(
    self,
    survey_id: str,
    user_id: str,
    export_format: str = 'csv',
    filters: Optional[dict] = None
):
    """
    Asynchronously export survey responses as CSV or JSON.
    
    Args:
        survey_id: UUID of the survey to export
        user_id: UUID of the user requesting the export
        export_format: 'csv' or 'json'
        filters: Dictionary with optional filters:
            - status: Filter by status (in_progress, completed)
            - start_date: Filter responses started after this date
            - end_date: Filter responses started before this date
    
    Returns:
        dict: Task result with file_path and metadata
    """
    try:
        # Update task state
        self.update_state(state='PROCESSING', meta={'progress': 0})
        
        # Get survey and user
        survey = Survey.objects.get(id=survey_id)
        user = User.objects.get(id=user_id)
        
        # Build queryset
        queryset = SurveyResponse.objects.filter(survey=survey).select_related(
            'survey', 'respondent'
        ).prefetch_related('answers__field')
        
        # Apply filters
        if filters:
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            if filters.get('start_date'):
                queryset = queryset.filter(started_at__gte=filters['start_date'])
            if filters.get('end_date'):
                queryset = queryset.filter(started_at__lte=filters['end_date'])
        
        # Get all fields for CSV headers
        fields = Field.objects.filter(section__survey=survey).order_by(
            'section__order', 'order'
        )
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        task_id = str(self.request.id)
        extension = export_format.lower()
        filename = f"exports/survey_{survey_id}_{timestamp}_{task_id[:8]}.{extension}"
        
        # Ensure exports directory exists
        exports_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(exports_dir, exist_ok=True)
        
        # Generate export file in memory
        if export_format.lower() == 'json':
            file_content, content_type, attachment_filename = _export_json_memory(queryset, survey, fields)
        else:
            file_content, content_type, attachment_filename = _export_csv_memory(queryset, survey, fields)
        
        # Send email with attachment
        _send_export_email(user, survey, file_content, content_type, attachment_filename, queryset.count())
        
        return {
            'status': 'SUCCESS',
            'total_count': queryset.count(),
            'export_format': export_format,
            'email_sent_to': user.email
        }
        
    except Exception as exc:
        # Send error notification email
        try:
            _send_error_email(user, survey, str(exc))
        except Exception:
            pass  # Don't fail if email sending fails
        
        # Re-raise to trigger Celery's retry mechanism if configured
        raise


def _export_csv_memory(queryset, survey: Survey, fields):
    """Generate CSV export in memory."""
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    headers = ['Response ID', 'Survey', 'Respondent', 'Status', 'Started At', 'Completed At']
    field_labels = [f"{field.section.title} - {field.label}" for field in fields]
    headers.extend(field_labels)
    writer.writerow(headers)
    
    # Write rows
    for survey_response in queryset:
        row = [
            str(survey_response.id),
            survey_response.survey.title,
            survey_response.respondent.email if survey_response.respondent else 'Anonymous',
            survey_response.status,
            survey_response.started_at.isoformat() if survey_response.started_at else '',
            survey_response.completed_at.isoformat() if survey_response.completed_at else '',
        ]
        
        # Get answers as dict for quick lookup
        answers_dict = {}
        for answer in survey_response.answers.select_related('field').all():
            field_id = str(answer.field_id)
            # Use decrypted_value for sensitive fields
            value = answer.decrypted_value if answer.decrypted_value else ''
            answers_dict[field_id] = value
        
        # Add field values
        for field in fields:
            row.append(answers_dict.get(str(field.id), ''))
        
        writer.writerow(row)
    
    # Get content as bytes
    content = output.getvalue().encode('utf-8')
    output.close()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"survey_{survey.id}_{timestamp}.csv"
    
    return content, 'text/csv', filename


def _export_json_memory(queryset, survey: Survey, fields):
    """Generate JSON export in memory."""
    from .serializers import SurveyResponseDetailSerializer
    
    # Serialize responses
    serializer = SurveyResponseDetailSerializer(queryset, many=True)
    
    # Create JSON structure
    data = {
        'export_date': datetime.now().isoformat(),
        'survey': {
            'id': str(survey.id),
            'title': survey.title,
        },
        'total_count': queryset.count(),
        'responses': serializer.data
    }
    
    # Convert to JSON bytes
    content = json.dumps(data, indent=2, default=str).encode('utf-8')
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"survey_{survey.id}_{timestamp}.json"
    
    return content, 'application/json', filename


def _send_export_email(user: User, survey: Survey, file_content: bytes, content_type: str, filename: str, total_count: int):
    """Send export file via email."""
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@surveyplatform.com')
    
    subject = f'Survey Export Ready: {survey.title}'
    message = f"""
Hello {user.email},

Your survey export has been generated successfully.

Survey: {survey.title}
Total Responses: {total_count}
Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

The export file is attached to this email.

Best regards,
Survey Platform Team
"""
    
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email,
        to=[user.email]
    )
    
    email.attach(filename, file_content, content_type)
    email.send()


def _send_error_email(user: User, survey: Survey, error_message: str):
    """Send error notification email."""
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@surveyplatform.com')
    
    subject = f'Survey Export Failed: {survey.title}'
    message = f"""
Hello {user.email},

Unfortunately, your survey export request failed.

Survey: {survey.title}
Error: {error_message}

Please try again or contact support if the issue persists.

Best regards,
Survey Platform Team
"""
    
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email,
        to=[user.email]
    )
    email.send()


@shared_task(bind=True, name='submissions.send_survey_invitations')
def send_survey_invitations(
    self,
    survey_id: str,
    emails: list,
    sent_by_user_id: Optional[str] = None,
    batch_size: int = 50
):
    """
    Send batch survey invitations via email.
    
    Processes emails in batches to avoid timeouts and creates Invitation
    records for audit trail.
    
    Args:
        survey_id: UUID of the survey to invite users to
        emails: List of email addresses to send invitations to
        sent_by_user_id: UUID of the user who triggered the invitations
        batch_size: Number of emails to process per batch (default: 50)
    
    Returns:
        dict: Task result with success/failure counts
    """
    try:
        # Update task state
        self.update_state(state='PROCESSING', meta={'progress': 0, 'total': len(emails)})
        
        # Get survey
        survey = Survey.objects.get(id=survey_id)
        
        # Get the user who sent the invitations (optional)
        sent_by = None
        if sent_by_user_id:
            try:
                sent_by = User.objects.get(id=sent_by_user_id)
            except User.DoesNotExist:
                pass
        
        # Build survey URL
        survey_url = _build_survey_url(survey)
        
        # Process in batches
        total_emails = len(emails)
        sent_count = 0
        failed_count = 0
        failed_emails = []
        
        for batch_start in range(0, total_emails, batch_size):
            batch_end = min(batch_start + batch_size, total_emails)
            batch_emails = emails[batch_start:batch_end]
            
            for email in batch_emails:
                try:
                    # Send the invitation email
                    _send_invitation_email(email, survey, survey_url)
                    
                    # Create Invitation record for audit trail
                    Invitation.objects.create(
                        survey=survey,
                        email=email,
                        sent_by=sent_by
                    )
                    
                    sent_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    failed_emails.append({'email': email, 'error': str(e)})
            
            # Update progress
            progress = int((batch_end / total_emails) * 100)
            self.update_state(
                state='PROCESSING',
                meta={
                    'progress': progress,
                    'sent': sent_count,
                    'failed': failed_count,
                    'total': total_emails
                }
            )
        
        return {
            'status': 'SUCCESS',
            'survey_id': str(survey_id),
            'survey_title': survey.title,
            'total_recipients': total_emails,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'failed_emails': failed_emails[:10] if failed_emails else []  # Limit for payload size
        }
        
    except Survey.DoesNotExist:
        return {
            'status': 'FAILED',
            'error': f'Survey with ID {survey_id} not found'
        }
    except Exception as exc:
        return {
            'status': 'FAILED',
            'error': str(exc)
        }


def _build_survey_url(survey: Survey) -> str:
    """Build the public URL for a survey."""
    base_url = getattr(settings, 'SURVEY_BASE_URL', 'https://surveys.example.com')
    return f"{base_url}/survey/{survey.id}"


def _send_invitation_email(recipient_email: str, survey: Survey, survey_url: str):
    """Send an invitation email to a single recipient."""
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@surveyplatform.com')
    
    subject = f"You're invited: {survey.title}"
    message = f"""
Hello,

You have been invited to participate in a survey.

Survey: {survey.title}
{f'Description: {survey.description}' if survey.description else ''}

Click the link below to start the survey:
{survey_url}

Thank you for your participation!

Best regards,
Survey Platform Team
"""
    
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email,
        to=[recipient_email]
    )
    email.send()

