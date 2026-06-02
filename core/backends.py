"""Custom auth backend for email-based login with gd_user."""
import bcrypt

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import identify_hasher, make_password

from .models import User


class EmailBackend(ModelBackend):
    """Authenticate by email instead of username."""

    @staticmethod
    def _is_django_password_hash(stored_hash):
        if not stored_hash:
            return False
        try:
            identify_hasher(stored_hash)
            return True
        except ValueError:
            return False

    @staticmethod
    def _verify_legacy_bcrypt(raw_password, stored_hash):
        """
        Verify legacy bcrypt hashes stored as raw $2* strings.
        Legacy PHP systems often use the $2y$ prefix; Python bcrypt expects $2b$.
        """
        if not stored_hash or not stored_hash.startswith("$2"):
            return False

        candidate_hash = stored_hash
        if stored_hash.startswith("$2y$") or stored_hash.startswith("$2a$"):
            candidate_hash = "$2b$" + stored_hash[4:]

        try:
            return bcrypt.checkpw(
                raw_password.encode("utf-8"),
                candidate_hash.encode("utf-8"),
            )
        except Exception:
            return False

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=username.strip())
        except User.DoesNotExist:
            make_password(password, hasher='pbkdf2_sha256')  # Timing attack prevention
            return None

        stored = user.password or ''

        # 1) Django pbkdf2/argon2 hashes (set via set_password, createsuperuser, or admin).
        if self._is_django_password_hash(stored):
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
            return None

        # 2) Legacy raw bcrypt ($2y$ / $2a$ / $2b$) from the old PHP site.
        if self._verify_legacy_bcrypt(password, stored):
            user.set_password(password)
            user.save(update_fields=['password'])
            if self.user_can_authenticate(user):
                return user
            return None

        # 3) Other Django-style checks (e.g. partial/unknown encodings).
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
