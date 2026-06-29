"""Session shopping basket for workshop bookings (multiple courses and places)."""
import json
import uuid
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection

from bookings.gift_voucher_basket import (
    get_stripe_gateway_id,
    parse_device_and_browser,
)
from bookings.models import Booking
from bookings.voucher_redemption import (
    STRIPE_GBP_MINIMUM,
    calculate_voucher_discount,
    get_voucher_by_code,
    validate_voucher_for_workshop,
)
from core.customer_auth import get_logged_in_customer
from core.customer_service import get_or_create_customer_record
from courses.models import Workshop

SESSION_KEY = 'workshop_basket'
MAX_QUANTITY_PER_LINE = 10


def places_available_message(available, existing_in_basket=0):
    """User-facing message when requested places exceed workshop availability."""
    place_word = 'place' if available == 1 else 'places'
    message = f'Only {available} {place_word} available on this course.'
    if existing_in_basket:
        basket_word = 'place' if existing_in_basket == 1 else 'places'
        message += f' ({existing_in_basket} {basket_word} already in your basket.)'
    return message


def loan_cameras_reserved_in_basket(basket, workshop_id, exclude_item_id=None):
    total = 0
    for item in basket.get('items', []):
        if item['workshop_id'] != workshop_id:
            continue
        if exclude_item_id and item.get('id') == exclude_item_id:
            continue
        total += int(item.get('loan_cameras') or 0)
    return total


def validate_loan_cameras_requested(
    workshop,
    loan_cameras,
    quantity,
    basket=None,
    exclude_item_id=None,
):
    loan_cameras = int(loan_cameras or 0)
    quantity = int(quantity or 0)
    if loan_cameras < 0:
        raise ValidationError('Invalid loan camera count.')
    if loan_cameras == 0:
        return 0
    if not workshop.has_loan_cameras_available:
        raise ValidationError('Loan cameras are not available for this course.')
    if loan_cameras > quantity:
        raise ValidationError('You cannot request more loan cameras than places booked.')
    reserved = loan_cameras_reserved_in_basket(
        basket or {},
        workshop.pk,
        exclude_item_id=exclude_item_id,
    )
    remaining = workshop.loan_cameras_remaining() - reserved
    if loan_cameras > remaining:
        camera_word = 'camera' if remaining == 1 else 'cameras'
        raise ValidationError(
            f'Only {remaining} loan {camera_word} still available for this course.'
        )
    return loan_cameras


def _empty_basket():
    return {
        'items': [],
        'voucher_id': None,
        'voucher_code': '',
        'voucher_discount': '0.00',
    }


def get_session_basket(request):
    basket = request.session.get(SESSION_KEY)
    if not basket or not isinstance(basket, dict):
        return _empty_basket()
    basket.setdefault('items', [])
    return basket


def save_session_basket(request, basket):
    request.session[SESSION_KEY] = basket
    request.session.modified = True


def basket_item_count(basket):
    return sum(int(item.get('quantity', 1)) for item in basket.get('items', []))


def _workshop_line_subtotal(workshop, quantity):
    price = Decimal(str(workshop.price))
    return price * int(quantity)


def basket_list_total(basket, workshops_by_id=None):
    total = Decimal('0.00')
    for item in basket.get('items', []):
        workshop = workshops_by_id.get(item['workshop_id']) if workshops_by_id else None
        if workshop:
            total += _workshop_line_subtotal(workshop, item['quantity'])
        else:
            total += Decimal(str(item.get('unit_price', 0))) * int(item.get('quantity', 1))
    return total


def basket_amount_due(basket, workshops_by_id=None):
    list_total = basket_list_total(basket, workshops_by_id)
    discount = Decimal(str(basket.get('voucher_discount') or '0'))
    return max(Decimal('0.00'), list_total - discount)


def load_workshops_for_basket(basket):
    from courses.display_images import attach_gd_images_to_workshops

    ids = {item['workshop_id'] for item in basket.get('items', [])}
    if not ids:
        return {}
    workshops = Workshop.objects.filter(pk__in=ids, active=1).select_related(
        'course', 'course__image', 'venue',
    ).prefetch_related('course__media', 'gallery_images__image')
    workshop_list = list(workshops)
    attach_gd_images_to_workshops(workshop_list)
    return {w.pk: w for w in workshop_list}


def get_basket_lines(request):
    basket = get_session_basket(request)
    workshops = load_workshops_for_basket(basket)
    lines = []
    for item in basket.get('items', []):
        workshop = workshops.get(item['workshop_id'])
        if not workshop:
            continue
        qty = int(item.get('quantity', 1))
        unit = Decimal(str(workshop.price))
        lines.append({
            'item': item,
            'workshop': workshop,
            'quantity': qty,
            'unit_price': unit,
            'line_total': unit * qty,
        })
    list_total = basket_list_total(basket, workshops)
    discount = Decimal(str(basket.get('voucher_discount') or '0'))
    return {
        'basket': basket,
        'lines': lines,
        'workshops': workshops,
        'list_total': list_total,
        'discount': discount,
        'total': max(Decimal('0.00'), list_total - discount),
        'item_count': basket_item_count(basket),
    }


def _validate_quantity_for_workshop(workshop, quantity, existing_in_basket=0):
    quantity = int(quantity)
    if quantity < 1:
        raise ValidationError('Please book at least one place.')
    if quantity > MAX_QUANTITY_PER_LINE:
        raise ValidationError(f'Maximum {MAX_QUANTITY_PER_LINE} places per line.')
    if workshop.is_full:
        raise ValidationError('This course is fully booked.')
    if not workshop.enrollment_open:
        raise ValidationError('Enrollment is not currently open for this course.')
    available = workshop.spaces_available
    if available is not None and quantity + existing_in_basket > available:
        raise ValidationError(
            places_available_message(available, existing_in_basket=existing_in_basket)
        )


def add_item_to_basket(request, workshop, cleaned_data, quantity):
    basket = get_session_basket(request)
    quantity = int(quantity)
    email = cleaned_data['student_email'].strip().lower()

    existing_qty = 0
    merge_target = None
    for item in basket['items']:
        if item['workshop_id'] == workshop.pk and item['student_email'].lower() == email:
            merge_target = item
            existing_qty = int(item.get('quantity', 1))
            break

    _validate_quantity_for_workshop(workshop, quantity, existing_in_basket=existing_qty)

    new_quantity = existing_qty + quantity if merge_target else quantity
    loan_cameras = validate_loan_cameras_requested(
        workshop,
        cleaned_data.get('loan_cameras', 0),
        new_quantity,
        basket=basket,
        exclude_item_id=merge_target.get('id') if merge_target else None,
    )

    if merge_target:
        merge_target['quantity'] = new_quantity
        merge_target['student_first_name'] = cleaned_data['student_first_name']
        merge_target['student_last_name'] = cleaned_data['student_last_name']
        merge_target['student_phone'] = cleaned_data.get('student_phone', '')
        merge_target['special_requirements'] = cleaned_data.get('special_requirements', '')
        merge_target['loan_cameras'] = loan_cameras
        merge_target['unit_price'] = str(workshop.price)
    else:
        basket['items'].append({
            'id': uuid.uuid4().hex,
            'workshop_id': workshop.pk,
            'quantity': quantity,
            'student_first_name': cleaned_data['student_first_name'],
            'student_last_name': cleaned_data['student_last_name'],
            'student_email': cleaned_data['student_email'].strip(),
            'student_phone': cleaned_data.get('student_phone', ''),
            'special_requirements': cleaned_data.get('special_requirements', ''),
            'loan_cameras': loan_cameras,
            'unit_price': str(workshop.price),
        })

    _recalculate_voucher(basket, load_workshops_for_basket(basket))
    save_session_basket(request, basket)
    return basket


def update_item_quantity(request, item_id, quantity):
    basket = get_session_basket(request)
    workshops = load_workshops_for_basket(basket)
    for item in basket['items']:
        if item['id'] == item_id:
            workshop = workshops.get(item['workshop_id'])
            if not workshop:
                raise ValidationError('This course is no longer available.')
            _validate_quantity_for_workshop(workshop, quantity)
            item['quantity'] = int(quantity)
            break
    else:
        raise ValidationError('Basket item not found.')
    _recalculate_voucher(basket, workshops)
    save_session_basket(request, basket)


def remove_item_from_basket(request, item_id):
    basket = get_session_basket(request)
    basket['items'] = [i for i in basket['items'] if i['id'] != item_id]
    workshops = load_workshops_for_basket(basket)
    _recalculate_voucher(basket, workshops)
    save_session_basket(request, basket)


def clear_session_basket(request):
    if SESSION_KEY in request.session:
        del request.session[SESSION_KEY]
        request.session.modified = True


def _recalculate_voucher(basket, workshops_by_id):
    code = basket.get('voucher_code') or ''
    if not code:
        basket['voucher_id'] = None
        basket['voucher_discount'] = '0.00'
        return
    try:
        apply_voucher_to_session_basket(basket, code, workshops_by_id)
    except ValidationError:
        basket['voucher_id'] = None
        basket['voucher_code'] = ''
        basket['voucher_discount'] = '0.00'


def apply_voucher_to_session_basket(basket, voucher_code, workshops_by_id=None):
    if workshops_by_id is None:
        workshops_by_id = load_workshops_for_basket(basket)
    if not basket.get('items'):
        raise ValidationError('Your basket is empty.')

    voucher = get_voucher_by_code(voucher_code)
    if not voucher:
        raise ValidationError('Voucher code not found.')

    for item in basket['items']:
        workshop = workshops_by_id.get(item['workshop_id'])
        if workshop:
            validate_voucher_for_workshop(voucher, workshop)

    list_total = basket_list_total(basket, workshops_by_id)
    discount = calculate_voucher_discount(voucher, list_total)
    amount_due = list_total - discount
    if Decimal('0') < amount_due < STRIPE_GBP_MINIMUM:
        raise ValidationError(
            f'The remaining balance (£{amount_due:.2f}) is below the minimum card payment '
            f'(£{STRIPE_GBP_MINIMUM:.2f}).'
        )

    basket['voucher_id'] = voucher.id
    basket['voucher_code'] = voucher.voucher_code
    basket['voucher_discount'] = str(discount)
    return basket


def clear_voucher_from_session_basket(basket):
    basket['voucher_id'] = None
    basket['voucher_code'] = ''
    basket['voucher_discount'] = '0.00'
    return basket


def _resolve_customer(request, purchaser_email, firstname=None, lastname=None, phone=''):
    logged_in = get_logged_in_customer(request)
    if logged_in:
        return logged_in

    email = (purchaser_email or '').strip()
    if not email:
        raise ValidationError('Email is required.')

    customer, _ = get_or_create_customer_record(email, firstname, lastname, phone)
    return customer


def _allocate_discounts(booking_amounts, total_discount):
    """Split voucher discount across bookings proportionally (last booking gets remainder)."""
    total_discount = Decimal(str(total_discount))
    if total_discount <= 0:
        return [Decimal('0.00')] * len(booking_amounts)
    subtotal = sum(booking_amounts)
    if subtotal <= 0:
        return [Decimal('0.00')] * len(booking_amounts)
    allocations = []
    allocated = Decimal('0.00')
    for idx, amount in enumerate(booking_amounts):
        if idx == len(booking_amounts) - 1:
            share = total_discount - allocated
        else:
            share = (total_discount * amount / subtotal).quantize(Decimal('0.01'))
            allocated += share
        allocations.append(share)
    return allocations


def create_pending_bookings_for_basket(basket, customer):
    """Create one Booking row per place; return booking ids in basket order."""
    workshops = load_workshops_for_basket(basket)
    booking_specs = []
    for item in basket['items']:
        workshop = workshops.get(item['workshop_id'])
        if not workshop:
            raise ValidationError('A course in your basket is no longer available.')
        qty = int(item['quantity'])
        _validate_quantity_for_workshop(workshop, qty)
        loan_cameras = int(item.get('loan_cameras') or 0)
        unit = Decimal(str(workshop.price))
        for place_index in range(qty):
            booking_specs.append({
                'workshop': workshop,
                'list_price': unit,
                'student_first_name': item['student_first_name'],
                'student_last_name': item['student_last_name'],
                'student_email': item['student_email'],
                'student_phone': item.get('student_phone', ''),
                'special_requirements': item.get('special_requirements', ''),
                'loan_camera': place_index < loan_cameras,
            })

    list_amounts = [spec['list_price'] for spec in booking_specs]
    discount_alloc = _allocate_discounts(
        list_amounts,
        Decimal(str(basket.get('voucher_discount') or '0')),
    )

    booking_ids = []
    for spec, discount_share in zip(booking_specs, discount_alloc):
        price_paid = max(Decimal('0.00'), spec['list_price'] - discount_share)
        booking = Booking(
            workshop=spec['workshop'],
            user=None,
            customer=customer,
            student_first_name=spec['student_first_name'],
            student_last_name=spec['student_last_name'],
            student_email=spec['student_email'],
            student_phone=spec['student_phone'],
            special_requirements=spec['special_requirements'],
            loan_camera=spec['loan_camera'],
            list_price=spec['list_price'],
            price_paid=price_paid,
            status='pending',
        )
        if basket.get('voucher_id'):
            booking.voucher_id = basket['voucher_id']
            booking.voucher_code = basket.get('voucher_code', '')
            booking.voucher_discount = discount_share
        booking.save()
        booking_ids.append(booking.id)
    return booking_ids


def persist_workshop_basket(request, basket, booking_ids, customer):
    """Save basket snapshot to gd_basket for payment webhook completion."""
    workshops = load_workshops_for_basket(basket)
    list_total = basket_list_total(basket, workshops)
    discount = Decimal(str(basket.get('voucher_discount') or '0'))
    total = max(Decimal('0.00'), list_total - discount)
    purchaser_email = ''
    if basket['items']:
        purchaser_email = basket['items'][0]['student_email']

    customer_id = customer.pk

    gateway_id = get_stripe_gateway_id()
    checksum = uuid.uuid4().hex
    basket_data = {
        'type': 'workshop_booking',
        'user_id': None,
        'customer_id': customer_id,
        'booking_ids': booking_ids,
        'list_total': str(list_total),
        'voucher_id': basket.get('voucher_id'),
        'voucher_code': basket.get('voucher_code', ''),
        'voucher_discount': str(discount),
        'total': str(total),
        'purchaser_email': purchaser_email,
        'items': basket.get('items', []),
    }

    from django.utils import timezone as dj_tz

    user_agent = request.META.get('HTTP_USER_AGENT', '')
    device_type, browser = parse_device_and_browser(user_agent)
    now = dj_tz.now().isoformat()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO gd_basket
            (customer_id, payment_gateway_id, checksum, basket_data, basket_total,
             discount_total, transaction_total, device_type, browser, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                customer_id,
                gateway_id,
                checksum,
                json.dumps(basket_data),
                float(total),
                float(discount),
                float(total),
                device_type,
                browser,
                now,
                now,
            ],
        )
        return cursor.lastrowid


def get_workshop_basket(basket_id):
    """Load gd_basket row for workshop booking checkout."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, customer_id, basket_data, basket_total FROM gd_basket WHERE id = %s",
            [basket_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        data = json.loads(row[2] or '{}')
        if data.get('type') != 'workshop_booking':
            return None
        return {
            'id': row[0],
            'customer_id': row[1],
            'basket_data': data,
            'basket_total': row[3],
        }


def apply_voucher_to_gd_basket(basket_id, voucher_code):
    """Apply voucher to a persisted gd_basket and update pending booking prices."""
    basket = get_workshop_basket(basket_id)
    if not basket:
        raise ValidationError('Basket not found.')
    data = basket['basket_data']
    booking_ids = data.get('booking_ids') or []
    bookings = list(
        Booking.objects.filter(id__in=booking_ids, status='pending').select_related('workshop')
    )
    if not bookings:
        raise ValidationError('No pending bookings for this basket.')

    session_like = {
        'items': data.get('items', []),
        'voucher_id': None,
        'voucher_code': '',
        'voucher_discount': '0.00',
    }
    workshops = {b.workshop_id: b.workshop for b in bookings}
    apply_voucher_to_session_basket(session_like, voucher_code, workshops)

    list_amounts = [Decimal(str(b.list_price or b.workshop.price)) for b in bookings]
    discount_alloc = _allocate_discounts(
        list_amounts,
        Decimal(str(session_like.get('voucher_discount') or '0')),
    )
    for booking, list_price, discount_share in zip(bookings, list_amounts, discount_alloc):
        booking.voucher_id = session_like.get('voucher_id')
        booking.voucher_code = session_like.get('voucher_code', '')
        booking.voucher_discount = discount_share
        booking.price_paid = max(Decimal('0.00'), list_price - discount_share)
        booking.save(
            update_fields=[
                'voucher_id',
                'voucher_code',
                'voucher_discount',
                'price_paid',
                'updated_at',
            ]
        )

    data['voucher_id'] = session_like.get('voucher_id')
    data['voucher_code'] = session_like.get('voucher_code', '')
    data['voucher_discount'] = session_like.get('voucher_discount', '0.00')
    data['total'] = str(
        max(Decimal('0.00'), Decimal(str(data.get('list_total', '0'))) - Decimal(data['voucher_discount']))
    )

    from django.utils import timezone as dj_tz
    now = dj_tz.now().isoformat()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE gd_basket
            SET basket_data = %s, basket_total = %s, discount_total = %s,
                transaction_total = %s, updated_at = %s
            WHERE id = %s
            """,
            [
                json.dumps(data),
                float(data['total']),
                float(data['voucher_discount']),
                float(data['total']),
                now,
                basket_id,
            ],
        )
    return get_workshop_basket(basket_id)


def clear_voucher_from_gd_basket(basket_id):
    basket = get_workshop_basket(basket_id)
    if not basket:
        return
    data = basket['basket_data']
    booking_ids = data.get('booking_ids') or []
    for booking in Booking.objects.filter(id__in=booking_ids, status='pending'):
        booking.voucher_id = None
        booking.voucher_code = ''
        booking.voucher_discount = Decimal('0.00')
        booking.price_paid = booking.list_price or booking.workshop.price
        booking.save(
            update_fields=[
                'voucher_id',
                'voucher_code',
                'voucher_discount',
                'price_paid',
                'updated_at',
            ]
        )
    data['voucher_id'] = None
    data['voucher_code'] = ''
    data['voucher_discount'] = '0.00'
    data['total'] = data.get('list_total', '0.00')
    from django.utils import timezone as dj_tz
    now = dj_tz.now().isoformat()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE gd_basket
            SET basket_data = %s, basket_total = %s, discount_total = 0,
                transaction_total = %s, updated_at = %s
            WHERE id = %s
            """,
            [json.dumps(data), float(data['total']), float(data['total']), now, basket_id],
        )


def prepare_checkout_from_session(request):
    """Create pending bookings + gd_basket from session cart. Returns basket_id."""
    basket = get_session_basket(request)
    if not basket.get('items'):
        raise ValidationError('Your basket is empty.')
    workshops = load_workshops_for_basket(basket)
    if len(workshops) != len({i['workshop_id'] for i in basket['items']}):
        raise ValidationError('A course in your basket is no longer available.')

    lead_item = basket['items'][0]
    purchaser_email = lead_item['student_email'].strip()
    customer = _resolve_customer(
        request,
        purchaser_email,
        firstname=lead_item.get('student_first_name'),
        lastname=lead_item.get('student_last_name'),
        phone=lead_item.get('student_phone', ''),
    )
    booking_ids = create_pending_bookings_for_basket(basket, customer)
    basket_id = persist_workshop_basket(request, basket, booking_ids, customer)
    clear_session_basket(request)
    return basket_id, booking_ids, customer
