"""Student sign-in, sign-up, and my bookings."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View

from bookings.models import Booking

from core.forms_student import (
    CompleteAccountPasswordForm,
    StudentLoginForm,
    StudentSignupForm,
)
from core.student_auth import (
    account_setup_from_bookings,
    bookings_for_user,
    link_bookings_to_user,
    resolve_student_user_for_email,
    user_needs_account_setup,
)


def _safe_next_url(request, fallback):
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return fallback


class StudentLoginView(View):
    template_name = 'account/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(_safe_next_url(request, reverse('account:my_bookings')))
        return render(request, self.template_name, {
            'form': StudentLoginForm(),
            'next': request.GET.get('next', ''),
        })

    def post(self, request):
        if request.user.is_authenticated:
            return redirect(_safe_next_url(request, reverse('account:my_bookings')))

        form = StudentLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user, backend='core.backends.EmailBackend')
            link_bookings_to_user(user)
            messages.success(request, 'Welcome back.')
            return redirect(_safe_next_url(request, reverse('account:my_bookings')))

        return render(request, self.template_name, {
            'form': form,
            'next': request.POST.get('next', ''),
        })


class StudentSignupView(View):
    template_name = 'account/signup.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(reverse('account:my_bookings'))
        return render(request, self.template_name, {'form': StudentSignupForm()})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect(reverse('account:my_bookings'))

        form = StudentSignupForm(request.POST)
        if form.is_valid():
            user, created = form.save()
            login(request, user, backend='core.backends.EmailBackend')
            if created:
                messages.success(request, 'Your account has been created.')
            else:
                messages.success(
                    request,
                    'Your account is ready — we linked your previous bookings.',
                )
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
        user = resolve_student_user_for_email(email)
        if not user or not user_needs_account_setup(user):
            return None
        booking = Booking.objects.filter(student_email__iexact=email).order_by('-created_at').first()
        if booking:
            return account_setup_from_bookings([booking])
        return {
            'email': email,
            'firstname': user.firstname or '',
            'lastname': user.lastname or '',
            'user': user,
            'booking_reference': '',
        }

    @staticmethod
    def _prime_session_from_booking_ref(request):
        ref = (request.GET.get('ref') or request.POST.get('ref') or '').strip()
        if not ref:
            return
        booking = Booking.objects.filter(booking_reference=ref).first()
        if booking and booking.student_email:
            request.session['account_setup_email'] = booking.student_email.strip().lower()

    def get(self, request):
        if request.user.is_authenticated:
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
        if request.user.is_authenticated:
            return redirect(reverse('account:my_bookings'))

        self._prime_session_from_booking_ref(request)
        email = (request.POST.get('email') or '').strip().lower()
        setup = self._build_setup(request, email=email)
        if not setup:
            messages.error(request, 'Unable to complete account setup. Please sign in or contact us.')
            return redirect(reverse('account:login'))

        form = CompleteAccountPasswordForm(request.POST, setup=setup)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='core.backends.EmailBackend')
            request.session.pop('account_setup_email', None)
            from payments.checkout_session_context import clear_checkout_success_context
            clear_checkout_success_context(request)
            messages.success(
                request,
                'Your account is ready. You can view your bookings any time.',
            )
            return redirect(reverse('account:my_bookings'))

        return render(request, self.template_name, {
            'setup': setup,
            'form': form,
        })


class StudentLogoutView(LogoutView):
    next_page = reverse_lazy('courses:homepage')

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


@login_required(login_url='account:login')
def my_bookings(request):
    all_bookings = list(bookings_for_user(request.user).order_by('-created_at'))
    upcoming = []
    past = []
    cancelled = []
    for booking in all_bookings:
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
    })
