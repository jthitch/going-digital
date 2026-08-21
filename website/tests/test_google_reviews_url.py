from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from website.google_reviews import _build_reviews_url, _build_write_review_url


class BuildReviewsUrlTests(SimpleTestCase):
    def test_prefers_place_id_reviews_page(self):
        config = SimpleNamespace(
            google_place_id='ChIJExamplePlaceId',
            reviews_url='https://www.google.com/search?q=test#lrd=abc',
        )
        with patch('website.google_reviews._google_cid_for_config', return_value='123'):
            url = _build_reviews_url(config)
        self.assertEqual(
            url,
            'https://search.google.com/local/reviews?placeid=ChIJExamplePlaceId',
        )

    def test_write_review_uses_place_id(self):
        config = SimpleNamespace(
            google_place_id='ChIJExamplePlaceId',
            reviews_url='https://example.com/reviews',
        )
        url = _build_write_review_url(config)
        self.assertEqual(
            url,
            'https://search.google.com/local/writereview?placeid=ChIJExamplePlaceId',
        )

    def test_falls_back_to_maps_cid(self):
        config = SimpleNamespace(
            google_place_id='',
            reviews_url='https://www.google.com/search?q=test#lrd=abc',
        )
        with patch('website.google_reviews._google_cid_for_config', return_value='999'):
            with patch('website.google_reviews._resolve_place_id', return_value=''):
                url = _build_reviews_url(config, api_key='key')
        self.assertEqual(url, 'https://www.google.com/maps?cid=999')

    def test_falls_back_to_admin_url(self):
        config = SimpleNamespace(
            google_place_id='',
            reviews_url='https://example.com/reviews',
        )
        with patch('website.google_reviews._google_cid_for_config', return_value=''):
            with patch('website.google_reviews._resolve_place_id', return_value=''):
                url = _build_reviews_url(config, api_key='key')
        self.assertEqual(url, 'https://example.com/reviews')
