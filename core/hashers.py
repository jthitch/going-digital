"""Custom password hasher for legacy gd_user bcrypt passwords."""
import bcrypt
from django.contrib.auth.hashers import BasePasswordHasher


class BcryptPasswordHasher(BasePasswordHasher):
    """Verify bcrypt passwords from legacy gd_user table."""

    algorithm = "bcrypt"

    def verify(self, password, encoded):
        if not encoded or not encoded.startswith("$2"):
            return False
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                encoded.encode("utf-8"),
            )
        except Exception:
            return False

    def safe_summary(self, encoded):
        return {"algorithm": self.algorithm}
