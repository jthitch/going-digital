from django.test import SimpleTestCase

from courses.admin_changelist import gd_change_list_class


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
