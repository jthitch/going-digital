"""Helpers for rendering legal pages from the database."""

from website.legal_page_defaults import DEFAULT_LEGAL_PAGES


def get_legal_page_context(page_key):
    """Return template context for a legal page, with DB content or defaults."""
    from website.models import LegalPage

    defaults = DEFAULT_LEGAL_PAGES[page_key]
    page = LegalPage.objects.filter(page_key=page_key).first()
    if page is None:
        return defaults.copy()

    return {
        'page_title': page.page_title,
        'browser_title': page.browser_title,
        'meta_description': page.meta_description,
        'meta_keywords': page.meta_keywords,
        'body': page.body,
    }
