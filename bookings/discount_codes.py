"""Franchisee/admin promotional discount codes (fixed £ or %)."""
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from bookings.models import DiscountCode
from courses.region_scope import filter_workshops_for_user, user_has_full_region_access

STRIPE_GBP_MINIMUM = Decimal('0.30')
MONEY_QUANT = Decimal('0.01')


def get_discount_code_by_code(code):
    code = (code or '').strip().upper()
    if not code:
        return None
    return DiscountCode.objects.filter(code__iexact=code).prefetch_related('workshops').first()


def filter_discount_codes_for_user(queryset, user):
    if user_has_full_region_access(user):
        return queryset
    return queryset.filter(created_by=user)


def workshops_queryset_for_discount_admin(user):
    from courses.models import Workshop

    qs = Workshop.objects.select_related('course', 'venue').order_by('-date', 'id')
    return filter_workshops_for_user(qs, user)


def validate_discount_code_active(discount_code):
    if not discount_code:
        raise ValidationError('Discount code not found.')
    if not discount_code.is_active:
        raise ValidationError('This discount code is not active.')
    today = timezone.now().date()
    if discount_code.expiry_date and discount_code.expiry_date < today:
        raise ValidationError('This discount code has expired.')
    return discount_code


def discount_code_applies_to_workshop(discount_code, workshop):
    if not discount_code or not workshop:
        return False
    return discount_code.workshops.filter(pk=workshop.pk).exists()


def calculate_discount_amount(discount_code, eligible_total):
    eligible_total = Decimal(str(eligible_total or 0))
    if eligible_total <= 0:
        return Decimal('0.00')
    amount = Decimal(str(discount_code.amount or 0))
    if discount_code.discount_type == DiscountCode.DISCOUNT_PERCENT:
        discount = (eligible_total * amount / Decimal('100')).quantize(
            MONEY_QUANT, rounding=ROUND_HALF_UP
        )
    else:
        discount = amount
    return min(discount, eligible_total).quantize(MONEY_QUANT)


def eligible_workshop_ids_for_code(discount_code, workshops_by_id):
    allowed = set(discount_code.workshops.values_list('pk', flat=True))
    return {wid for wid in workshops_by_id if wid in allowed}


def validate_discount_code_for_basket(discount_code, workshops_by_id, basket_items):
    validate_discount_code_active(discount_code)
    allowed = eligible_workshop_ids_for_code(discount_code, workshops_by_id)
    if not allowed:
        raise ValidationError('This discount code is not valid for any courses in your basket.')

    eligible_total = Decimal('0.00')
    for item in basket_items:
        workshop = workshops_by_id.get(item['workshop_id'])
        if not workshop or workshop.pk not in allowed:
            continue
        qty = int(item.get('quantity') or 1)
        eligible_total += Decimal(str(workshop.price)) * qty

    if eligible_total <= 0:
        raise ValidationError('This discount code is not valid for any courses in your basket.')

    discount = calculate_discount_amount(discount_code, eligible_total)
    if discount <= 0:
        raise ValidationError('This discount code does not reduce the basket total.')

    amount_due_eligible = eligible_total - discount
    if Decimal('0') < amount_due_eligible < STRIPE_GBP_MINIMUM:
        raise ValidationError(
            f'The remaining balance (£{amount_due_eligible:.2f}) is below the minimum card payment '
            f'(£{STRIPE_GBP_MINIMUM:.2f}).'
        )
    return discount, allowed


def validate_discount_code_for_workshop(discount_code, workshop):
    validate_discount_code_active(discount_code)
    if not discount_code_applies_to_workshop(discount_code, workshop):
        raise ValidationError('This discount code is not valid for this workshop.')
    return discount_code


def apply_discount_code_to_booking(booking, code):
    """Validate discount code and update a single booking's pricing."""
    discount_code = get_discount_code_by_code(code)
    validate_discount_code_for_workshop(discount_code, booking.workshop)

    list_price = Decimal(str(booking.list_price or booking.workshop.price))
    discount = calculate_discount_amount(discount_code, list_price)
    price_paid = list_price - discount

    if Decimal('0') < price_paid < STRIPE_GBP_MINIMUM:
        raise ValidationError(
            f'The remaining balance (£{price_paid:.2f}) is below the minimum card payment '
            f'(£{STRIPE_GBP_MINIMUM:.2f}). Use a smaller discount or pay the full price.'
        )

    booking.list_price = list_price
    booking.voucher_id = None
    booking.discount_code = discount_code
    booking.voucher_code = discount_code.code
    booking.voucher_discount = discount
    booking.price_paid = price_paid
    booking.save(
        update_fields=[
            'list_price',
            'voucher_id',
            'discount_code',
            'voucher_code',
            'voucher_discount',
            'price_paid',
            'updated_at',
        ]
    )
    return booking


def redeem_discount_code_for_booking(booking):
    """Increment redemption count after successful payment. Idempotent per booking."""
    if not booking.discount_code_id or not booking.voucher_discount:
        return
    if booking.voucher_redeemed_at:
        return

    discount = Decimal(str(booking.voucher_discount))
    if discount <= 0:
        return

    with transaction.atomic():
        DiscountCode.objects.filter(pk=booking.discount_code_id).update(
            times_redeemed=F('times_redeemed') + 1,
        )
        redeemed_at = timezone.now()
        type(booking).objects.filter(pk=booking.pk).update(
            voucher_redeemed_at=redeemed_at,
            updated_at=redeemed_at,
        )
        booking.voucher_redeemed_at = redeemed_at


def codes_for_workshop(workshop):
    if not workshop or not workshop.pk:
        return DiscountCode.objects.none()
    return (
        DiscountCode.objects.filter(workshops=workshop, is_active=True)
        .order_by('code')
        .distinct()
    )


def codes_owned_by_user(user):
    return DiscountCode.objects.filter(created_by=user, is_active=True).order_by('code')


def format_discount_codes_html(codes):
    codes = list(codes)
    if not codes:
        return 'No discount codes apply to this workshop yet.'
    return format_html(
        '<ul style="margin:0;padding-left:1.25rem;">{}</ul>',
        format_html_join(
            '',
            '<li><strong>{}</strong> — {}{}</li>',
            (
                (
                    code.code,
                    code.discount_label,
                    f' (expires {code.expiry_date:%d %b %Y})' if code.expiry_date else '',
                )
                for code in codes
            ),
        ),
    )
