"""Set a gd_user password (Django pbkdf2 hash) for admin login troubleshooting."""
import getpass

from django.core.management.base import BaseCommand, CommandError

from core.models import User


class Command(BaseCommand):
    help = (
        'Set the login password for a gd_user (stores a Django pbkdf2 hash). '
        'Use the user email address. After this, sign in to /admin/ with that email and password.'
    )

    def add_arguments(self, parser):
        parser.add_argument('email', help='User email (login username)')
        parser.add_argument(
            '--password',
            help='New password (omit to prompt securely)',
        )

    def handle(self, *args, **options):
        email = options['email'].strip()
        password = options.get('password')
        if not password:
            password = getpass.getpass('New password: ')
            confirm = getpass.getpass('Confirm password: ')
            if password != confirm:
                raise CommandError('Passwords do not match.')

        if not password:
            raise CommandError('Password cannot be empty.')

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise CommandError(f'No user with email {email!r}') from exc

        user.set_password(password)
        user.save(update_fields=['password'])

        prefix = (user.password or '')[:12]
        self.stdout.write(
            self.style.SUCCESS(
                f'Password updated for {user.email} (user_type_id={user.user_type_id}, '
                f'active={user.active}, hash starts with {prefix!r}). '
                f'Sign in at /admin/ using this email and the new password.'
            )
        )
