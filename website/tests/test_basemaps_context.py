from django.test import RequestFactory, SimpleTestCase, override_settings

from website.context_processors import basemaps


class BasemapsContextTests(SimpleTestCase):
    @override_settings(BASEMAPS_API_KEY='test-carto-key')
    def test_exposes_api_key(self):
        request = RequestFactory().get('/')
        self.assertEqual(basemaps(request), {'basemaps_api_key': 'test-carto-key'})

    @override_settings(BASEMAPS_API_KEY='')
    def test_empty_when_unset(self):
        request = RequestFactory().get('/')
        self.assertEqual(basemaps(request), {'basemaps_api_key': ''})
