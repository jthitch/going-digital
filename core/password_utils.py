"""Shared password verification for gd_customer and legacy gd_user hashes."""
import bcrypt

from django.contrib.auth.hashers import check_password, identify_hasher


def is_django_password_hash(stored_hash):
    stored_hash = (stored_hash or '').strip()
    if not stored_hash:
        return False
    try:
        identify_hasher(stored_hash)
        return True
    except ValueError:
        return False


def is_legacy_bcrypt_hash(stored_hash):
    stored_hash = (stored_hash or '').strip()
    return bool(stored_hash) and stored_hash.startswith('$2')


def verify_legacy_bcrypt(raw_password, stored_hash):
    """
    Verify legacy bcrypt hashes stored as raw $2* strings.
    Legacy PHP systems use $2y$; Python bcrypt expects $2b$.
    """
    stored_hash = (stored_hash or '').strip()
    if not stored_hash or not stored_hash.startswith('$2'):
        return False

    candidate_hash = stored_hash
    if stored_hash.startswith('$2y$') or stored_hash.startswith('$2a$'):
        candidate_hash = '$2b$' + stored_hash[4:]

    try:
        return bcrypt.checkpw(
            raw_password.encode('utf-8'),
            candidate_hash.encode('utf-8'),
        )
    except Exception:
        return False


def verify_password_against_hash(raw_password, stored_hash):
    """Return True when raw_password matches a Django or legacy bcrypt hash."""
    stored_hash = (stored_hash or '').strip()
    if not stored_hash or not raw_password:
        return False

    if is_django_password_hash(stored_hash):
        return check_password(raw_password, stored_hash)

    if verify_legacy_bcrypt(raw_password, stored_hash):
        return True

    return check_password(raw_password, stored_hash)


def hash_needs_upgrade(stored_hash):
    """True when a successful login should re-hash to Django pbkdf2."""
    return is_legacy_bcrypt_hash(stored_hash)
