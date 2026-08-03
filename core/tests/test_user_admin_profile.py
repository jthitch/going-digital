from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase

from core.admin import UserAdmin

User = get_user_model()


class FranchiseeProfileAdminTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = admin.site
        self.user_admin = UserAdmin(User, self.site)

    def _franchisee(self):
        return User(
            pk=42,
            email='franchisee@example.com',
            user_type_id=3,
            active=1,
            is_franchisee=1,
        )

    def _administrator(self):
        return User(pk=1, email='admin@example.com', user_type_id=2, active=1)

    def test_franchisee_can_change_own_profile_only(self):
        user = self._franchisee()
        request = self.factory.get('/admin/core/user/my-profile/')
        request.user = user

        self.assertFalse(self.user_admin.has_module_permission(request))
        self.assertTrue(self.user_admin.has_change_permission(request, user))
        self.assertFalse(self.user_admin.has_change_permission(request, self._administrator()))

    def test_franchisee_profile_fieldsets_exclude_permissions(self):
        user = self._franchisee()
        request = self.factory.get('/')
        request.user = user

        fieldsets = self.user_admin.get_fieldsets(request, user)
        flat_fields = [f for _title, opts in fieldsets for f in opts.get('fields', ())]
        self.assertIn('telephone', flat_fields)
        self.assertIn('address', flat_fields)
        self.assertIn('postcode', flat_fields)
        self.assertNotIn('user_type_id', flat_fields)
        self.assertNotIn('regions', flat_fields)

    def test_administrator_keeps_full_user_admin_access(self):
        admin_user = self._administrator()
        request = self.factory.get('/admin/core/user/')
        request.user = admin_user

        self.assertTrue(self.user_admin.has_module_permission(request))
        other = self._franchisee()
        self.assertTrue(self.user_admin.has_change_permission(request, other))
