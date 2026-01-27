"""
Booking views - server-rendered forms for SEO.
"""
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from courses.models import CourseInstance
from .models import Booking
from .forms import BookingForm


class CreateBookingView(CreateView):
    """
    Server-rendered booking form.
    In dev mode, allows booking without authentication.
    """
    model = Booking
    form_class = BookingForm
    template_name = 'bookings/create_booking.html'
    
    def dispatch(self, request, *args, **kwargs):
        # In dev mode, allow unauthenticated users
        if not settings.DEBUG and not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        return super().dispatch(request, *args, **kwargs)
    
    def get_course_instance(self):
        """Get the course instance for this booking."""
        instance_id = self.kwargs.get('instance_id')
        return get_object_or_404(CourseInstance, id=instance_id, enrollment_open=True)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['course_instance'] = self.get_course_instance()
        # Pass user only if authenticated, otherwise pass None
        kwargs['user'] = self.request.user if self.request.user.is_authenticated else None
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course_instance'] = self.get_course_instance()
        return context
    
    def form_valid(self, form):
        """Create booking and redirect to payment."""
        booking = form.save(commit=False)
        booking.course_instance = self.get_course_instance()
        # In dev mode, allow anonymous users (create a user if needed)
        if self.request.user.is_authenticated:
            booking.user = self.request.user
        else:
            # For dev mode: create or get an anonymous user
            from core.models import User
            anonymous_user, _ = User.objects.get_or_create(
                username='anonymous',
                defaults={'email': form.cleaned_data.get('student_email', 'anonymous@example.com')}
            )
            booking.user = anonymous_user
        booking.price_paid = booking.course_instance.price
        booking.save()
        
        # Redirect to payment
        return redirect('payments:create_checkout', booking_id=booking.id)


class BookingConfirmationView(LoginRequiredMixin, DetailView):
    """
    Booking confirmation page.
    """
    model = Booking
    template_name = 'bookings/confirmation.html'
    context_object_name = 'booking'
    slug_field = 'booking_reference'
    slug_url_kwarg = 'booking_ref'
    
    def get_queryset(self):
        """Ensure user can only view their own bookings."""
        return Booking.objects.filter(user=self.request.user)


class CreateBookingAPIView(APIView):
    """
    API endpoint for React booking component (progressive enhancement).
    """
    permission_classes = []  # Will be handled by React component authentication
    
    def post(self, request):
        # This would be implemented for React component
        # For now, return a placeholder
        return Response(
            {'message': 'API endpoint for React booking component'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
