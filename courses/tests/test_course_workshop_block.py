from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from courses.region_scope import (
    filter_courses_for_user,
    filter_courses_for_workshop_picker,
    franchisee_course_blocked,
    user_can_view_course,
)


class CourseWorkshopBlockScopeTests(SimpleTestCase):
    def _franchisee(self, pk=42):
        user = MagicMock()
        user.pk = pk
        user.is_authenticated = True
        user.is_superuser = False
        user.user_type_id = 3
        return user

    @patch('courses.region_scope.course_workshop_block_ids', return_value=frozenset({10, 20}))
    @patch('courses.region_scope.get_user_region_ids', return_value=[1])
    def test_course_list_excludes_blocked_courses(self, _regions, _blocks):
        user = self._franchisee()
        qs = MagicMock()
        region_filtered = MagicMock()
        blocked_filtered = MagicMock()
        qs.filter.return_value = region_filtered
        region_filtered.exclude.return_value = blocked_filtered

        result = filter_courses_for_user(qs, user)

        region_filtered.exclude.assert_called_once_with(pk__in={10, 20})
        self.assertIs(result, blocked_filtered)

    @patch('courses.region_scope._filter_courses_by_region')
    @patch('courses.region_scope.filter_courses_for_user')
    def test_workshop_picker_reincludes_existing_course(self, filter_user, filter_region):
        user = self._franchisee()
        base = MagicMock()
        base.model.objects.filter.return_value = MagicMock(name='kept_raw')
        filtered = MagicMock(name='filtered')
        kept = MagicMock(name='kept')
        combined = MagicMock(name='combined')
        filter_user.return_value = filtered
        filter_region.return_value = kept
        (filtered | kept).distinct.return_value = combined

        result = filter_courses_for_workshop_picker(base, user, include_course_ids=[10])

        self.assertIs(result, combined)
        base.model.objects.filter.assert_called_once_with(pk__in={10})

    @patch('courses.region_scope.course_workshop_block_ids', return_value=frozenset({7}))
    def test_franchisee_cannot_view_blocked_course(self, _ids):
        user = self._franchisee()
        course = MagicMock(pk=7, region_id=1)
        self.assertTrue(franchisee_course_blocked(user, course))
        self.assertFalse(user_can_view_course(user, course))
