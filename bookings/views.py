"""
Booking views - server-rendered forms for SEO.
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, TemplateView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Workshop

from .forms import BookingForm
from .models import Booking
from .workshop_basket import (
    add_item_to_basket,
    get_basket_lines,
    prepare_checkout_from_session,
    remove_item_from_basket,
    update_item_quantity,
)


class CreateBookingView(CreateView):
    """
    Add a workshop (with one or more places) to the session basket.
    """
    model = Booking
    form_class = BookingForm
    template_name = 'bookings/create_booking.html'

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEBUG and not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        return super().dispatch(request, *args, **kwargs)

    def get_workshop(self):
        instance_id = self.kwargs.get('instance_id')
        return get_object_or_404(Workshop, id=instance_id, active=1)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['workshop'] = self.get_workshop()
        kwargs['user'] = self.request.user if self.request.user.is_authenticated else None
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course_instance'] = self.get_workshop()
        context['basket_summary'] = get_basket_lines(self.request)
        return context

    def form_valid(self, form):
        workshop = self.get_workshop()
        try:
            add_item_to_basket(
                self.request,
                workshop,
                form.cleaned_data,
                form.cleaned_data['quantity'],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0] if exc.messages else str(exc))
            return self.form_invalid(form)

        qty = form.cleaned_data['quantity']
        messages.success(
            self.request,
            f'Added {qty} place{"s" if qty != 1 else ""} to your basket.',
        )
        action = self.request.POST.get('action', 'basket')
        if action == 'checkout':
            return redirect('bookings:basket_checkout')
        return redirect('bookings:basket')


class BookingBasketView(TemplateView):
    template_name = 'bookings/basket.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_basket_lines(self.request))
        return context


class BookingBasketUpdateView(View):
    def post(self, request, item_id):
        quantity = request.POST.get('quantity', '1')
        try:
            update_item_quantity(request, item_id, quantity)
            messages.success(request, 'Basket updated.')
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
        return redirect('bookings:basket')


class BookingBasketRemoveView(View):
    def post(self, request, item_id):
        remove_item_from_basket(request, item_id)
        messages.info(request, 'Removed from basket.')
        return redirect('bookings:basket')


class BookingBasketCheckoutView(View):
    """Create pending bookings from session basket and start payment checkout."""

    def post(self, request):
        try:
            basket_id, _booking_ids = prepare_checkout_from_session(request)
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
            return redirect('bookings:basket')
        return redirect('payments:create_workshop_basket_checkout', basket_id=basket_id)


class BookingConfirmationView(LoginRequiredMixin, DetailView):
    model = Booking
    template_name = 'bookings/confirmation.html'
    context_object_name = 'booking'
    slug_field = 'booking_reference'
    slug_url_kwarg = 'booking_ref'

    def get_queryset(self):
        user = self.request.user
        email = (user.email or '').strip()
        qs = Booking.objects.filter(user=user)
        if email:
            qs = Booking.objects.filter(
                Q(user=user) | Q(student_email__iexact=email),
            )
        return qs.select_related('workshop', 'workshop__course', 'workshop__venue', 'payment')


class CreateBookingAPIView(APIView):
    permission_classes = []

    def post(self, request):
        return Response(
            {'message': 'API endpoint for React booking component'},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
