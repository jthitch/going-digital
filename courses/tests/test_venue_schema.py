from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from courses.venue_schema import extract_uk_postcode, venue_postal_address, venue_place_schema


class ExtractUkPostcodeTests(SimpleTestCase):
    def test_finds_postcode_in_address(self):
        self.assertEqual(
            extract_uk_postcode('12 High Street, Bristol BS8 1TH'),
            'BS8 1TH',
        )

    def test_normalises_spacing(self):
        self.assertEqual(extract_uk_postcode('Somewhere SW1A1AA UK'), 'SW1A 1AA')

    def test_empty_when_missing(self):
        self.assertEqual(extract_uk_postcode('12 High Street, Bristol'), '')


class VenuePostalAddressTests(SimpleTestCase):
    @patch('courses.venue_schema._county_name_by_id', return_value={7: 'Somerset'})
    def test_omits_empty_and_fills_derived_fields(self, _counties):
        venue = MagicMock()
        venue.venue_address = 'The Mill, Station Road, Bath BA1 2AB'
        venue.location = 'Bath'
        venue.county_id = 7

        address = venue_postal_address(venue)

        self.assertEqual(address['@type'], 'PostalAddress')
        self.assertEqual(address['streetAddress'], 'The Mill, Station Road, Bath BA1 2AB')
        self.assertEqual(address['addressLocality'], 'Bath')
        self.assertEqual(address['addressRegion'], 'Somerset')
        self.assertEqual(address['postalCode'], 'BA1 2AB')
        self.assertEqual(address['addressCountry'], 'GB')

    @patch('courses.venue_schema._county_name_by_id', return_value={})
    def test_skips_missing_county(self, _counties):
        venue = MagicMock()
        venue.venue_address = 'Somewhere'
        venue.location = ''
        venue.county_id = 99

        address = venue_postal_address(venue)

        self.assertNotIn('addressRegion', address)
        self.assertNotIn('addressLocality', address)
        self.assertNotIn('postalCode', address)

    @patch('courses.venue_schema._county_name_by_id', return_value={3: 'North Yorkshire'})
    def test_place_includes_geo(self, _counties):
        venue = MagicMock()
        venue.venue_name = 'Test Venue'
        venue.venue_address = '1 Road, York YO1 7HH'
        venue.location = 'York'
        venue.latitude = 53.96
        venue.longitude = -1.08
        venue.county_id = 3

        place = venue_place_schema(venue)
        self.assertEqual(place['geo']['latitude'], 53.96)
        self.assertEqual(place['address']['postalCode'], 'YO1 7HH')
        self.assertEqual(place['address']['addressRegion'], 'North Yorkshire')
