from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from courses.region_scope import (
    franchisee_has_venue_workshop_grant,
    user_can_access_venue,
)


class VenueWorkshopAccessScopeTests(SimpleTestCase):
    def _franchisee(self, pk=42):
        user = MagicMock()
        user.pk = pk
        user.is_authenticated = True
        user.is_superuser = False
        user.user_type_id = 3
        return user

    @patch('courses.region_scope.franchisee_owns_venue', return_value=False)
    @patch('courses.region_scope.franchisee_has_venue_workshop_grant', return_value=True)
    def test_user_can_view_venue_with_workshop_grant(self, _grant, _owns):
        user = self._franchisee()
        venue = MagicMock(region_id=1)
        self.assertTrue(user_can_access_venue(user, venue))

    @patch('courses.region_scope.venue_workshop_access_venue_ids', return_value=frozenset({5}))
    def test_franchisee_has_grant(self, _ids):
        user = self._franchisee()
        venue = MagicMock(pk=5)
        self.assertTrue(franchisee_has_venue_workshop_grant(user, venue))
