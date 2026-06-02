"""
Payment views - Stripe integration.
"""
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    stripe = None

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse, JsonResponse
from django.views import View
from bookings.models import Booking
from bookings.gift_voucher_basket import get_basket
from .checkout_completion import complete_checkout_session
from .models import Payment

# Configure Stripe if available
if STRIPE_AVAILABLE and hasattr(settings, 'STRIPE_SECRET_KEY'):
    stripe.api_key = settings.STRIPE_SECRET_KEY


class CreateCheckoutSessionView(View):
    """Create Stripe Checkout Session for booking."""
    
    def dispatch(self, request, *args, **kwargs):
        """Handle both GET and POST requests for easier testing."""
        if request.method == 'GET':
            return self.post(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, booking_id):
        if not STRIPE_AVAILABLE:
            return JsonResponse({'error': 'Stripe is not configured. Please install stripe and set STRIPE_SECRET_KEY in settings.'}, status=503)
        
        # In dev mode, allow booking without authentication
        if request.user.is_authenticated:
            booking = get_object_or_404(Booking, id=booking_id, user=request.user, status='pending')
        else:
            booking = get_object_or_404(Booking, id=booking_id, status='pending')
        
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'gbp',
                        'product_data': {
                            'name': f"{booking.workshop.course.title if booking.workshop.course else 'Workshop'} - {booking.workshop.venue.name if booking.workshop.venue else 'TBC'}",
                            'description': f"Course on {booking.workshop.start_date.strftime('%d %B %Y')}",
                        },
                        'unit_amount': int(booking.price_paid * 100),  # Convert to cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri('/payments/success/?session_id={CHECKOUT_SESSION_ID}'),
                cancel_url=request.build_absolute_uri('/payments/cancel/'),
                metadata={
                    'booking_id': str(booking.id),
                    'booking_reference': booking.booking_reference,
                },
                customer_email=booking.student_email,
            )
            
            # Create payment record
            payment = Payment.objects.create(
                user=booking.user,
                intent_type='checkout_session',
                stripe_id=checkout_session.id,
                amount=booking.price_paid,
                currency='gbp',
                description=f"Booking {booking.booking_reference}",
                metadata={'booking_id': booking.id, 'booking_reference': booking.booking_reference}
            )
            
            booking.payment = payment
            booking.save()
            
            return redirect(checkout_session.url)
            
        except stripe.error.StripeError as e:
            return JsonResponse({'error': str(e)}, status=400)


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
                success_url=request.build_absolute_uri(
                    f'/payments/success/?session_id={{CHECKOUT_SESSION_ID}}&type=gift_voucher'
                ),
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


class PaymentSuccessView(TemplateView):
    """Payment success page."""
    template_name = 'payments/success.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = self.request.GET.get('session_id')
        context['is_gift_voucher'] = self.request.GET.get('type') == 'gift_voucher'

        if session_id and STRIPE_AVAILABLE:
            try:
                session = stripe.checkout.Session.retrieve(session_id)
                complete_checkout_session(
                    session,
                    source='checkout.session.completed (success_page)',
                )
                metadata = session.metadata or {}

                if 'gift_voucher_basket_id' in metadata:
                    try:
                        from bookings.gift_voucher_basket import get_vouchers_for_basket
                        basket_id = int(metadata['gift_voucher_basket_id'])
                        basket = get_basket(basket_id)
                        if basket and basket.get('basket_data', {}).get('type') == 'gift_voucher':
                            context['gift_voucher_basket'] = basket
                            context['gift_voucher_codes'] = get_vouchers_for_basket(basket_id)
                    except (ValueError, TypeError):
                        pass
                elif 'booking_id' in metadata:
                    try:
                        context['booking'] = Booking.objects.get(id=metadata['booking_id'])
                    except Booking.DoesNotExist:
                        pass
            except stripe.error.StripeError:
                pass
        return context


class PaymentCancelView(TemplateView):
    """Payment cancellation page."""
    template_name = 'payments/cancel.html'
