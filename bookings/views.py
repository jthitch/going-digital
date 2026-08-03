"""
Booking views - server-rendered forms for SEO.
"""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, TemplateView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Workshop

from .forms import BasketCheckoutForm, BookingForm
from .models import Booking
from .terms_acceptance import record_basket_terms_acceptance
from core.customer_auth import is_customer_authenticated
from core.student_auth import customer_can_view_booking
from .workshop_basket import (
    add_item_to_basket,
    apply_voucher_to_session_basket,
    clear_voucher_from_session_basket,
    get_basket_lines,
    get_session_basket,
    loan_cameras_reserved_in_basket,
    load_workshops_for_basket,
    prepare_checkout_from_session,
    remove_item_from_basket,
    save_session_basket,
    update_item_quantity,
)
from payments.forms import VoucherCheckoutForm


class CreateBookingView(CreateView):
    """
    Add a workshop (with one or more places) to the session basket.
    """
    model = Booking
    form_class = BookingForm
    template_name = 'bookings/create_booking.html'

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_workshop(self):
        from courses.display_images import attach_gd_images_to_workshops

        instance_id = self.kwargs.get('instance_id')
        workshop = get_object_or_404(
            Workshop.objects.select_related('course', 'course__image', 'venue').prefetch_related(
                'course__media',
                'gallery_images__image',
            ),
            id=instance_id,
            active=1,
        )
        attach_gd_images_to_workshops([workshop])
        return workshop

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['workshop'] = self.get_workshop()
        from core.customer_auth import get_logged_in_customer
        from bookings.workshop_basket import get_session_basket

        kwargs['customer'] = get_logged_in_customer(self.request)
        kwargs['basket'] = get_session_basket(self.request)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workshop = self.get_workshop()
        context['course_instance'] = workshop
        context['basket_summary'] = get_basket_lines(self.request)
        context['loan_cameras_available'] = workshop.has_loan_cameras_available
        if workshop.has_loan_cameras_available:
            reserved = loan_cameras_reserved_in_basket(
                get_session_basket(self.request),
                workshop.pk,
            )
            context['loan_cameras_remaining'] = max(
                0,
                workshop.loan_cameras_remaining() - reserved,
            )
        else:
            context['loan_cameras_remaining'] = 0
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
            message = exc.messages[0] if exc.messages else str(exc)
            form.add_error('quantity', message)
            return self.form_invalid(form)

        qty = form.cleaned_data['quantity']
        messages.success(
            self.request,
            f'Added {qty} place{"s" if qty != 1 else ""} to your basket.',
        )
        return redirect('bookings:basket')


class BookingBasketView(TemplateView):
    template_name = 'bookings/basket.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_basket_lines(self.request))
        basket = get_session_basket(self.request)
        context['voucher_form'] = VoucherCheckoutForm(
            initial={'voucher_code': basket.get('voucher_code', '')},
        )
        context['checkout_form'] = BasketCheckoutForm()
        return context


class BookingBasketVoucherView(View):
    def post(self, request):
        action = request.POST.get('action', 'apply')
        if action == 'remove':
            basket = get_session_basket(request)
            clear_voucher_from_session_basket(basket)
            save_session_basket(request, basket)
            messages.info(request, 'Voucher removed.')
            return redirect('bookings:basket')

        form = VoucherCheckoutForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Please check the voucher code and try again.')
            return redirect('bookings:basket')

        code = (form.cleaned_data.get('voucher_code') or '').strip()
        if not code:
            messages.error(request, 'Please enter a voucher code.')
            return redirect('bookings:basket')

        try:
            basket = get_session_basket(request)
            workshops = load_workshops_for_basket(basket)
            apply_voucher_to_session_basket(basket, code, workshops)
            save_session_basket(request, basket)
            messages.success(request, 'Voucher applied.')
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
        return redirect('bookings:basket')


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
    """Create pending bookings from session basket and start payment."""

    def post(self, request):
        form = BasketCheckoutForm(request.POST)
        if not form.is_valid():
            message = form.errors.get('accept_terms', ['Please accept the terms and conditions to proceed.'])[0]
            messages.error(request, message)
            return redirect('bookings:basket')

        try:
            basket_id, booking_ids, customer = prepare_checkout_from_session(request)
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
            return redirect('bookings:basket')

        record_basket_terms_acceptance(
            request,
            customer=customer,
            basket_id=basket_id,
            booking_ids=booking_ids,
        )

        if form.cleaned_data.get('subscribe_newsletter') and customer.email:
            from core.customer_service import subscribe_customer_to_newsletter

            try:
                subscribe_customer_to_newsletter(customer.email)
            except (ValueError, ValidationError):
                pass

        from payments.views import initiate_workshop_basket_payment

        return initiate_workshop_basket_payment(request, basket_id)


class BookingConfirmationView(DetailView):
    model = Booking
    template_name = 'bookings/confirmation.html'
    context_object_name = 'booking'
    slug_field = 'booking_reference'
    slug_url_kwarg = 'booking_ref'

    def dispatch(self, request, *args, **kwargs):
        booking = get_object_or_404(
            Booking.objects.select_related(
                'workshop',
                'workshop__course',
                'workshop__venue',
                'payment',
            ),
            booking_reference=kwargs[self.slug_url_kwarg],
        )
        if not customer_can_view_booking(request, booking):
            if is_customer_authenticated(request):
                raise Http404('No booking found matching the query')
            login_url = reverse('account:login')
            return redirect(f'{login_url}?next={request.path}')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Booking.objects.select_related(
            'workshop',
            'workshop__course',
            'workshop__venue',
            'payment',
        )

    def get_context_data(self, **kwargs):
        from .social_media import (
            facebook_groups_context_for_booking,
            facebook_share_items_for_bookings,
        )

        context = super().get_context_data(**kwargs)
        booking = context['booking']
        context.update(facebook_groups_context_for_booking(booking))
        context['facebook_share_items'] = facebook_share_items_for_bookings(
            [booking],
            self.request,
        )
        from .franchisee_contract import franchisee_contract_notice

        context['franchisee_contract_notice'] = franchisee_contract_notice(booking.workshop)
        return context


class CreateBookingAPIView(APIView):
    permission_classes = []

    def post(self, request):
        return Response(
            {'message': 'API endpoint for React booking component'},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
