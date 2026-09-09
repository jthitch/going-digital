"""Tests for disk-cached list-card image variants."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from PIL import Image

from courses.list_card_images import cached_list_card_image, cached_list_card_image_url


class ListCardImageCacheTests(SimpleTestCase):
    def test_builds_webp_under_media_cache_and_reuses_it(self):
        media_root = Path(settings.MEDIA_ROOT)
        source_dir = media_root / 'gd_images'
        source_dir.mkdir(parents=True, exist_ok=True)
        source = source_dir / 'list-card-test-source.jpg'
        Image.new('RGB', (1600, 1200), color=(20, 80, 140)).save(source, format='JPEG', quality=90)

        with override_settings(GD_LIST_CARD_IMAGE_WIDTH=720, GD_LIST_CARD_IMAGE_QUALITY=72):
            image1 = cached_list_card_image(source)
            image2 = cached_list_card_image(source)

        self.assertTrue(image1.url.startswith(settings.MEDIA_URL))
        self.assertTrue(image1.url.endswith('.webp'))
        self.assertEqual(image1.url, image2.url)
        # Landscape 1600x1200 -> 720x540, not a hardcoded 3:4 (720x960).
        self.assertEqual(image1.width, 720)
        self.assertEqual(image1.height, 540)
        self.assertEqual(image2.width, 720)
        self.assertEqual(image2.height, 540)

        rel = image1.url[len(settings.MEDIA_URL.rstrip('/')) + 1 :]
        dest = media_root / rel
        self.assertTrue(dest.is_file())
        with Image.open(dest) as img:
            self.assertEqual(img.format, 'WEBP')
            self.assertEqual(img.width, 720)
            self.assertEqual(img.height, 540)

        # Cache file should be meaningfully smaller than the full-size source.
        self.assertLess(dest.stat().st_size, source.stat().st_size)

    def test_portrait_dimensions_match_resized_file(self):
        media_root = Path(settings.MEDIA_ROOT)
        source_dir = media_root / 'gd_images'
        source_dir.mkdir(parents=True, exist_ok=True)
        source = source_dir / 'list-card-test-portrait.jpg'
        Image.new('RGB', (900, 1500), color=(140, 40, 20)).save(source, format='JPEG', quality=90)

        with override_settings(GD_LIST_CARD_IMAGE_WIDTH=720, GD_LIST_CARD_IMAGE_QUALITY=72):
            image = cached_list_card_image(source)

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
