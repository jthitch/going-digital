from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from courses.search_location import (
    ResolvedSearchPlace,
    _looks_like_full_postcode,
    _looks_like_outcode,
    _resolve_via_nominatim,
    resolve_search_place,
)


class PostcodeDetectionTests(SimpleTestCase):
    def test_full_postcode(self):
        self.assertTrue(_looks_like_full_postcode('BS8 1TH'))
        self.assertTrue(_looks_like_full_postcode('bs81th'))
        self.assertFalse(_looks_like_full_postcode('BS8'))
        self.assertFalse(_looks_like_full_postcode('Bath'))

    def test_outcode(self):
        self.assertTrue(_looks_like_outcode('BS8'))
        self.assertTrue(_looks_like_outcode('SW1A'))
        self.assertFalse(_looks_like_outcode('BS8 1TH'))
        self.assertFalse(_looks_like_outcode('Bath'))


class ResolveSearchPlaceTests(SimpleTestCase):
    @patch('courses.search_location._resolve_via_nominatim', return_value=None)
    @patch('courses.search_location._resolve_from_venues', return_value=None)
    @patch('courses.search_location._resolve_outcode', return_value=None)
    @patch('courses.search_location._resolve_postcode')
    def test_prefers_full_postcode(self, postcode, outcode, venues, nominatim):
        postcode.return_value = ResolvedSearchPlace(51.45, -2.6, 'BS8 1TH', 'postcode')
        place = resolve_search_place('BS8 1TH')
        self.assertEqual(place.source, 'postcode')
        postcode.assert_called_once()
        outcode.assert_not_called()
        venues.assert_not_called()
        nominatim.assert_not_called()

    @patch('courses.search_location._resolve_via_nominatim', return_value=None)
    @patch('courses.search_location._resolve_from_venues')
    @patch('courses.search_location._resolve_outcode', return_value=None)
    def test_falls_back_to_venues_then_stops(self, outcode, venues, nominatim):
        venues.return_value = ResolvedSearchPlace(51.38, -2.36, 'Bath', 'venue')
        place = resolve_search_place('Bath')
        self.assertEqual(place.label, 'Bath')
        self.assertEqual(place.source, 'venue')
        nominatim.assert_not_called()

    @patch('courses.search_location._resolve_via_nominatim')
    @patch('courses.search_location._resolve_from_venues', return_value=None)
    @patch('courses.search_location._resolve_outcode', return_value=None)
    def test_nominatim_fallback_for_unknown_town(self, outcode, venues, nominatim):
        nominatim.return_value = ResolvedSearchPlace(50.72, -1.88, 'Poole', 'geocode')
        place = resolve_search_place('Poole')
        self.assertEqual(place.source, 'geocode')
        nominatim.assert_called_once_with('Poole')

    def test_blank_query(self):
        self.assertIsNone(resolve_search_place(''))
        self.assertIsNone(resolve_search_place('  '))


class NominatimGuardTests(SimpleTestCase):
    @patch('courses.search_location._cache_get', return_value=None)
    def test_skips_topic_keywords(self, _cache):
        self.assertIsNone(_resolve_via_nominatim('portrait'))
        self.assertIsNone(_resolve_via_nominatim('beginner portrait'))
