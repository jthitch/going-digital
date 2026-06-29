"""Template context for website-wide UI."""
from django.templatetags.static import static


def google_reviews(request):
    """Live Google rating badge for hero, course pages, etc."""
    try:
        from website.google_reviews import get_google_reviews_display

        return {'google_reviews': get_google_reviews_display()}
    except Exception:
        return {'google_reviews': None}


def _default_newsletter_modal_settings():
    return {
        'image_url': static('img/newsletter/man-in-shaddow-newsletter-signup.jpg'),
        'desktop_position': '85% 50%',
        'mobile_position': '50% 25%',
        'desktop_bg_size': '100% 100%, cover',
        'mobile_bg_size': '100% 100%, cover',
    }


def newsletter_modal(request):
    """Newsletter popup image URL and background focal point for all public pages."""
    defaults = _default_newsletter_modal_settings()
    try:
        from website.models import NewsletterModalSettings

        settings = NewsletterModalSettings.objects.first()
    except Exception:
        return {'newsletter_modal_settings': defaults}

    if not settings:
        return {'newsletter_modal_settings': defaults}

    image_url = settings.image.url if settings.image else defaults['image_url']
    return {
        'newsletter_modal_settings': {
            'image_url': image_url,
            'desktop_position': settings.desktop_background_position,
            'mobile_position': settings.mobile_background_position,
            'desktop_bg_size': settings.desktop_background_size,
            'mobile_bg_size': settings.mobile_background_size,
        },
    }
