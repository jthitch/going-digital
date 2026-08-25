from django.test import SimpleTestCase

from courses.region_scope import user_can_change_venue, user_can_edit_venue_details
from courses.venue_approval import (
    VENUE_APPROVAL_APPROVED,
    VENUE_APPROVAL_NOT_SUBMITTED,
    VENUE_APPROVAL_PENDING,
    VENUE_APPROVAL_REJECTED,
    apply_venue_approval_decision,
    content_values_from_mapping,
    live_venue_content_values,
    venue_approval_state,
)


class _FakeVenue:
    def __init__(self, **kwargs):
        self.pk = kwargs.get('pk')
        self.approved = kwargs.get('approved', 0)
        self.rejected = kwargs.get('rejected', 0)
        self.approval_requested = kwargs.get('approval_requested', 0)
        self.reject_reason = kwargs.get('reject_reason')
        self.approvedby_id = kwargs.get('approvedby_id')
        self.approved_at = kwargs.get('approved_at')
        self.approval_requested_at = kwargs.get('approval_requested_at')
        self.approval_requested_by_id = kwargs.get('approval_requested_by_id')
        self.user_id = kwargs.get('user_id')
        self.createdby_id = kwargs.get('createdby_id')
        self.region_id = kwargs.get('region_id', 1)
        self._content = kwargs.get('content')

    def get_content(self):
        return self._content


class _FakeContent:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeUser:
    def __init__(self, *, pk=1, is_superuser=False, user_type_id=3, region_ids=None):
        self.pk = pk
        self.is_authenticated = True
        self.is_superuser = is_superuser
        self.user_type_id = user_type_id
        self.is_region_scoped = not is_superuser and user_type_id != 2
        self._region_ids = region_ids or [1]

    def get_region_ids(self):
        return list(self._region_ids)


class VenueApprovalHelpersTests(SimpleTestCase):
    def test_venue_approval_state(self):
        self.assertEqual(venue_approval_state(None), VENUE_APPROVAL_NOT_SUBMITTED)
        self.assertEqual(
            venue_approval_state(_FakeVenue(pk=1, approved=1)),
            VENUE_APPROVAL_APPROVED,
        )
        self.assertEqual(
            venue_approval_state(_FakeVenue(pk=1, rejected=1)),
            VENUE_APPROVAL_REJECTED,
        )
        self.assertEqual(
            venue_approval_state(_FakeVenue(pk=1, approval_requested=1)),
            VENUE_APPROVAL_PENDING,
        )
        self.assertEqual(
            venue_approval_state(_FakeVenue(pk=1)),
            VENUE_APPROVAL_NOT_SUBMITTED,
        )

    def test_apply_approve_sets_flags_and_stamp(self):
        venue = _FakeVenue(pk=1, approval_requested=1)
        apply_venue_approval_decision(
            venue,
            VENUE_APPROVAL_APPROVED,
            editor_user_id=9,
            now='NOW',
        )
        self.assertEqual(venue.approved, 1)
        self.assertEqual(venue.rejected, 0)
        self.assertEqual(venue.approval_requested, 0)
        self.assertIsNone(venue.reject_reason)
        self.assertEqual(venue.approvedby_id, 9)
        self.assertEqual(venue.approved_at, 'NOW')

    def test_apply_reject_requires_reason_storage(self):
        venue = _FakeVenue(pk=1, approval_requested=1)
        apply_venue_approval_decision(
            venue,
            VENUE_APPROVAL_REJECTED,
            reject_reason='  Missing photos  ',
        )
        self.assertEqual(venue.approved, 0)
        self.assertEqual(venue.rejected, 1)
        self.assertEqual(venue.approval_requested, 0)
        self.assertEqual(venue.reject_reason, 'Missing photos')

    def test_apply_pending_clears_rejection(self):
        venue = _FakeVenue(pk=1, rejected=1, reject_reason='No')
        apply_venue_approval_decision(venue, VENUE_APPROVAL_PENDING, editor_user_id=3)
        self.assertEqual(venue.approved, 0)
        self.assertEqual(venue.rejected, 0)
        self.assertEqual(venue.approval_requested, 1)
        self.assertIsNone(venue.reject_reason)

    def test_live_venue_content_values(self):
        venue = _FakeVenue(
            pk=1,
            content=_FakeContent(
                content_title='Title',
                strapline='Strap',
                main_content='Main',
                sub_content='',
                meta_title='',
                meta_description='',
                meta_keywords='',
            ),
        )
        values = live_venue_content_values(venue)
        self.assertEqual(values['content_title'], 'Title')
        self.assertEqual(values['main_content'], 'Main')
        self.assertEqual(content_values_from_mapping({'content_title': 'X'})['content_title'], 'X')

    def test_franchisee_can_change_approved_venue_but_not_details(self):
        from unittest.mock import patch

        user = _FakeUser(pk=5, region_ids=[1])
        venue = _FakeVenue(pk=9, approved=1, user_id=5, region_id=1)
        with patch('courses.region_scope.franchisee_has_venue_workshop_grant', return_value=False):
            self.assertTrue(user_can_change_venue(user, venue))
            self.assertFalse(user_can_edit_venue_details(user, venue))

    def test_franchisee_can_edit_details_when_pending(self):
        from unittest.mock import patch

        user = _FakeUser(pk=5, region_ids=[1])
        venue = _FakeVenue(pk=9, approved=0, user_id=5, region_id=1)
        with patch('courses.region_scope.franchisee_has_venue_workshop_grant', return_value=False):
            self.assertTrue(user_can_change_venue(user, venue))
            self.assertTrue(user_can_edit_venue_details(user, venue))
