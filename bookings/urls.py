"""
URL configuration for bookings app.
"""
from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('create/<int:instance_id>/', views.CreateBookingView.as_view(), name='create'),
    path('basket/', views.BookingBasketView.as_view(), name='basket'),
    path('basket/remove/<str:item_id>/', views.BookingBasketRemoveView.as_view(), name='basket_remove'),
    path('basket/update/<str:item_id>/', views.BookingBasketUpdateView.as_view(), name='basket_update'),
    path('basket/checkout/', views.BookingBasketCheckoutView.as_view(), name='basket_checkout'),
    path('confirm/<str:booking_ref>/', views.BookingConfirmationView.as_view(), name='confirm'),
    
    # API endpoints for React components
    path('api/create/', views.CreateBookingAPIView.as_view(), name='api_create'),
]
