"""Record acceptance of terms and conditions at basket checkout."""

from website.models import LegalPage

from .models import BookingTermsAcceptance


def get_terms_version_timestamp():
    page = LegalPage.objects.filter(page_key=LegalPage.TERMS).first()
    return page.updated_at if page else None


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def record_basket_terms_acceptance(request, *, customer, basket_id, booking_ids):
    """Persist that the purchaser accepted terms before payment."""
    BookingTermsAcceptance.objects.create(
        customer=customer,
        basket_id=basket_id,
        booking_ids=list(booking_ids),
        ip_address=get_client_ip(request),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:500],
        terms_updated_at=get_terms_version_timestamp(),
    )
