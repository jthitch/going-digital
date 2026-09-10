"""Tests for list-card image helpers (original uploads, no disk resize)."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from PIL import Image

from courses.list_card_images import (
    cached_list_card_image,
    cached_list_card_image_url,
    schedule_list_card_warm,
)


class ListCardImageTests(SimpleTestCase):
    def _source(self, name, size):
        media_root = Path(settings.MEDIA_ROOT)
        source_dir = media_root / 'gd_images'
        source_dir.mkdir(parents=True, exist_ok=True)
        source = source_dir / name
        Image.new('RGB', size, color=(20, 80, 140)).save(source, format='JPEG', quality=90)
        return source

    def test_returns_original_url_with_fallback_size(self):
        source = self._source('list-card-test-source.jpg', (1600, 1200))
        image = cached_list_card_image(source, fallback_size=(1600, 1200))

        self.assertIn('/gd_images/list-card-test-source.jpg', image.url)
        self.assertNotIn('/cache/list_cards/', image.url)
        self.assertEqual(image.width, 1600)
        self.assertEqual(image.height, 1200)

        cache_dir = Path(settings.MEDIA_ROOT) / 'cache' / 'list_cards'
        self.assertFalse(cache_dir.exists() and any(cache_dir.glob('*.webp')))

    def test_generate_flag_does_not_encode(self):
        source = self._source('list-card-no-encode.jpg', (1600, 1200))
        cache_dir = Path(settings.MEDIA_ROOT) / 'cache' / 'list_cards'
        before = set(cache_dir.glob('*.webp')) if cache_dir.exists() else set()

        image = cached_list_card_image(source, generate=True)

        self.assertIn('/gd_images/', image.url)
        self.assertNotIn('/cache/list_cards/', image.url)
        after = set(cache_dir.glob('*.webp')) if cache_dir.exists() else set()
        self.assertEqual(before, after)

    def test_rejects_paths_outside_media_root(self):
        outside = Path(settings.BASE_DIR) / 'list-card-outside.jpg'
        Image.new('RGB', (100, 100), color=(0, 0, 0)).save(outside, format='JPEG')
        try:
            self.assertEqual(cached_list_card_image_url(outside), '')
            self.assertFalse(cached_list_card_image(outside))
        finally:
            outside.unlink(missing_ok=True)

    def test_warm_is_noop(self):
        source = self._source('list-card-warm.jpg', (800, 600))
        schedule_list_card_warm([source])
        cache_dir = Path(settings.MEDIA_ROOT) / 'cache' / 'list_cards'
        self.assertFalse(cache_dir.exists() and any(cache_dir.glob('*.webp')))
