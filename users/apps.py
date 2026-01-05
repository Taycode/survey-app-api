from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "users"
    
    def ready(self):
        # Import schema extensions for drf-spectacular autodiscovery
        try:
            import users.schema  # noqa: F401
        except ImportError:
            pass