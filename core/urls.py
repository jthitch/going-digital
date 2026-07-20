"""Student account URLs."""
from django.urls import path

from core.views_student import (
    CompleteAccountSetupView,
    CustomerPasswordResetCompleteView,
    CustomerPasswordResetConfirmView,
    CustomerPasswordResetDoneView,
    CustomerPasswordResetView,
    StudentLoginView,
    StudentSignupView,
    booking_calendar_ics,
    edit_booking_camera,
    my_bookings,
    post_booking_attendee_details,
    post_booking_community,
    student_logout,
)

app_name = 'account'

urlpatterns = [
    path('login/', StudentLoginView.as_view(), name='login'),
    path('signup/', StudentSignupView.as_view(), name='signup'),
    path('password-reset/', CustomerPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/sent/', CustomerPasswordResetDoneView.as_view(), name='password_reset_done'),
    path(
        'password-reset/confirm/<str:token>/',
        CustomerPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        CustomerPasswordResetCompleteView.as_view(),
        name='password_reset_complete',
    ),
    path('complete-setup/', CompleteAccountSetupView.as_view(), name='complete_setup'),
    path('booking-details/', post_booking_attendee_details, name='post_booking_attendee_details'),
    path('join-community/', post_booking_community, name='post_booking_community'),
    path('logout/', student_logout, name='logout'),
    path('my-bookings/', my_bookings, name='my_bookings'),
    path(
        'my-bookings/<str:booking_reference>/camera/',
        edit_booking_camera,
        name='edit_booking_camera',
    ),
    path(
        'my-bookings/<str:booking_reference>/calendar.ics',
        booking_calendar_ics,
        name='booking_calendar',
    ),
]
