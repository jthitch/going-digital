"""Validate and redeem legacy gd_voucher codes against workshop bookings."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from bookings.discount_codes import (
    apply_discount_code_to_booking,
    get_discount_code_by_code,
    redeem_discount_code_for_booking,
)
from bookings.gift_voucher_basket import get_or_create_customer
from bookings.models import Booking, Voucher

STRIPE_GBP_MINIMUM = Decimal('0.30')


def voucher_remaining(voucher):
    value = Decimal(str(voucher.value or 0))
    claimed = Decimal(str(voucher.amount_claimed or 0))
    return max(Decimal('0'), value - claimed)


def get_voucher_by_code(code):
    code = (code or '').strip()
    if not code:
        return None
    return Voucher.objects.filter(voucher_code__iexact=code).first()


def validate_voucher_for_workshop(voucher, workshop):
    if not voucher:
        raise ValidationError('Voucher code not found.')
    if not voucher.active:
        raise ValidationError('This voucher is not active.')
    if voucher_remaining(voucher) <= 0:
        raise ValidationError('This voucher has no remaining balance.')
    if voucher.use_once and Decimal(str(voucher.amount_claimed or 0)) > 0:
        raise ValidationError('This voucher has already been used.')

    today = timezone.now().date()
    if voucher.expiry_date and voucher.expiry_date < today:
        raise ValidationError('This voucher has expired.')

    if voucher.workshop_id and voucher.workshop_id != workshop.pk:
        raise ValidationError('This voucher is not valid for this workshop.')

    if voucher.region_id and workshop.region_id and voucher.region_id != workshop.region_id:
        raise ValidationError('This voucher is not valid for this region.')

    if voucher.allowed_course and workshop.course_id and voucher.allowed_course != workshop.course_id:
        raise ValidationError('This voucher is not valid for this course.')

    if voucher.course_ids:
        allowed = {
            int(part)
            for part in voucher.course_ids.split(',')
            if part.strip().isdigit()
        }
        if workshop.course_id and workshop.course_id not in allowed:
            raise ValidationError('This voucher is not valid for this course.')

    return voucher


def calculate_voucher_discount(voucher, list_price):
    list_price = Decimal(str(list_price))
    return min(voucher_remaining(voucher), list_price)


def clear_booking_voucher(booking):
    list_price = booking.list_price or booking.workshop.price
    booking.list_price = list_price
    booking.voucher_id = None
    booking.discount_code = None
    booking.voucher_code = ''
    booking.voucher_discount = Decimal('0.00')
    booking.price_paid = list_price
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


def apply_voucher_to_booking(booking, voucher_code):
    """Validate gift voucher or discount code and update booking pricing."""
    voucher = get_voucher_by_code(voucher_code)
    if voucher:
        validate_voucher_for_workshop(voucher, booking.workshop)

        list_price = Decimal(str(booking.list_price or booking.workshop.price))
        discount = calculate_voucher_discount(voucher, list_price)
        price_paid = list_price - discount

        if Decimal('0') < price_paid < STRIPE_GBP_MINIMUM:
            raise ValidationError(
                f'The remaining balance (£{price_paid:.2f}) is below the minimum card payment '
                f'(£{STRIPE_GBP_MINIMUM:.2f}). Use a smaller voucher amount or pay the full price.'
            )

        booking.list_price = list_price
        booking.voucher_id = voucher.id
        booking.discount_code = None
        booking.voucher_code = voucher.voucher_code
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

    if get_discount_code_by_code(voucher_code):
        return apply_discount_code_to_booking(booking, voucher_code)

    raise ValidationError('Voucher code not found.')


def redeem_voucher_for_booking(booking):
    """
    Mark gd_voucher or DiscountCode as claimed after successful payment.
    Idempotent when called again for the same booking.
    """
    if booking.discount_code_id:
        redeem_discount_code_for_booking(booking)
        return

    if not booking.voucher_id or not booking.voucher_discount:
        return

    if booking.voucher_redeemed_at:
        return

    discount = Decimal(str(booking.voucher_discount))
    if discount <= 0:
        return

    customer_id, _ = get_or_create_customer(
        email=booking.student_email,
        firstname=booking.student_first_name,
        lastname=booking.student_last_name,
        phone=booking.student_phone or '',
    )
    today = timezone.now().date().isoformat()
    now = timezone.now().isoformat()

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, value, amount_claimed, use_once, active
                FROM gd_voucher
                WHERE id = %s
                FOR UPDATE
                """,
                [booking.voucher_id],
            )
            row = cursor.fetchone()
            if not row:
                raise ValidationError('Voucher no longer exists.')

            voucher_id, value, amount_claimed, use_once, active = row
            value = Decimal(str(value or 0))
            amount_claimed = Decimal(str(amount_claimed or 0))
            remaining = value - amount_claimed

            if not active or remaining <= 0:
                raise ValidationError('Voucher is no longer valid.')

            if discount > remaining:
                raise ValidationError('Voucher balance changed. Please contact support.')

            new_claimed = amount_claimed + discount
            new_remaining = value - new_claimed
            new_active = 0 if new_remaining <= 0 or use_once else 1

            cursor.execute(
                """
                UPDATE gd_voucher
                SET amount_claimed = %s,
                    claimed_date = %s,
                    claimed_on_booking_id = %s,
                    claimed_by_customer_id = %s,
                    active = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    float(new_claimed),
                    today,
                    booking.id,
                    customer_id,
                    new_active,
                    now,
                    voucher_id,
                ],
            )

    redeemed_at = timezone.now()
    Booking.objects.filter(pk=booking.pk).update(
        voucher_redeemed_at=redeemed_at,
        updated_at=redeemed_at,
    )
    booking.voucher_redeemed_at = redeemed_at
