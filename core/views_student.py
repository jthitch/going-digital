"""Student sign-in, sign-up, and my bookings (gd_customer session auth)."""
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from bookings.models import Booking

from bookings.calendar import attach_calendar_to_booking, calendar_data_for_booking
from bookings.suggested_courses import suggested_courses_for_user_bookings
from bookings.tutor_contact import attach_tutor_contact_to_booking
from bookings.social_media import attach_facebook_share_to_booking

from core.customer_auth import (
    customer_login_required,
    is_customer_authenticated,
    login_customer,
    logout_customer,
)
from core.forms_student import (
    CompleteAccountPasswordForm,
    StudentLoginForm,
    StudentSignupForm,
)
from core.student_auth import (
    account_setup_from_bookings,
    bookings_for_customer,
    customer_needs_account_setup,
    link_bookings_to_customer,
    resolve_customer_for_email,
)


def _safe_next_url(request, fallback):
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return fallback


class StudentLoginView(View):
    template_name = 'account/login.html'

    def get(self, request):
        if is_customer_authenticated(request):
            return redirect(_safe_next_url(request, reverse('account:my_bookings')))
        return render(request, self.template_name, {
            'form': StudentLoginForm(),
            'next': request.GET.get('next', ''),
        })

    def post(self, request):
        if is_customer_authenticated(request):
            return redirect(_safe_next_url(request, reverse('account:my_bookings')))

        form = StudentLoginForm(request, data=request.POST)
        if form.is_valid():
            customer = form.get_customer()
            login_customer(request, customer)
            link_bookings_to_customer(customer)
            messages.success(request, 'Welcome back.')
            return redirect(_safe_next_url(request, reverse('account:my_bookings')))

        return render(request, self.template_name, {
            'form': form,
            'next': request.POST.get('next', ''),
        })


class StudentSignupView(View):
    template_name = 'account/signup.html'

    def get(self, request):
        if is_customer_authenticated(request):
            return redirect(reverse('account:my_bookings'))
        return render(request, self.template_name, {'form': StudentSignupForm()})

    def post(self, request):
        if is_customer_authenticated(request):
            return redirect(reverse('account:my_bookings'))

        form = StudentSignupForm(request.POST)
        if form.is_valid():
            customer, created = form.save()
            login_customer(request, customer)
            if created:
                messages.success(request, 'Your account has been created.')
            else:
                messages.success(
                    request,
                    'Your account is ready — we linked your previous bookings.',
                )
            if bookings_for_customer(customer).filter(status='confirmed').exists():
                return redirect(reverse('account:post_booking_community'))
            return redirect(reverse('account:my_bookings'))

        return render(request, self.template_name, {'form': form})


def _session_account_setup_email(request):
    return (request.session.get('account_setup_email') or '').strip().lower()


def _authorise_account_setup_email(request, email):
    """Allow setup only for the email stored at checkout or a matching booking ref."""
    email = (email or '').strip().lower()
    if not email:
        return False
    if _session_account_setup_email(request) == email:
        return True
    from payments.checkout_session_context import get_checkout_success_context

    checkout_ctx = get_checkout_success_context(request)
    if (checkout_ctx.get('email') or '').strip().lower() == email:
        return True
    booking_ref = (request.GET.get('ref') or request.POST.get('ref') or '').strip()
    if booking_ref:
        return Booking.objects.filter(
            booking_reference=booking_ref,
            student_email__iexact=email,
        ).exists()
    return False


class CompleteAccountSetupView(View):
    """Let a student set a password immediately after booking."""
    template_name = 'account/complete_setup.html'

    def _build_setup(self, request, email=None):
        email = (email or _session_account_setup_email(request) or '').strip().lower()
        if not email or not _authorise_account_setup_email(request, email):
            return None
        booking = Booking.objects.filter(student_email__iexact=email).order_by('-created_at').first()
        if booking:
            return account_setup_from_bookings([booking])
        customer = resolve_customer_for_email(email)
        if not customer or not customer_needs_account_setup(customer):
            return None
        return {
            'email': email,
            'firstname': customer.firstname or '',
            'lastname': customer.lastname or '',
            'customer': customer,
            'booking_reference': '',
        }

    @staticmethod
    def _prime_session_from_booking_ref(request):
        """
        Store account-setup email only when the browser already proved access
        (checkout session) or supplies a matching email with the booking ref.
        """
        ref = (request.GET.get('ref') or request.POST.get('ref') or '').strip()
        if not ref:
            return
        booking = Booking.objects.filter(booking_reference=ref).first()
        if not booking or not booking.student_email:
            return

        student_email = booking.student_email.strip().lower()
        from payments.checkout_session_context import load_bookings_from_checkout_context

        checkout_bookings = load_bookings_from_checkout_context(request)
        if any(item.pk == booking.pk for item in checkout_bookings):
            request.session['account_setup_email'] = student_email
            return

        supplied_email = (
            request.GET.get('email')
            or request.POST.get('email')
            or ''
        ).strip().lower()
        if supplied_email and supplied_email == student_email:
            request.session['account_setup_email'] = student_email

    def get(self, request):
        if is_customer_authenticated(request):
            return redirect(reverse('account:my_bookings'))
        self._prime_session_from_booking_ref(request)
        setup = self._build_setup(request)
        if not setup:
            messages.info(request, 'Sign in or create an account to view your bookings.')
            return redirect(reverse('account:login'))
        return render(request, self.template_name, {
            'setup': setup,
            'form': CompleteAccountPasswordForm(setup=setup),
        })

    def post(self, request):
        if is_customer_authenticated(request):
            return redirect(reverse('account:my_bookings'))

        self._prime_session_from_booking_ref(request)
        email = (request.POST.get('email') or '').strip().lower()
        setup = self._build_setup(request, email=email)
        if not setup:
            messages.error(request, 'Unable to complete account setup. Please sign in or contact us.')
            return redirect(reverse('account:login'))

        form = CompleteAccountPasswordForm(request.POST, setup=setup)
        if form.is_valid():
            customer = form.save()
            login_customer(request, customer)
            request.session.pop('account_setup_email', None)
            from payments.checkout_session_context import clear_checkout_success_context
            clear_checkout_success_context(request)
            messages.success(
                request,
                'Your account is ready. You can view your bookings any time.',
            )
            community_url = reverse('account:post_booking_community')
            booking_ref = (setup.get('booking_reference') or '').strip()
            if booking_ref:
                community_url = f'{community_url}?ref={booking_ref}'
            return redirect(community_url)

        return render(request, self.template_name, {
            'setup': setup,
            'form': form,
        })


def student_logout(request):
    logout_customer(request)
    messages.success(request, 'You have been signed out.')
    return redirect('courses:homepage')


def _prime_community_session_from_booking_ref(request):
    ref = (request.GET.get('ref') or '').strip()
    if not ref:
        return
    booking = Booking.objects.filter(booking_reference=ref).first()
    if booking and booking.student_email:
        request.session['account_setup_email'] = booking.student_email.strip().lower()


def _bookings_for_community_page(request):
    if is_customer_authenticated(request):
        customer = request.customer
        return list(
            bookings_for_customer(customer)
            .select_related('workshop', 'workshop__course', 'workshop__venue')
            .filter(status='confirmed')
            .order_by('-created_at')[:5]
        )

    from payments.checkout_session_context import load_bookings_from_checkout_context

    bookings = list(load_bookings_from_checkout_context(request))
    if bookings:
        return bookings

    ref = (request.GET.get('ref') or '').strip()
    if not ref:
        return []
    booking = Booking.objects.filter(booking_reference=ref).select_related(
        'workshop', 'workshop__course', 'workshop__venue',
    ).first()
    return [booking] if booking else []


def _authorise_post_booking_community(request, bookings):
    if is_customer_authenticated(request):
        return True
    if not bookings:
        return False

    from payments.checkout_session_context import get_checkout_success_context

    email = (
        _session_account_setup_email(request)
        or get_checkout_success_context(request).get('email')
        or ''
    ).strip().lower()
    if not email:
        return False
    return any((b.student_email or '').strip().lower() == email for b in bookings)


def post_booking_community(request):
    """Invite students to join Facebook groups after checkout or account setup."""
    from bookings.social_media import (
        facebook_community_cards_from_groups_context,
        facebook_groups_context_for_bookings,
        facebook_share_items_for_bookings,
    )

    _prime_community_session_from_booking_ref(request)
    bookings = _bookings_for_community_page(request)
    if not _authorise_post_booking_community(request, bookings):
        messages.info(request, 'Sign in or complete checkout to view this page.')
        return redirect(reverse('account:login'))

    context = facebook_groups_context_for_bookings(bookings)
    context['facebook_community_cards'] = facebook_community_cards_from_groups_context(context)
    context['facebook_share_items'] = facebook_share_items_for_bookings(bookings, request)

    primary = bookings[0] if bookings else None
    context['account_ready'] = is_customer_authenticated(request)
    context['booking_reference'] = primary.booking_reference if primary else ''
    return render(request, 'account/post_booking_community.html', context)


@customer_login_required
def my_bookings(request):
    customer = request.customer
    all_bookings = list(bookings_for_customer(customer).order_by('-created_at'))
    upcoming = []
    past = []
    cancelled = []
    facebook_share_bookings = []
    for booking in all_bookings:
        attach_calendar_to_booking(booking)
        attach_tutor_contact_to_booking(booking)
        attach_facebook_share_to_booking(booking, request)
        if booking.facebook_share and booking.status != 'cancelled':
            facebook_share_bookings.append(booking)
        if booking.status == 'cancelled':
            cancelled.append(booking)
            continue
        if booking.workshop and booking.workshop.start_date and booking.is_past_course_start():
            past.append(booking)
        else:
            upcoming.append(booking)

    return render(request, 'account/my_bookings.html', {
        'upcoming_bookings': upcoming,
        'past_bookings': past,
        'cancelled_bookings': cancelled,
        'booking_count': len(all_bookings),
        'suggested_courses': suggested_courses_for_user_bookings(all_bookings),
        'facebook_share_bookings': facebook_share_bookings,
    })


@customer_login_required
def booking_calendar_ics(request, booking_reference):
    """Download .ics calendar file for a booking."""
    customer = request.customer
    booking = get_object_or_404(
        Booking.objects.select_related('workshop', 'workshop__course', 'workshop__venue'),
        booking_reference=booking_reference,
    )
    if not bookings_for_customer(customer).filter(pk=booking.pk).exists():
        raise Http404

    calendar = calendar_data_for_booking(booking)
    if not calendar.get('calendar_ics'):
        raise Http404

    response = HttpResponse(
        calendar['calendar_ics'],
        content_type='text/calendar; charset=utf-8',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="{calendar["calendar_ics_filename"]}"'
    )
    return response
