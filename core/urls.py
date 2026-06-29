"""Student account URLs."""
from django.urls import path

from core.views_student import (
    CompleteAccountSetupView,
    StudentLoginView,
    StudentSignupView,
    booking_calendar_ics,
    my_bookings,
    post_booking_community,
    student_logout,
)

app_name = 'account'

urlpatterns = [
    path('login/', StudentLoginView.as_view(), name='login'),
    path('signup/', StudentSignupView.as_view(), name='signup'),
    path('complete-setup/', CompleteAccountSetupView.as_view(), name='complete_setup'),
    path('join-community/', post_booking_community, name='post_booking_community'),
    path('logout/', student_logout, name='logout'),
    path('my-bookings/', my_bookings, name='my_bookings'),
    path(
        'my-bookings/<str:booking_reference>/calendar.ics',
        booking_calendar_ics,
        name='booking_calendar',
    ),
]
