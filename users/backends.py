from django.contrib.auth.backends import ModelBackend
from .models import CustomUser

class EmailVerificationBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username, password, **kwargs)
        if user and (not user.email_verified or not user.is_active):
            return None  # Запретить вход
        return user