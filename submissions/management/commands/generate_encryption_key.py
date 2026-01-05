"""
Management command to generate a new encryption key for sensitive fields.

Usage:
    python manage.py generate_encryption_key
    
Output:
    A base64-encoded 32-byte key suitable for use in FIELD_ENCRYPTION_KEY environment variable.
"""
from django.core.management.base import BaseCommand
from submissions.encryption import EncryptionService


class Command(BaseCommand):
    help = 'Generate a new encryption key for sensitive field encryption'

    def handle(self, *args, **options):
        key = EncryptionService.generate_key()
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('Generated Encryption Key:'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.WARNING(key))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('\n')
        self.stdout.write('Add this to your .env file:')
        self.stdout.write(self.style.WARNING(f'FIELD_ENCRYPTION_KEY={key}'))
        self.stdout.write('\n')
        self.stdout.write('Or export as environment variable:')
        self.stdout.write(self.style.WARNING(f'export FIELD_ENCRYPTION_KEY={key}'))
        self.stdout.write('\n')
        self.stdout.write(self.style.ERROR('⚠️  Keep this key secure! Do not commit it to version control.'))
        self.stdout.write('\n')

