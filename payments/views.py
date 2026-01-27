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
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.views import View
from bookings.models import Booking
from .models import Payment
from .tasks import send_booking_confirmation_email, send_payment_success_email

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
                            'name': f"{booking.course_instance.course.title} - {booking.course_instance.location.city}",
                            'description': f"Course on {booking.course_instance.start_date.strftime('%B %d, %Y')}",
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
            self.handle_checkout_session_completed(session)
        elif event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            self.handle_payment_intent_succeeded(payment_intent)
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            self.handle_payment_intent_failed(payment_intent)
        
        return HttpResponse(status=200)
    
    def handle_checkout_session_completed(self, session):
        """Handle successful checkout session."""
        try:
            payment = Payment.objects.get(stripe_id=session.id)
            payment.status = 'succeeded'
            payment.succeeded_at = timezone.now()
            payment.webhook_processed = True
            payment.last_webhook_event = 'checkout.session.completed'
            payment.save()
            
            # Update booking
            if payment.metadata and 'booking_id' in payment.metadata:
                booking = Booking.objects.get(id=payment.metadata['booking_id'])
                booking.status = 'confirmed'
                booking.save()
                
            # Update course instance student count
            booking.course_instance.current_students += 1
            booking.course_instance.save()
            
            # Send confirmation emails (call directly, not with .delay())
            send_booking_confirmation_email(booking.id)
            send_payment_success_email(booking.id)
                
        except (Payment.DoesNotExist, Booking.DoesNotExist, KeyError) as e:
            # Log error
            print(f"Error handling checkout session: {e}")
    
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
        if session_id and STRIPE_AVAILABLE:
            try:
                session = stripe.checkout.Session.retrieve(session_id)
                if session.metadata and 'booking_id' in session.metadata:
                    from bookings.models import Booking
                    try:
                        booking = Booking.objects.get(id=session.metadata['booking_id'])
                        context['booking'] = booking
                    except Booking.DoesNotExist:
                        pass
            except stripe.error.StripeError:
                pass
        return context


class PaymentCancelView(TemplateView):
    """Payment cancellation page."""
    template_name = 'payments/cancel.html'
