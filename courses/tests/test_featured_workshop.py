"""Tests for featured workshop resolution on course detail pages."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from courses.workshop_querysets import (
    instances_for_workshop_param,
    matching_workshop,
    resolve_featured_workshop,
)


class MatchingWorkshopTests(SimpleTestCase):
    def test_none_without_id(self):
        a = SimpleNamespace(pk=10)
        self.assertIsNone(matching_workshop([a], None))
        self.assertIsNone(matching_workshop([a], ''))
        self.assertIsNone(matching_workshop([a], 'x'))

    def test_matches_pk(self):
        a = SimpleNamespace(pk=10)
        b = SimpleNamespace(pk=20)
        self.assertIs(matching_workshop([a, b], 20), b)
        self.assertIs(matching_workshop([a, b], '20'), b)
        self.assertIsNone(matching_workshop([a, b], 99))


class ResolveFeaturedWorkshopTests(SimpleTestCase):
    def test_returns_none_for_empty_list(self):
        self.assertIsNone(resolve_featured_workshop([]))
        self.assertIsNone(resolve_featured_workshop(None))

    def test_defaults_to_first(self):
        a = SimpleNamespace(pk=10)
        b = SimpleNamespace(pk=20)
        self.assertIs(resolve_featured_workshop([a, b]), a)

    def test_selects_matching_workshop_id(self):
        a = SimpleNamespace(pk=10)
        b = SimpleNamespace(pk=20)
        self.assertIs(resolve_featured_workshop([a, b], workshop_id=20), b)
        self.assertIs(resolve_featured_workshop([a, b], workshop_id='20'), b)

    def test_unknown_id_falls_back_to_first(self):
        a = SimpleNamespace(pk=10)
        b = SimpleNamespace(pk=20)
        self.assertIs(resolve_featured_workshop([a, b], workshop_id=99), a)
        self.assertIs(resolve_featured_workshop([a, b], workshop_id='x'), a)


class InstancesForWorkshopParamTests(SimpleTestCase):
    def test_no_param_keeps_full_list(self):
        a = SimpleNamespace(pk=10)
        b = SimpleNamespace(pk=20)
        listed, featured = instances_for_workshop_param([a, b])
        self.assertEqual(listed, [a, b])
        self.assertIs(featured, a)

    def test_matching_param_returns_only_that_workshop(self):
        a = SimpleNamespace(pk=10)
        b = SimpleNamespace(pk=20)
        listed, featured = instances_for_workshop_param([a, b], workshop_id=20)
        self.assertEqual(listed, [b])
        self.assertIs(featured, b)

    def test_unknown_param_keeps_full_list(self):
        a = SimpleNamespace(pk=10)
        b = SimpleNamespace(pk=20)
        listed, featured = instances_for_workshop_param([a, b], workshop_id=99)
        self.assertEqual(listed, [a, b])
        self.assertIs(featured, a)
