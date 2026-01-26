"""
URL configuration for bookings app.
"""
from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # Booking creation (server-rendered form)
    path('create/<int:instance_id>/', views.CreateBookingView.as_view(), name='create'),
    
    # Booking confirmation
    path('confirm/<str:booking_ref>/', views.BookingConfirmationView.as_view(), name='confirm'),
    
    # API endpoints for React components
    path('api/create/', views.CreateBookingAPIView.as_view(), name='api_create'),
]
