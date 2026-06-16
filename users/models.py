from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import secrets

class CustomUser(AbstractUser):
    username = models.CharField(max_length=30, unique=True)
    email = models.EmailField(unique=True, blank=False)
    is_active = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=64, blank=True)
    token_created = models.DateTimeField(default=timezone.now)

    def generate_verification_token(self):
        self.verification_token = secrets.token_urlsafe(32)
        self.token_created = timezone.now()
        self.save()
        return self.verification_token  # Добавьте возврат токена

    def __str__(self):
        return self.username

