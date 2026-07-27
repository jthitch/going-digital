from unittest.mock import MagicMock

from django.test import SimpleTestCase

from courses.workshop_admin_list import (
    apply_workshop_custom_date_range,
    is_workshop_changelist_request,
    workshop_changelist_has_custom_date_range,
    workshop_changelist_show_full_history,
)


class WorkshopChangelistScopeTests(SimpleTestCase):
    def test_show_full_history_when_searching(self):
        request = MagicMock(GET={'q': 'landscape'})
        self.assertTrue(workshop_changelist_show_full_history(request))

    def test_default_scope_without_filters(self):
        request = MagicMock(GET={})
        self.assertFalse(workshop_changelist_show_full_history(request))

    def test_show_full_history_for_date_filter_all(self):
        request = MagicMock(GET={'show_all': '1'})
        self.assertTrue(workshop_changelist_show_full_history(request))

    def test_show_full_history_for_course_filter(self):
        request = MagicMock(GET={'course__id__exact': '12'})
        self.assertTrue(workshop_changelist_show_full_history(request))

    def test_show_full_history_for_custom_date_range(self):
        request = MagicMock(GET={'date_from': '2024-01-01'})
        self.assertTrue(workshop_changelist_has_custom_date_range(request))
        self.assertTrue(workshop_changelist_show_full_history(request))

    def test_custom_date_range_keeps_open_dated_rows(self):
        request = MagicMock(GET={'date_from': '2024-01-01', 'date_to': '2024-01-31'})
        queryset = MagicMock()

        apply_workshop_custom_date_range(request, queryset)

        queryset.filter.assert_called_once()
        query_arg = queryset.filter.call_args.args[0]
        query_text = str(query_arg)
        self.assertIn('open_dated', query_text)
        self.assertIn('date__date__gte', query_text)
        self.assertIn('date__date__lte', query_text)
        self.assertNotIn('date__isnull', query_text)

    def test_changelist_detected_from_admin_path(self):
        request = MagicMock(
            path='/admin/courses/workshop/',
            resolver_match=None,
        )
        self.assertTrue(is_workshop_changelist_request(request))
