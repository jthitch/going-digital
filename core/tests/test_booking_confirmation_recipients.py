from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.mail import (
    booking_confirmation_bcc_emails,
    franchisee_emails_for_workshop,
    superuser_notification_emails,
)


class FranchiseeEmailsForWorkshopTests(SimpleTestCase):
    @override_settings(EMAIL_FRANCHISEE_BCC_ENABLED=True, EMAIL_SUPPRESS_RECIPIENTS=[])
    @patch('courses.models.Tutor.objects')
    @patch('courses.models.RegionUser.objects')
    @patch('core.models.User.objects')
    def test_includes_owner_creator_tutor_and_course_creator(
        self, user_objects, region_objects, tutor_objects,
    ):
        region_objects.filter.return_value.values_list.return_value = []
        tutor_objects.filter.return_value.first.return_value = SimpleNamespace(
            email='tutor@example.com',
        )

        def user_filter(**kwargs):
            mapping = {
                10: SimpleNamespace(email='owner@example.com'),
                11: SimpleNamespace(email='creator@example.com'),
                12: SimpleNamespace(email='course-creator@example.com'),
            }
            qs = MagicMock()
            qs.first.return_value = mapping.get(kwargs.get('pk'))
            return qs

        user_objects.filter.side_effect = user_filter

        course = SimpleNamespace(createdby_id=12)
        workshop = SimpleNamespace(
            user_id=10,
            createdby_id=11,
            region_id=None,
            tutor_id=5,
            course=course,
        )

        emails = franchisee_emails_for_workshop(workshop)
        self.assertEqual(
            set(emails),
            {
                'owner@example.com',
                'creator@example.com',
                'course-creator@example.com',
                'tutor@example.com',
            },
        )


class SuperuserNotificationEmailsTests(SimpleTestCase):
    @override_settings(EMAIL_SUPERUSER_BCC_ENABLED=True, EMAIL_SUPPRESS_RECIPIENTS=[])
    @patch('core.models.User.objects')
    def test_lists_active_superusers(self, user_objects):
        user_objects.filter.return_value.exclude.return_value.exclude.return_value = [
            SimpleNamespace(email='admin1@example.com'),
            SimpleNamespace(email='Admin2@Example.com'),
            SimpleNamespace(email=''),
        ]
        emails = superuser_notification_emails()
        self.assertEqual(emails, ['admin1@example.com', 'admin2@example.com'])

    @override_settings(EMAIL_SUPERUSER_BCC_ENABLED=False, EMAIL_SUPPRESS_RECIPIENTS=[])
    def test_disabled_returns_empty(self):
        self.assertEqual(superuser_notification_emails(), [])


class BookingConfirmationBccEmailsTests(SimpleTestCase):
    @override_settings(EMAIL_SUPPRESS_RECIPIENTS=[])
    @patch('core.mail.superuser_notification_emails', return_value=['admin@example.com', 'tutor@example.com'])
    @patch(
        'core.mail.franchisee_emails_for_workshop',
        return_value=['tutor@example.com', 'franchisee@example.com', 'student@example.com'],
    )
    def test_merges_dedupes_and_excludes_student(self, _franchisee, _super):
        booking = SimpleNamespace(workshop=object())
        bcc = booking_confirmation_bcc_emails(
            [booking],
            student_email='student@example.com',
        )
        self.assertEqual(
            bcc,
            ['tutor@example.com', 'franchisee@example.com', 'admin@example.com'],
        )
