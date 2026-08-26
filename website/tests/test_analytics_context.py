from django.test import RequestFactory, SimpleTestCase, override_settings

from website.context_processors import analytics


class AnalyticsContextTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(GTM_CONTAINER_ID='GTM-TEST123')
    def test_exposes_gtm_container_id(self):
        request = self.factory.get('/')
        self.assertEqual(analytics(request)['gtm_container_id'], 'GTM-TEST123')

    @override_settings(GTM_CONTAINER_ID='')
    def test_empty_when_unset(self):
        request = self.factory.get('/')
        self.assertEqual(analytics(request)['gtm_container_id'], '')
