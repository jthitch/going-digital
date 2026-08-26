from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from courses.location_landings import (
    CityLanding,
    build_city_landings,
    city_slug_for_location,
    clear_location_landing_cache,
    get_indexable_city,
    infer_venue_locality,
)


class CitySlugTests(SimpleTestCase):
    def setUp(self):
        clear_location_landing_cache()

    def test_slugifies_location(self):
        self.assertEqual(city_slug_for_location('Bath'), 'bath')
        self.assertEqual(city_slug_for_location('  South East Scotland '), 'south-east-scotland')
        self.assertEqual(city_slug_for_location(''), '')


class InferVenueLocalityTests(SimpleTestCase):
    def setUp(self):
        clear_location_landing_cache()

    def test_prefers_explicit_location(self):
        venue = SimpleNamespace(location='Bath', venue_address='1 High St, Bristol BS1 1AA')
        self.assertEqual(infer_venue_locality(venue), 'Bath')

    def test_parses_town_from_address(self):
        venue = SimpleNamespace(
            location=None,
            venue_address='WWT Arundel, Mill Road, Arundel, West Sussex, BN18 9PB',
        )
        self.assertEqual(infer_venue_locality(venue), 'Arundel')

    def test_parses_london_from_address(self):
        venue = SimpleNamespace(
            location='',
            venue_address='Franklin-Wilkins Building Stamford Street, London, SE1 9NH',
        )
        self.assertEqual(infer_venue_locality(venue), 'London')

    def test_empty_when_no_data(self):
        venue = SimpleNamespace(location=None, venue_address='')
        self.assertEqual(infer_venue_locality(venue), '')

    def test_skips_instructional_location(self):
        venue = SimpleNamespace(
            location='Historic Winchester (please see joining instructions for full details)',
            venue_address='High Street, Winchester, Hampshire, SO23 9EX',
        )
        self.assertEqual(infer_venue_locality(venue), 'Winchester')


class BuildCityLandingsTests(SimpleTestCase):
    def setUp(self):
        clear_location_landing_cache()

    def test_groups_venues_by_inferred_locality(self):
        venues = [
            SimpleNamespace(pk=1, location='Bath', venue_address=''),
            SimpleNamespace(pk=2, location='bath', venue_address=''),
            SimpleNamespace(
                pk=3,
                location=None,
                venue_address='High Street, York, North Yorkshire, YO1 7HH',
            ),
        ]
        cities = build_city_landings(venues)
        by_slug = {c.slug: c for c in cities}
        self.assertEqual(set(by_slug['bath'].venue_ids), {1, 2})
        self.assertEqual(by_slug['bath'].name, 'Bath')
        self.assertEqual(by_slug['york'].venue_ids, (3,))

    def test_orders_by_display_name(self):
        venues = [
            SimpleNamespace(pk=1, location='York', venue_address=''),
            SimpleNamespace(pk=2, location='Bath', venue_address=''),
            SimpleNamespace(pk=3, location='Manchester', venue_address=''),
        ]
        cities = build_city_landings(venues)
        self.assertEqual([c.name for c in cities], ['Bath', 'Manchester', 'York'])

    def test_get_indexable_city_finds_slug(self):
        fake = [
            CityLanding(slug='bath', name='Bath', venue_ids=(1,)),
            CityLanding(slug='york', name='York', venue_ids=(2,)),
        ]
        with patch('courses.location_landings.indexable_cities', return_value=fake):
            self.assertEqual(get_indexable_city('bath').name, 'Bath')
            self.assertIsNone(get_indexable_city('london'))
            self.assertIsNone(get_indexable_city(''))


class IndexableRegionFilterTests(SimpleTestCase):
    def setUp(self):
        clear_location_landing_cache()

    def test_get_indexable_region_requires_slug(self):
        from courses.location_landings import get_indexable_region

        self.assertIsNone(get_indexable_region(''))

    @patch('courses.location_landings.venues_with_bookable_workshops')
    @patch('courses.location_landings.Region.objects')
    def test_get_indexable_region_checks_bookable_venues(self, region_objects, venues_qs):
        from courses.location_landings import get_indexable_region

        region = SimpleNamespace(pk=3, slug='yorkshire', region_name='Yorkshire')
        region_objects.filter.return_value.exclude.return_value.first.return_value = region
        venues_qs.return_value.filter.return_value.exists.return_value = True

        self.assertIs(get_indexable_region('yorkshire'), region)
        venues_qs.return_value.filter.assert_called_once_with(region_id=3)

    @patch('courses.location_landings.venues_with_bookable_workshops')
    @patch('courses.location_landings.Region.objects')
    def test_get_indexable_region_rejects_thin_region(self, region_objects, venues_qs):
        from courses.location_landings import get_indexable_region

        region = SimpleNamespace(pk=3, slug='yorkshire', region_name='Yorkshire')
        region_objects.filter.return_value.exclude.return_value.first.return_value = region
        venues_qs.return_value.filter.return_value.exists.return_value = False

        self.assertIsNone(get_indexable_region('yorkshire'))
