from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from django.utils.html import strip_tags

from courses.image_usage import (
    ImageUsage,
    bookable_workshop_q,
    format_usage_lines,
    live_gd_image_filter_q,
)


class FormatUsageLinesTests(SimpleTestCase):
    def test_empty_usages(self):
        self.assertEqual(format_usage_lines([]), '—')

    def test_links_and_truncation(self):
        usages = [
            ImageUsage(area='Course', label='Course: Alpha', admin_url='/admin/a/'),
            ImageUsage(area='Workshop', label='Workshop: Beta', admin_url=''),
            ImageUsage(area='Course', label='Course: Gamma', admin_url='/admin/c/'),
            ImageUsage(area='Course', label='Course: Delta', admin_url='/admin/d/'),
        ]
        html = str(format_usage_lines(usages, max_items=2))
        self.assertIn('Course: Alpha', html)
        self.assertIn('href="/admin/a/"', html)
        self.assertIn('Workshop: Beta', html)
        self.assertIn('+2 more', strip_tags(html))


class LiveFilterExpressionTests(SimpleTestCase):
    def test_live_filter_q_is_combined_exists(self):
        expr = live_gd_image_filter_q(now=timezone.now())
        # Combined OR of three Exists() for course / gallery / legacy workshop.
        self.assertEqual(expr.connector, 'OR')
        self.assertEqual(len(expr.children), 3)

    def test_bookable_workshop_q_requires_active_course(self):
        q = bookable_workshop_q(now=timezone.now())
        text = str(q)
        self.assertIn('course__active', text)
        self.assertIn('active', text)


class BuildUsageMapIntegrationTests(SimpleTestCase):
    """Exercise usage map with patched querysets (no DB writes)."""

    @patch('courses.image_usage.WorkshopGalleryImage.objects')
    @patch('courses.image_usage.Workshop.objects')
    @patch('courses.image_usage.Course.objects')
    def test_course_and_gallery_usage(self, course_objects, workshop_objects, gallery_objects):
        from courses.image_usage import build_gd_image_usage_map

        course = MagicMock(pk=1, course_name='Landscape', image_id=10)
        course_qs = MagicMock()
        course_qs.exclude.return_value = course_qs
        course_qs.filter.return_value = course_qs
        course_qs.only.return_value = [course]
        course_objects.filter.return_value = course_qs

        workshop = MagicMock(pk=5, course_id=1, venue_id=None, image_id=0)
        workshop.course = MagicMock(course_name='Landscape')
        workshop.venue = None

        workshop_qs = MagicMock()
        workshop_qs.select_related.return_value = workshop_qs
        workshop_qs.values.return_value = MagicMock()
        workshop_qs.exclude.return_value = workshop_qs
        workshop_qs.filter.return_value = []
        # iterating workshop_qs for legacy: empty after excludes
        workshop_objects.filter.return_value = workshop_qs

        link = MagicMock(workshop_id=5, image_id=10, workshop=workshop)
        gallery_qs = MagicMock()
        gallery_qs.select_related.return_value = gallery_qs
        gallery_qs.filter.return_value = gallery_qs
        gallery_qs.__iter__ = lambda self: iter([link])
        gallery_objects.filter.return_value = gallery_qs

        usage_map = build_gd_image_usage_map([10], now=timezone.now())
        self.assertIn(10, usage_map)
        labels = [u.label for u in usage_map[10]]
        self.assertTrue(any(label.startswith('Course:') for label in labels))
        self.assertTrue(any(label.startswith('Workshop:') for label in labels))

    @patch('courses.image_usage.WorkshopGalleryImage.objects')
    @patch('courses.image_usage.Workshop.objects')
    @patch('courses.image_usage.Course.objects')
    def test_inactive_course_image_excluded_when_filtering_ids(
        self, course_objects, workshop_objects, gallery_objects
    ):
        from courses.image_usage import build_gd_image_usage_map

        # Course.objects.filter(active=True, ...) returns empty for image 99
        course_qs = MagicMock()
        course_qs.exclude.return_value = course_qs
        course_qs.filter.return_value = course_qs
        course_qs.only.return_value = []
        course_objects.filter.return_value = course_qs

        workshop_qs = MagicMock()
        workshop_qs.select_related.return_value = workshop_qs
        workshop_qs.values.return_value = MagicMock()
        workshop_qs.exclude.return_value = workshop_qs
        workshop_qs.filter.return_value = []
        workshop_objects.filter.return_value = workshop_qs

        gallery_qs = MagicMock()
        gallery_qs.select_related.return_value = gallery_qs
        gallery_qs.filter.return_value = gallery_qs
        gallery_qs.__iter__ = lambda self: iter([])
        gallery_objects.filter.return_value = gallery_qs

        usage_map = build_gd_image_usage_map([99], now=timezone.now() + timedelta(days=1))
        self.assertEqual(usage_map, {})
