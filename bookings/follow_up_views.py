"""Day-after workshop follow-up: rate stars and optional feedback form."""
from django import forms
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from bookings.follow_up_email_copy import follow_up_email_copy
from bookings.models import Booking, WorkshopFeedback
from website.google_reviews import google_write_review_url


class FeedbackCommentForm(forms.Form):
    comment = forms.CharField(
        label='Your feedback',
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': 'What went well, and what could we improve?',
            'class': 'feedback-comment',
        }),
        max_length=5000,
        required=True,
    )


def _booking_for_token(token):
    token = (token or '').strip()
    if not token:
        raise Http404('Invalid link')
    return get_object_or_404(
        Booking.objects.select_related('workshop', 'workshop__course'),
        follow_up_token=token,
    )


def _record_rating(booking, rating):
    """Create or update WorkshopFeedback with the star rating. Returns the feedback row."""
    feedback, _created = WorkshopFeedback.objects.get_or_create(
        booking=booking,
        defaults={
            'workshop': booking.workshop,
            'rating': rating,
        },
    )
    if feedback.rating != rating:
        feedback.rating = rating
        feedback.workshop = booking.workshop
        feedback.save(update_fields=['rating', 'workshop', 'updated_at'])
    return feedback


class FollowUpRateView(View):
    """Record 1–5 star click from the follow-up email, then route the student."""

    def get(self, request, token, rating):
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            raise Http404('Invalid rating')
        if rating < 1 or rating > 5:
            raise Http404('Invalid rating')

        booking = _booking_for_token(token)
        if not booking.workshop_id:
            raise Http404('Booking has no workshop')

        _record_rating(booking, rating)

        if rating == 5:
            return redirect(google_write_review_url())

        return redirect('bookings:follow_up_feedback', token=token)


class FollowUpFeedbackView(View):
    """Collect written feedback after a 1–4 star rating."""

    template_name = 'bookings/follow_up_feedback.html'

    def get(self, request, token):
        booking = _booking_for_token(token)
        feedback = WorkshopFeedback.objects.filter(booking=booking).first()
        if feedback and feedback.rating == 5:
            return redirect(google_write_review_url())
        if feedback and (feedback.comment or '').strip():
            return redirect('bookings:follow_up_thanks', token=token)

        copy = follow_up_email_copy()
        form = FeedbackCommentForm()
        return render(request, self.template_name, {
            'booking': booking,
            'feedback': feedback,
            'form': form,
            'feedback_prompt': copy['feedback_prompt'],
            'course_title': (
                booking.workshop.course.title
                if booking.workshop and booking.workshop.course
                else 'your course'
            ),
        })

    def post(self, request, token):
        booking = _booking_for_token(token)
        feedback = WorkshopFeedback.objects.filter(booking=booking).first()
        if feedback and feedback.rating == 5:
            return redirect(google_write_review_url())
        if not feedback:
            return redirect('bookings:follow_up_rate', token=token, rating=3)
        if (feedback.comment or '').strip():
            return redirect('bookings:follow_up_thanks', token=token)

        form = FeedbackCommentForm(request.POST)
        copy = follow_up_email_copy()
        if not form.is_valid():
            return render(request, self.template_name, {
                'booking': booking,
                'feedback': feedback,
                'form': form,
                'feedback_prompt': copy['feedback_prompt'],
                'course_title': (
                    booking.workshop.course.title
                    if booking.workshop and booking.workshop.course
                    else 'your course'
                ),
            })

        feedback.comment = form.cleaned_data['comment'].strip()
        feedback.comment_submitted_at = timezone.now()
        feedback.save(update_fields=['comment', 'comment_submitted_at', 'updated_at'])
        return redirect('bookings:follow_up_thanks', token=token)


class FollowUpThanksView(View):
    template_name = 'bookings/follow_up_thanks.html'

    def get(self, request, token):
        booking = _booking_for_token(token)
        feedback = WorkshopFeedback.objects.filter(booking=booking).first()
        return render(request, self.template_name, {
            'booking': booking,
            'feedback': feedback,
        })
