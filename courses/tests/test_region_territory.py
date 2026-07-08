from django.test import SimpleTestCase

from courses.region_territory import (
    _normalize_region_label,
    _parse_coordinates,
    load_territory_polygons,
)


class RegionTerritoryTests(SimpleTestCase):
    def test_normalize_region_label(self):
        self.assertEqual(_normalize_region_label('Mid & North Wales'), 'mid and north wales')
        self.assertEqual(_normalize_region_label('South-East'), 'south east')

    def test_parse_coordinates(self):
        ring = _parse_coordinates('-1.5,52.5,0 0.0,53.0,0')
        self.assertEqual(ring, [[52.5, -1.5], [53.0, 0.0]])

    def test_load_territory_polygons(self):
        polygons = load_territory_polygons()
        self.assertGreaterEqual(len(polygons), 10)
        cotswolds = next((p for p in polygons if p['kml_name'] == 'Cotswolds'), None)
        self.assertIsNotNone(cotswolds)
        self.assertGreater(len(cotswolds['coordinates']), 3)
