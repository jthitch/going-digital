from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from courses.search_location import ResolvedSearchPlace
from courses.venue_list import (
    DEFAULT_NEAR_RADIUS_MILES,
    OTHER_REGION_LABEL,
    apply_near_me_to_workshop_queryset,
    clamp_near_radius,
    filter_venues_by_search,
    filter_venues_near,
    group_venues_by_region,
    haversine_miles,
    nearby_venue_ids,
    parse_near_me,
)
from courses.views import VenueListView


class VenueListHelpersTests(SimpleTestCase):
    def test_filter_skips_blank_search(self):
        qs = MagicMock(name='qs')
        self.assertIs(filter_venues_by_search(qs, '  '), qs)
        qs.filter.assert_not_called()

    def test_filter_matches_name_town_address_and_region(self):
        qs = MagicMock(name='qs')
        filtered = MagicMock(name='filtered')
        qs.filter.return_value = filtered
        with patch('courses.venue_list.Region.objects') as region_objects:
            region_objects.filter.return_value.values_list.return_value = [5]

            result = filter_venues_by_search(qs, 'Bath')

        self.assertIs(result, filtered)
        qs.filter.assert_called_once()
        q_obj = qs.filter.call_args.args[0]
        self.assertIn('venue_name__icontains', str(q_obj))
        region_objects.filter.assert_called_once_with(region_name__icontains='Bath')

    def test_group_venues_by_region_orders_and_buckets_unknown(self):
        venues = [
            SimpleNamespace(region_id=2, venue_name='Zulu Studio'),
            SimpleNamespace(region_id=1, venue_name='Alpha Hall'),
            SimpleNamespace(region_id=1, venue_name='Beta Hall'),
            SimpleNamespace(region_id=None, venue_name='Orphan'),
            SimpleNamespace(region_id=99, venue_name='Missing Region'),
        ]
        region_rows = [
            SimpleNamespace(id=1, region_name='South West'),
            SimpleNamespace(id=2, region_name='London'),
        ]
        with patch('courses.venue_list.Region.objects') as region_objects:
            region_objects.filter.return_value = region_rows
            groups = group_venues_by_region(venues)

        self.assertEqual(
            [g['name'] for g in groups],
            ['London', 'South West', OTHER_REGION_LABEL],
        )
        self.assertEqual(
            [v.venue_name for v in groups[1]['venues']],
            ['Alpha Hall', 'Beta Hall'],
        )
        self.assertEqual(
            {v.venue_name for v in groups[2]['venues']},
            {'Orphan', 'Missing Region'},
        )

    def test_haversine_known_distance(self):
        # Roughly London → Brighton ~47 miles
        distance = haversine_miles(51.5074, -0.1278, 50.8225, -0.1372)
        self.assertTrue(45 <= distance <= 50)

    def test_clamp_near_radius(self):
        self.assertEqual(clamp_near_radius(None), DEFAULT_NEAR_RADIUS_MILES)
        self.assertEqual(clamp_near_radius('25'), 25)
        self.assertEqual(clamp_near_radius('27'), 25)
        self.assertEqual(clamp_near_radius('3'), 5)
        self.assertEqual(clamp_near_radius('999'), 100)

    def test_parse_near_me(self):
        lat, lng, radius = parse_near_me({'lat': '51.5', 'lng': '-0.12', 'radius': '40'})
        self.assertAlmostEqual(lat, 51.5)
        self.assertAlmostEqual(lng, -0.12)
        self.assertEqual(radius, 40)

        lat, lng, radius = parse_near_me({'radius': '10'})
        self.assertIsNone(lat)
        self.assertIsNone(lng)
        self.assertEqual(radius, 10)

    def test_filter_venues_near_sorts_and_excludes(self):
        venues = [
            SimpleNamespace(venue_name='Far', latitude=55.0, longitude=-3.0),
            SimpleNamespace(venue_name='Near B', latitude=51.51, longitude=-0.12),
            SimpleNamespace(venue_name='Near A', latitude=51.508, longitude=-0.128),
            SimpleNamespace(venue_name='No coords', latitude=None, longitude=None),
        ]
        nearby = filter_venues_near(
            venues,
            lat=51.5074,
            lng=-0.1278,
            radius_miles=25,
        )
        self.assertEqual([v.venue_name for v in nearby], ['Near A', 'Near B'])
        self.assertTrue(nearby[0].distance_miles <= nearby[1].distance_miles)

    def test_nearby_venue_ids_empty_candidates(self):
        self.assertEqual(
            nearby_venue_ids(lat=51.5, lng=-0.1, radius_miles=25, venue_ids=[]),
            [],
        )

    def test_apply_near_me_to_workshop_queryset(self):
        qs = MagicMock(name='qs')
        excluded = MagicMock(name='excluded')
        filtered = MagicMock(name='filtered')
        qs.exclude.return_value = excluded
        excluded.values_list.return_value.distinct.return_value = [10, 20]
        qs.filter.return_value = filtered

        with patch('courses.venue_list.nearby_venue_ids', return_value=[10]) as near_ids:
            result = apply_near_me_to_workshop_queryset(
                qs, lat=51.5, lng=-0.1, radius_miles=25,
            )

        near_ids.assert_called_once_with(
            lat=51.5, lng=-0.1, radius_miles=25, venue_ids=[10, 20],
        )
        qs.filter.assert_called_once_with(venue_id__in=[10])
        self.assertIs(result, filtered)

    def test_apply_near_me_none_nearby(self):
        qs = MagicMock(name='qs')
        excluded = MagicMock(name='excluded')
        empty = MagicMock(name='empty')
        qs.exclude.return_value = excluded
        excluded.values_list.return_value.distinct.return_value = [10]
        qs.none.return_value = empty

        with patch('courses.venue_list.nearby_venue_ids', return_value=[]):
            result = apply_near_me_to_workshop_queryset(
                qs, lat=51.5, lng=-0.1, radius_miles=5,
            )

        self.assertIs(result, empty)
        qs.filter.assert_not_called()


class VenueListPlaceSearchTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _queryset_mocks(self):
        qs = MagicMock(name='public_qs')
        qs.prefetch_related.return_value = qs
        qs.order_by.return_value = qs
        return qs

    @patch('courses.venue_list.filter_venues_by_search')
    @patch('courses.venue_list.public_venues_queryset')
    @patch('courses.search_location.resolve_search_place')
    def test_place_query_skips_text_filter(self, resolve_place, public_qs, text_filter):
        place = ResolvedSearchPlace(51.38, -2.36, 'Bath', 'venue')
        resolve_place.return_value = place
        public_qs.return_value = self._queryset_mocks()

        request = self.factory.get('/venues/', {'q': 'Bath'})
        view = VenueListView()
        view.setup(request)
        view.get_queryset()

        resolve_place.assert_called_once_with('Bath')
        text_filter.assert_not_called()
        self.assertEqual(view.near_lat, 51.38)
        self.assertEqual(view.near_lng, -2.36)
        self.assertFalse(view.near_me_active)
        self.assertIs(view.resolved_place, place)

    @patch('courses.venue_list.filter_venues_by_search')
    @patch('courses.venue_list.public_venues_queryset')
    @patch('courses.search_location.resolve_search_place', return_value=None)
    def test_non_place_query_uses_text_filter(self, resolve_place, public_qs, text_filter):
        base_qs = self._queryset_mocks()
        public_qs.return_value = base_qs
        text_filter.return_value = base_qs

        request = self.factory.get('/venues/', {'q': 'studio lighting'})
        view = VenueListView()
        view.setup(request)
        view.get_queryset()

        resolve_place.assert_called_once_with('studio lighting')
        text_filter.assert_called_once_with(base_qs, 'studio lighting')
        self.assertIsNone(view.resolved_place)

    @patch('courses.venue_list.filter_venues_by_search')
    @patch('courses.venue_list.public_venues_queryset')
    @patch('courses.search_location.resolve_search_place')
    def test_browser_near_me_wins_over_place_resolve(
        self, resolve_place, public_qs, text_filter,
    ):
        base_qs = self._queryset_mocks()
        public_qs.return_value = base_qs
        text_filter.return_value = base_qs

        request = self.factory.get('/venues/', {
            'q': 'Bath',
            'lat': '51.5',
            'lng': '-0.1',
            'radius': '20',
        })
        view = VenueListView()
        view.setup(request)
        view.get_queryset()

        resolve_place.assert_not_called()
        text_filter.assert_called_once_with(base_qs, 'Bath')
        self.assertTrue(view.near_me_active)
        self.assertAlmostEqual(view.near_lat, 51.5)
        self.assertAlmostEqual(view.near_lng, -0.1)
