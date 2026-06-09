"""Student account URLs."""
from django.urls import path

from core.views_student import (
    CompleteAccountSetupView,
    StudentLoginView,
    StudentLogoutView,
    StudentSignupView,
    my_bookings,
)

app_name = 'account'

urlpatterns = [
    path('login/', StudentLoginView.as_view(), name='login'),
    path('signup/', StudentSignupView.as_view(), name='signup'),
    path('complete-setup/', CompleteAccountSetupView.as_view(), name='complete_setup'),
    path('logout/', StudentLogoutView.as_view(), name='logout'),
    path('my-bookings/', my_bookings, name='my_bookings'),
]
