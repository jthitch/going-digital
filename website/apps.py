from django.apps import AppConfig


class WebsiteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'website'
    verbose_name = 'Website'

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from website.models import GoogleReviewHighlight, GoogleReviewsSettings

        def clear_google_reviews_cache(sender, instance, **kwargs):
            from website.google_reviews import invalidate_google_reviews_cache

            place_id = ''
            if isinstance(instance, GoogleReviewsSettings):
                place_id = instance.google_place_id
            elif isinstance(instance, GoogleReviewHighlight):
                settings_obj = GoogleReviewsSettings.objects.first()
                place_id = settings_obj.google_place_id if settings_obj else ''
            invalidate_google_reviews_cache(place_id=place_id)

        post_save.connect(clear_google_reviews_cache, sender=GoogleReviewsSettings)
        post_save.connect(clear_google_reviews_cache, sender=GoogleReviewHighlight)
        post_delete.connect(clear_google_reviews_cache, sender=GoogleReviewHighlight)