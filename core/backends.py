"""Custom auth backend for email-based login with gd_user."""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import make_password

from .models import User


class EmailBackend(ModelBackend):
    """Authenticate by email instead of username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            make_password(password, hasher='pbkdf2_sha256')  # Timing attack prevention
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
