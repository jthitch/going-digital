"""
Payment views - Stripe integration.
"""
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    stripe = None

import uuid
from decimal import Decimal
from urllib.parse import unquote

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse, JsonResponse
from django.views import View
from bookings.models import Booking
from bookings.gift_voucher_basket import get_basket
from bookings.workshop_basket import (
    apply_voucher_to_gd_basket,
    clear_voucher_from_gd_basket,
    get_workshop_basket,
)
from bookings.voucher_redemption import (
    apply_voucher_to_booking,
    clear_booking_voucher,
)
from core.customer_auth import get_logged_in_customer, is_customer_authenticated
from core.forms_student import CompleteAccountPasswordForm
from core.student_auth import (
    payment_account_context_from_bookings,
    payment_account_context_from_checkout_data,
)
from payments.checkout_session_context import (
    get_checkout_success_context,
    load_bookings_from_checkout_context,
    store_checkout_success_context,
)

from .checkout_completion import complete_checkout_session, stripe_metadata_dict
from .forms import VoucherCheckoutForm
from .models import Payment


def _redirect_to_open_checkout(booking):
    """Reuse an existing open Stripe Checkout session instead of creating duplicates."""
    if not STRIPE_AVAILABLE or not booking.payment_id:
        return None
    payment = booking.payment
    if payment.status != 'pending' or payment.intent_type != 'checkout_session':
        return None
    try:
        session = stripe.checkout.Session.retrieve(payment.stripe_id)
    except stripe.error.StripeError:
        return None
    if session.status == 'open' and session.url:
        return redirect(session.url)
    return None


# Configure Stripe if available
if STRIPE_AVAILABLE and hasattr(settings, 'STRIPE_SECRET_KEY'):
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _get_pending_booking(request, booking_id):
    qs = Booking.objects.select_related('workshop', 'workshop__course', 'workshop__venue', 'payment')
    customer = get_logged_in_customer(request)
    if customer:
        return get_object_or_404(qs, id=booking_id, customer=customer, status='pending')
    return get_object_or_404(qs, id=booking_id, status='pending')


def _detach_pending_payment(booking):
    if not booking.payment_id:
        return
    payment = booking.payment
    if payment.status != 'pending':
        return
    if payment.intent_type == 'checkout_session' and STRIPE_AVAILABLE:
        try:
            stripe.checkout.Session.expire(payment.stripe_id)
        except stripe.error.StripeError:
            pass
    payment.status = 'cancelled'
    payment.save(update_fields=['status', 'updated_at'])
    booking.payment = None
    booking.save(update_fields=['payment', 'updated_at'])


def _booking_list_price(booking):
    return booking.list_price or booking.workshop.price


def _booking_payment_metadata(booking):
    metadata = {
        'booking_id': booking.id,
        'booking_reference': booking.booking_reference,
    }
    if booking.voucher_id:
        metadata['voucher_id'] = booking.voucher_id
        metadata['voucher_code'] = booking.voucher_code
        metadata['voucher_discount'] = str(booking.voucher_discount)
        if booking.list_price is not None:
            metadata['list_price'] = str(booking.list_price)
    return metadata


def _checkout_context(booking, voucher_form=None):
    return {
        'booking': booking,
        'list_price': _booking_list_price(booking),
        'voucher_form': voucher_form or VoucherCheckoutForm(),
    }


def _start_stripe_checkout(request, booking):
    if not STRIPE_AVAILABLE:
        return JsonResponse(
            {'error': 'Stripe is not configured. Please install stripe and set STRIPE_SECRET_KEY in settings.'},
            status=503,
        )

    existing_redirect = _redirect_to_open_checkout(booking)
    if existing_redirect:
        return existing_redirect

    unit_amount = int(booking.price_paid * 100)
    if unit_amount <= 0:
        return redirect('payments:create_checkout', booking_id=booking.id)

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {
                        'name': (
                            f"{booking.workshop.course.title if booking.workshop.course else 'Workshop'}"
                            f" - {booking.workshop.venue.name if booking.workshop.venue else 'TBC'}"
                        ),
                        'description': f"Course on {booking.workshop.start_date.strftime('%d %B %Y')}",
                    },
                    'unit_amount': unit_amount,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=_stripe_checkout_success_url(request),
            cancel_url=request.build_absolute_uri(
                reverse('payments:create_checkout', kwargs={'booking_id': booking.id})
            ),
            metadata={
                'booking_id': str(booking.id),
                'booking_reference': booking.booking_reference,
                **(
                    {
                        'voucher_id': str(booking.voucher_id),
                        'voucher_code': booking.voucher_code,
                    }
                    if booking.voucher_id
                    else {}
                ),
            },
            customer_email=booking.student_email,
        )

        payment_metadata = _booking_payment_metadata(booking)

        payment = Payment.objects.create(
            user=None,
            intent_type='checkout_session',
            stripe_id=checkout_session.id,
            amount=booking.price_paid,
            currency='gbp',
            description=f"Booking {booking.booking_reference}",
            metadata=payment_metadata,
        )

        booking.payment = payment
        booking.save(update_fields=['payment', 'updated_at'])
        store_checkout_success_context(request, [booking])

        return redirect(checkout_session.url)

    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e)}, status=400)


def _complete_free_voucher_checkout(request, booking):
    stripe_id = f'free-{booking.booking_reference}-{uuid.uuid4().hex[:12]}'
    payment_metadata = _booking_payment_metadata(booking)

    payment = Payment.objects.create(
        user=None,
        intent_type='voucher_free',
        stripe_id=stripe_id,
        amount=Decimal('0.00'),
        currency='gbp',
        description=f"Booking {booking.booking_reference} (voucher)",
        metadata=payment_metadata,
    )
    booking.payment = payment
    booking.save(update_fields=['payment', 'updated_at'])

    complete_checkout_session(
        {
            'id': stripe_id,
            'payment_status': 'paid',
            'status': 'complete',
            'metadata': payment_metadata,
        },
        source='voucher_free (checkout)',
    )
    store_checkout_success_context(request, [booking])
    return redirect(f'{reverse("payments:success")}?session_id={stripe_id}')


class CreateCheckoutSessionView(View):
    """Checkout review with optional voucher redemption, then Stripe or free completion."""

    def get(self, request, booking_id):
        booking = _get_pending_booking(request, booking_id)
        if not booking.list_price:
            booking.list_price = booking.workshop.price
            booking.save(update_fields=['list_price', 'updated_at'])
        return render(request, 'payments/checkout.html', _checkout_context(booking))

    def post(self, request, booking_id):
        booking = _get_pending_booking(request, booking_id)
        action = request.POST.get('action', 'pay')

        if action == 'redeem':
            form = VoucherCheckoutForm(request.POST)
            if not form.is_valid():
                return render(
                    request,
                    'payments/checkout.html',
                    _checkout_context(booking, form),
                )
            code = form.cleaned_data['voucher_code']
            if not code:
                form.add_error('voucher_code', 'Please enter a voucher code.')
                return render(
                    request,
                    'payments/checkout.html',
                    _checkout_context(booking, form),
                )
            try:
                _detach_pending_payment(booking)
                apply_voucher_to_booking(booking, code)
                booking.refresh_from_db()
                messages.success(request, f'Voucher {booking.voucher_code} applied.')
            except ValidationError as exc:
                form.add_error('voucher_code', exc.messages[0] if exc.messages else str(exc))
                return render(
                    request,
                    'payments/checkout.html',
                    _checkout_context(booking, form),
                )
            return redirect('payments:create_checkout', booking_id=booking.id)

        if action == 'remove':
            _detach_pending_payment(booking)
            clear_booking_voucher(booking)
            messages.info(request, 'Voucher removed.')
            return redirect('payments:create_checkout', booking_id=booking.id)

        if booking.price_paid <= 0:
            if not booking.voucher_id:
                messages.error(request, 'Apply a voucher that covers the full course price, or pay by card.')
                return redirect('payments:create_checkout', booking_id=booking.id)
            return _complete_free_voucher_checkout(request, booking)

        return _start_stripe_checkout(request, booking)


def _get_workshop_basket_context(basket_id):
    basket = get_workshop_basket(basket_id)
    if not basket:
        return None
    data = basket['basket_data']
    booking_ids = data.get('booking_ids') or []
    bookings = list(
        Booking.objects.filter(id__in=booking_ids, status='pending')
        .select_related('workshop', 'workshop__course', 'workshop__venue')
        .order_by('id')
    )
    if not bookings:
        return None
    list_total = Decimal(str(data.get('list_total', '0')))
    discount = Decimal(str(data.get('voucher_discount', '0')))
    total = Decimal(str(data.get('total', '0')))
    return {
        'gd_basket': basket,
        'basket_data': data,
        'bookings': bookings,
        'list_total': list_total,
        'discount': discount,
        'total': total,
        'voucher_form': VoucherCheckoutForm(
            initial={'voucher_code': data.get('voucher_code', '')},
        ),
    }


def _workshop_basket_payment_metadata(basket_id, data, booking_ids):
    return {
        'workshop_basket_id': basket_id,
        'booking_ids': booking_ids,
        'list_total': data.get('list_total'),
        'voucher_code': data.get('voucher_code', ''),
        'voucher_discount': data.get('voucher_discount', '0'),
        'total': data.get('total'),
    }


def _start_stripe_basket_checkout(request, basket_id, ctx):
    if not STRIPE_AVAILABLE:
        return JsonResponse({'error': 'Stripe is not configured.'}, status=503)

    bookings = ctx['bookings']
    total = ctx['total']
    data = ctx['basket_data']
    unit_amount = int(total * 100)
    if unit_amount <= 0:
        return redirect('payments:create_workshop_basket_checkout', basket_id=basket_id)

    line_items = []
    for booking in bookings:
        workshop = booking.workshop
        line_items.append({
            'price_data': {
                'currency': 'gbp',
                'product_data': {
                    'name': (
                        f"{workshop.course.title if workshop.course else 'Workshop'}"
                        f" - {workshop.venue.name if workshop.venue else 'TBC'}"
                    ),
                    'description': (
                        f"{booking.student_first_name} {booking.student_last_name} · "
                        f"{workshop.start_date.strftime('%d %B %Y')}"
                    ),
                },
                'unit_amount': int(booking.price_paid * 100),
            },
            'quantity': 1,
        })

    purchaser_email = data.get('purchaser_email') or bookings[0].student_email
    booking_ids = [b.id for b in bookings]
    metadata = {
        'workshop_basket_id': str(basket_id),
        'booking_ids': ','.join(str(i) for i in booking_ids),
    }

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=_stripe_checkout_success_url(request),
            cancel_url=request.build_absolute_uri(
                reverse('payments:create_workshop_basket_checkout', kwargs={'basket_id': basket_id})
            ),
            metadata=metadata,
            customer_email=purchaser_email,
        )

        payment_metadata = _workshop_basket_payment_metadata(basket_id, data, booking_ids)
        payment = Payment.objects.create(
            user=None,
            intent_type='checkout_session',
            stripe_id=checkout_session.id,
            amount=total,
            currency='gbp',
            description=f"Workshop basket #{basket_id}",
            metadata=payment_metadata,
        )
        Booking.objects.filter(id__in=booking_ids).update(payment=payment)
        store_checkout_success_context(request, bookings)
        return redirect(checkout_session.url)
    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e)}, status=400)


def _complete_free_workshop_basket_checkout(request, basket_id, ctx):
    bookings = ctx['bookings']
    data = ctx['basket_data']
    booking_ids = [b.id for b in bookings]
    stripe_id = f'free-basket-{basket_id}-{uuid.uuid4().hex[:12]}'
    payment_metadata = _workshop_basket_payment_metadata(basket_id, data, booking_ids)
    payment = Payment.objects.create(
        user=None,
        intent_type='voucher_free',
        stripe_id=stripe_id,
        amount=Decimal('0.00'),
        currency='gbp',
        description=f"Workshop basket #{basket_id} (voucher)",
        metadata=payment_metadata,
    )
    Booking.objects.filter(id__in=booking_ids).update(payment=payment)
    complete_checkout_session(
        {
            'id': stripe_id,
            'payment_status': 'paid',
            'status': 'complete',
            'metadata': {
                'workshop_basket_id': str(basket_id),
                'booking_ids': ','.join(str(i) for i in booking_ids),
            },
        },
        source='voucher_free (basket checkout)',
    )
    store_checkout_success_context(request, bookings)
    return redirect(f'{reverse("payments:success")}?session_id={stripe_id}')


def initiate_workshop_basket_payment(request, basket_id):
    """Start Stripe Checkout or complete a fully discounted basket."""
    ctx = _get_workshop_basket_context(basket_id)
    if not ctx:
        from django.http import Http404
        raise Http404('Basket not found')

    if ctx['total'] <= 0:
        if not ctx['basket_data'].get('voucher_code'):
            messages.error(
                request,
                'Apply a voucher that covers the full amount, or pay by card.',
            )
            return redirect('payments:create_workshop_basket_checkout', basket_id=basket_id)
        return _complete_free_workshop_basket_checkout(request, basket_id, ctx)

    return _start_stripe_basket_checkout(request, basket_id, ctx)


class CreateWorkshopBasketCheckoutView(View):
    """Checkout review for a multi-booking workshop basket."""

    def get(self, request, basket_id):
        ctx = _get_workshop_basket_context(basket_id)
        if not ctx:
            from django.http import Http404
            raise Http404('Basket not found')
        return render(request, 'payments/checkout_basket.html', ctx)

    def post(self, request, basket_id):
        ctx = _get_workshop_basket_context(basket_id)
        if not ctx:
            from django.http import Http404
            raise Http404('Basket not found')
        action = request.POST.get('action', 'pay')

        if action == 'redeem':
            form = VoucherCheckoutForm(request.POST)
            if not form.is_valid():
                ctx['voucher_form'] = form
                return render(request, 'payments/checkout_basket.html', ctx)
            code = form.cleaned_data['voucher_code']
            if not code:
                form.add_error('voucher_code', 'Please enter a voucher code.')
                ctx['voucher_form'] = form
                return render(request, 'payments/checkout_basket.html', ctx)
            try:
                apply_voucher_to_gd_basket(basket_id, code)
                messages.success(request, 'Voucher applied.')
            except ValidationError as exc:
                form.add_error('voucher_code', exc.messages[0] if exc.messages else str(exc))
                ctx['voucher_form'] = form
                return render(request, 'payments/checkout_basket.html', ctx)
            return redirect('payments:create_workshop_basket_checkout', basket_id=basket_id)

        if action == 'remove':
            clear_voucher_from_gd_basket(basket_id)
            messages.info(request, 'Voucher removed.')
            return redirect('payments:create_workshop_basket_checkout', basket_id=basket_id)

        return initiate_workshop_basket_payment(request, basket_id)


class CreateGiftVoucherCheckoutView(View):
    """Create Stripe Checkout Session for gift voucher purchase (uses gd_basket)."""

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return self.post(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, basket_id):
        if not STRIPE_AVAILABLE:
            return JsonResponse({'error': 'Stripe is not configured.'}, status=503)

        basket = get_basket(basket_id)
        if not basket or basket.get('basket_data', {}).get('type') != 'gift_voucher':
            from django.http import Http404
            raise Http404('Basket not found')

        data = basket['basket_data']
        user_id = data.get('user_id')
        if request.user.is_authenticated and user_id is not None and user_id != request.user.id:
            from django.http import Http404
            raise Http404('Basket not found')

        from core.models import User
        user = User.objects.get(id=user_id) if user_id else None

        amount = data['amount']
        quantity = data['quantity']
        total = data['total']
        purchaser_email = data.get('purchaser_email', '')

        try:
            product_name = f"Gift Voucher - £{int(amount)} x {quantity}"
            if quantity > 1:
                product_name = f"Gift Vouchers - £{int(amount)} each x {quantity}"

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'gbp',
                        'product_data': {
                            'name': product_name,
                            'description': 'Going Digital photography course gift voucher. Valid for 9 months.',
                        },
                        'unit_amount': int(total * 100),  # Convert to pence
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=_stripe_checkout_success_url(request, extra_query='type=gift_voucher'),
                cancel_url=request.build_absolute_uri(reverse('courses:gift_vouchers')),
                metadata={
                    'gift_voucher_basket_id': str(basket_id),
                },
                customer_email=purchaser_email,
            )

            Payment.objects.create(
                user=user,
                intent_type='checkout_session',
                stripe_id=checkout_session.id,
                amount=total,
                currency='gbp',
                description=f"Gift Voucher Basket #{basket_id}",
                metadata={
                    'gift_voucher_basket_id': str(basket_id),
                }
            )

            request.session['gift_voucher_checkout_basket_id'] = basket_id

            return redirect(checkout_session.url)

        except stripe.error.StripeError as e:
            return JsonResponse({'error': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    """Handle Stripe webhooks."""
    
    def post(self, request):
        if not STRIPE_AVAILABLE:
            return HttpResponse(status=503)
        
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
            )
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            complete_checkout_session(session, source='checkout.session.completed')
        elif event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            self.handle_payment_intent_succeeded(payment_intent)
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            self.handle_payment_intent_failed(payment_intent)
        
        return HttpResponse(status=200)
    
    def handle_payment_intent_succeeded(self, payment_intent):
        """Handle successful payment intent."""
        # Similar implementation for payment intents
        pass
    
    def handle_payment_intent_failed(self, payment_intent):
        """Handle failed payment intent."""
        pass


def _payment_metadata_booking_ids(metadata):
    booking_ids = metadata.get('booking_ids')
    if isinstance(booking_ids, str):
        return [int(x) for x in booking_ids.split(',') if str(x).strip().isdigit()]
    if isinstance(booking_ids, (list, tuple)):
        return [int(x) for x in booking_ids if str(x).strip().isdigit()]
    return []


def _load_bookings_from_payment_metadata(metadata):
    if 'workshop_basket_id' in metadata:
        booking_ids = _payment_metadata_booking_ids(metadata)
        if booking_ids:
            return Booking.objects.filter(id__in=booking_ids).select_related(
                'workshop', 'workshop__course', 'workshop__venue', 'user',
            )
    if 'booking_id' in metadata:
        try:
            return Booking.objects.filter(pk=int(metadata['booking_id'])).select_related(
                'workshop', 'workshop__course', 'workshop__venue', 'user',
            )
        except (TypeError, ValueError):
            pass
    return Booking.objects.none()


def _attach_account_setup_context(request, context, bookings=None, checkout_data=None):
    if context.get('is_gift_voucher') or context.get('payment_account'):
        return

    booking_list = list(bookings or [])
    if context.get('booking') and not booking_list:
        booking_list = [context['booking']]

    account_ctx = None
    if booking_list:
        account_ctx = payment_account_context_from_bookings(
            booking_list,
            is_authenticated=is_customer_authenticated(request),
        )
    elif checkout_data:
        account_ctx = payment_account_context_from_checkout_data(
            checkout_data,
            is_authenticated=is_customer_authenticated(request),
        )

    if not account_ctx:
        return

    request.session['account_setup_email'] = account_ctx['email'].strip().lower()
    context['payment_account'] = account_ctx
    if account_ctx['mode'] == 'setup':
        context['account_setup_form'] = CompleteAccountPasswordForm(
            setup=account_ctx['setup'],
        )


def _is_stripe_session_placeholder(session_id):
    if not session_id:
        return True
    decoded = unquote(session_id)
    return decoded == '{CHECKOUT_SESSION_ID}' or '{CHECKOUT_SESSION_ID}' in decoded


def _stripe_checkout_success_url(request, *, extra_query=''):
    """
    Absolute success URL for Stripe Checkout.

    Stripe must receive the literal ``{CHECKOUT_SESSION_ID}`` token. Django's
    ``build_absolute_uri()`` percent-encodes braces, which prevents substitution.
    """
    query = 'session_id={CHECKOUT_SESSION_ID}'
    if extra_query:
        query = f'{query}&{extra_query.lstrip("&")}'
    return f'{request.scheme}://{request.get_host()}/payments/success/?{query}'


def _recover_gift_voucher_checkout(request, session_id, metadata, payment):
    """
    When Stripe's session id placeholder reaches the success page, recover the
    basket from the checkout session we stored server-side.
    """
    if not _is_stripe_session_placeholder(session_id):
        return session_id, metadata, payment
    if request.GET.get('type') != 'gift_voucher':
        return session_id, metadata, payment

    basket_id = request.session.pop('gift_voucher_checkout_basket_id', None)
    if not basket_id:
        return session_id, metadata, payment

    recovered = Payment.objects.filter(
        metadata__gift_voucher_basket_id=str(basket_id),
    ).order_by('-id').first()
    if not recovered:
        return session_id, metadata, payment

    return recovered.stripe_id, dict(recovered.metadata or {}), recovered


def _populate_gift_voucher_success_context(context, metadata):
    from bookings.gift_voucher_basket import get_vouchers_for_basket
    from payments.gift_voucher_cards import get_active_gift_card_designs

    basket_id = int(metadata['gift_voucher_basket_id'])
    basket = get_basket(basket_id)
    if not basket or basket.get('basket_data', {}).get('type') != 'gift_voucher':
        return

    context['is_gift_voucher'] = True
    context['gift_voucher_basket'] = basket
    context['gift_voucher_basket_id'] = basket_id
    context['gift_voucher_codes'] = get_vouchers_for_basket(basket_id)
    context['gift_card_designs'] = list(get_active_gift_card_designs())
    context['gift_voucher_default_email'] = basket['basket_data'].get('purchaser_email') or ''


def _populate_success_from_bookings(context, bookings):
    booking_list = list(bookings)
    if not booking_list:
        return
    if len(booking_list) == 1:
        context['booking'] = booking_list[0]
    else:
        context['bookings'] = booking_list


def _attach_facebook_share_for_success(request, context):
    """Facebook share cards for signed-in students on the payment success page."""
    if not is_customer_authenticated(request):
        return

    booking_list = []
    if context.get('bookings'):
        booking_list = list(context['bookings'])
    elif context.get('booking'):
        booking_list = [context['booking']]
    if not booking_list:
        return

    from bookings.social_media import facebook_share_items_for_bookings

    items = facebook_share_items_for_bookings(booking_list, request)
    if items:
        context['facebook_share_items'] = items


class PaymentSuccessView(TemplateView):
    """Payment success page."""
    template_name = 'payments/success.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = self.request.GET.get('session_id')
        context['is_gift_voucher'] = self.request.GET.get('type') == 'gift_voucher'
        context['session_id'] = session_id

        checkout_data = load_bookings_from_checkout_context(self.request)
        checkout_session_data = get_checkout_success_context(self.request)

        if not session_id:
            if checkout_data.exists():
                _populate_success_from_bookings(context, checkout_data)
                _attach_account_setup_context(
                    self.request, context, checkout_data, checkout_session_data,
                )
            _attach_facebook_share_for_success(self.request, context)
            return context

        payment = None
        metadata = {}
        if not _is_stripe_session_placeholder(session_id):
            payment = Payment.objects.filter(stripe_id=session_id).first()
            metadata = dict((payment.metadata if payment else {}) or {})
            stripe_session = None

            if STRIPE_AVAILABLE and payment and payment.intent_type == 'checkout_session':
                try:
                    stripe_session = stripe.checkout.Session.retrieve(session_id)
                    metadata.update(stripe_metadata_dict(stripe_session.metadata))
                except stripe.error.StripeError:
                    pass

            if payment and payment.status != 'succeeded':
                complete_checkout_session(
                    stripe_session or {
                        'id': session_id,
                        'payment_status': 'paid',
                        'status': 'complete',
                        'metadata': metadata,
                    },
                    source='checkout.session.completed (success_page)',
                )
                payment.refresh_from_db()
                metadata = dict(payment.metadata or metadata)
        else:
            session_id, metadata, payment = _recover_gift_voucher_checkout(
                self.request, session_id, metadata, payment,
            )
            if session_id and payment:
                context['session_id'] = session_id
                if payment.status != 'succeeded':
                    complete_checkout_session(
                        {
                            'id': session_id,
                            'payment_status': 'paid',
                            'status': 'complete',
                            'metadata': metadata,
                        },
                        source='checkout.session.completed (success_page)',
                    )
                    payment.refresh_from_db()
                    metadata = dict(payment.metadata or metadata)

        if 'gift_voucher_basket_id' in metadata:
            try:
                _populate_gift_voucher_success_context(context, metadata)
            except (ValueError, TypeError):
                pass
            return context

        bookings = _load_bookings_from_payment_metadata(metadata)
        if not bookings.exists() and checkout_data.exists():
            bookings = checkout_data

        if bookings.exists():
            booking_list = list(bookings)
            _populate_success_from_bookings(context, booking_list)
            _attach_account_setup_context(
                self.request, context, booking_list, checkout_session_data,
            )
        elif checkout_session_data:
            context['checkout_pending'] = True
            _attach_account_setup_context(
                self.request, context, None, checkout_session_data,
            )

        _attach_facebook_share_for_success(self.request, context)
        return context


class GiftVoucherCardDownloadView(View):
    """Download a rendered gift card PNG for a paid voucher basket."""

    def get(self, request, basket_id):
        from payments.gift_voucher_cards import (
            render_gift_voucher_card,
            verify_gift_voucher_session_access,
        )

        session_id = request.GET.get('session_id', '')
        if not verify_gift_voucher_session_access(session_id, basket_id):
            return HttpResponse('Not found.', status=404)

        design_id = request.GET.get('design')
        if not design_id:
            return HttpResponse('Please choose a design.', status=400)

        try:
            voucher_index = int(request.GET.get('voucher', 0))
        except (TypeError, ValueError):
            voucher_index = 0

        png_bytes, code = render_gift_voucher_card(basket_id, voucher_index, design_id)
        if request.GET.get('preview') == '1':
            from website.gift_card_render import shrink_png_bytes
            png_bytes = shrink_png_bytes(png_bytes)
        response = HttpResponse(png_bytes, content_type='image/png')
        disposition = 'inline' if request.GET.get('preview') == '1' else 'attachment'
        response['Content-Disposition'] = f'{disposition}; filename="gift-voucher-{code}.png"'
        return response


class GiftVoucherCardEmailView(View):
    """Email a rendered gift card to the purchaser or another address."""

    def post(self, request, basket_id):
        from payments.gift_voucher_cards import verify_gift_voucher_session_access
        from payments.tasks import send_gift_voucher_card_email

        session_id = request.POST.get('session_id', '')
        if not verify_gift_voucher_session_access(session_id, basket_id):
            return HttpResponse('Not found.', status=404)

        email = (request.POST.get('email') or '').strip()
        design_id = request.POST.get('design')
        if not email or not design_id:
            messages.error(request, 'Please choose a design and enter an email address.')
            return redirect(
                f"{reverse('payments:success')}?session_id={session_id}&type=gift_voucher"
            )

        try:
            voucher_index = int(request.POST.get('voucher', 0))
        except (TypeError, ValueError):
            voucher_index = 0

        if send_gift_voucher_card_email(basket_id, voucher_index, design_id, email):
            messages.success(request, f'Gift card sent to {email}.')
        else:
            messages.error(request, 'We could not send the gift card. Please try again or contact us.')

        return redirect(
            f"{reverse('payments:success')}?session_id={session_id}&type=gift_voucher"
        )


class PaymentCancelView(TemplateView):
    """Payment cancellation page."""
    template_name = 'payments/cancel.html'
