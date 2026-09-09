"""Tests for disk-cached list-card image variants."""
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from PIL import Image

from courses.list_card_images import (
    cached_list_card_image,
    cached_list_card_image_url,
)


class ListCardImageCacheTests(SimpleTestCase):
    def _source(self, name, size):
        media_root = Path(settings.MEDIA_ROOT)
        source_dir = media_root / 'gd_images'
        source_dir.mkdir(parents=True, exist_ok=True)
        source = source_dir / name
        Image.new('RGB', size, color=(20, 80, 140)).save(source, format='JPEG', quality=90)
        return source

    def test_builds_webp_meta_and_reuses_without_pillow(self):
        source = self._source('list-card-test-source.jpg', (1600, 1200))

        with override_settings(GD_LIST_CARD_IMAGE_WIDTH=720, GD_LIST_CARD_IMAGE_QUALITY=72):
            image1 = cached_list_card_image(source, generate=True)
            with mock.patch('courses.list_card_images._image_size') as probe:
                image2 = cached_list_card_image(source, generate=False)
                probe.assert_not_called()

        self.assertTrue(image1.url.startswith(settings.MEDIA_URL))
        self.assertTrue(image1.url.endswith('.webp'))
        self.assertEqual(image1.url, image2.url)
        self.assertEqual(image1.width, 720)
        self.assertEqual(image1.height, 540)
        self.assertEqual(image2.width, 720)
        self.assertEqual(image2.height, 540)

        rel = image1.url[len(settings.MEDIA_URL.rstrip('/')) + 1 :]
        dest = Path(settings.MEDIA_ROOT) / rel
        self.assertTrue(dest.is_file())
        self.assertTrue(dest.with_suffix('.meta.json').is_file())
        with Image.open(dest) as img:
            self.assertEqual(img.format, 'WEBP')
            self.assertEqual(img.size, (720, 540))
        self.assertLess(dest.stat().st_size, source.stat().st_size)

    def test_generate_false_does_not_encode(self):
        source = self._source('list-card-no-encode.jpg', (1600, 1200))
        cache_dir = Path(settings.MEDIA_ROOT) / 'cache' / 'list_cards'
        before = set(cache_dir.glob('*.webp')) if cache_dir.exists() else set()

        with override_settings(GD_LIST_CARD_IMAGE_WIDTH=720, GD_LIST_CARD_IMAGE_QUALITY=72):
            image = cached_list_card_image(source, generate=False)

        self.assertIn('/gd_images/', image.url)
        self.assertNotIn('/cache/list_cards/', image.url)
        after = set(cache_dir.glob('*.webp')) if cache_dir.exists() else set()
        self.assertEqual(before, after)

    def test_portrait_dimensions_match_resized_file(self):
        source = self._source('list-card-test-portrait.jpg', (900, 1500))

        with override_settings(GD_LIST_CARD_IMAGE_WIDTH=720, GD_LIST_CARD_IMAGE_QUALITY=72):
            image = cached_list_card_image(source, generate=True)

        self.assertEqual(image.width, 720)
        self.assertEqual(image.height, 1200)
        self.assertNotEqual(image.height, 960)

    def test_rejects_paths_outside_media_root(self):
        outside = Path(settings.BASE_DIR) / 'list-card-outside.jpg'
        Image.new('RGB', (100, 100), color=(0, 0, 0)).save(outside, format='JPEG')
        try:
            self.assertEqual(cached_list_card_image_url(outside), '')
            self.assertFalse(cached_list_card_image(outside))
        finally:
            outside.unlink(missing_ok=True)
