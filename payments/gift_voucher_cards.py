"""Gift voucher card download/email helpers."""
from urllib.parse import unquote

from django.http import Http404

from bookings.gift_voucher_basket import get_basket, get_voucher_for_basket_index
from payments.models import Payment
from website.gift_card_render import render_gift_card_png
from website.models import GiftCardDesign


def _is_stripe_session_placeholder(session_id):
    if not session_id:
        return True
    decoded = unquote(session_id)
    return decoded == '{CHECKOUT_SESSION_ID}' or '{CHECKOUT_SESSION_ID}' in decoded


def verify_gift_voucher_session_access(session_id, basket_id):
    """True when session_id is a paid checkout for this gift voucher basket."""
    if _is_stripe_session_placeholder(session_id):
        return False
    payment = Payment.objects.filter(stripe_id=session_id, status='succeeded').first()
    if not payment:
        return False
    metadata = dict(payment.metadata or {})
    return str(metadata.get('gift_voucher_basket_id')) == str(basket_id)


def get_active_gift_card_designs():
    return GiftCardDesign.objects.filter(is_active=True).order_by('display_order', 'name')


def get_gift_card_design(design_id):
    design = GiftCardDesign.objects.filter(pk=design_id, is_active=True).first()
    if not design:
        raise Http404('Gift card design not found.')
    return design


def render_gift_voucher_card(basket_id, voucher_index, design_id):
    """Return PNG bytes for one voucher in a paid basket."""
    basket = get_basket(basket_id)
    if not basket or basket.get('basket_data', {}).get('type') != 'gift_voucher':
        raise Http404('Gift voucher order not found.')

    voucher = get_voucher_for_basket_index(basket_id, voucher_index)
    if not voucher:
        raise Http404('Voucher not found.')

    design = get_gift_card_design(design_id)
    code, value, expiry = voucher
    return render_gift_card_png(
        design,
        basket['basket_data'],
        code,
        value,
        expiry,
    ), code
