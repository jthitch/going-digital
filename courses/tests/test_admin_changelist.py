from datetime import date
from unittest.mock import MagicMock

from django.db.models import Q
from django.test import SimpleTestCase

from courses.admin_changelist import (
    CHANGE_LIST_DATE_RANGE_PARAMS,
    SearchFirstChangeListMixin,
    apply_changelist_date_range,
    changelist_has_custom_date_range,
    gd_change_list_class,
    parse_changelist_date_range,
)


class GdChangeListExtraParamsTests(SimpleTestCase):
    def test_strips_custom_params_from_filter_validation(self):
        cl_class = gd_change_list_class(('date_from', 'date_to', 'show_all'))
        changelist = cl_class.__new__(cl_class)
        params = {
            'date_from': '2024-01-01',
            'date_to': '2024-12-31',
            'show_all': '1',
            'active': '1',
        }
        filtered = changelist.get_filters_params(params.copy())
        self.assertNotIn('date_from', filtered)
        self.assertNotIn('date_to', filtered)
        self.assertNotIn('show_all', filtered)
        self.assertEqual(filtered.get('active'), '1')


class ChangelistDateRangeHelperTests(SimpleTestCase):
    def test_parse_swaps_inverted_range(self):
        request = MagicMock(GET={'date_from': '2024-06-01', 'date_to': '2024-01-01'})
        date_from, date_to = parse_changelist_date_range(request)
        self.assertEqual(date_from, date(2024, 1, 1))
        self.assertEqual(date_to, date(2024, 6, 1))

    def test_has_custom_date_range(self):
        self.assertFalse(changelist_has_custom_date_range(MagicMock(GET={})))
        self.assertTrue(
            changelist_has_custom_date_range(MagicMock(GET={'date_from': '2024-01-01'}))
        )

    def test_apply_filters_field_lookups(self):
        request = MagicMock(GET={'date_from': '2024-01-01', 'date_to': '2024-01-31'})
        queryset = MagicMock()
        apply_changelist_date_range(request, queryset, field='issue_date')
        queryset.filter.assert_called_once()
        query_text = str(queryset.filter.call_args.args[0])
        self.assertIn('issue_date__gte', query_text)
        self.assertIn('issue_date__lte', query_text)

    def test_apply_or_q(self):
        request = MagicMock(GET={'date_from': '2024-01-01'})
        queryset = MagicMock()
        apply_changelist_date_range(
            request, queryset, field='date__date', or_q=Q(open_dated=1),
        )
        query_text = str(queryset.filter.call_args.args[0])
        self.assertIn('open_dated', query_text)
        self.assertIn('date__date__gte', query_text)

    def test_mixin_merges_date_range_params(self):
        class Admin(SearchFirstChangeListMixin):
            gd_changelist_extra_params = ('show_all',)
            gd_changelist_show_date_range = True

        admin = Admin()
        self.assertEqual(
            admin.resolved_gd_changelist_extra_params(),
            ('show_all', *CHANGE_LIST_DATE_RANGE_PARAMS),
        )
        self.assertEqual(
            admin.resolved_gd_changelist_form_field_params(),
            CHANGE_LIST_DATE_RANGE_PARAMS,
        )
