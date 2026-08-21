"""
URL configuration for bookings app.
"""
from django.urls import path
from . import follow_up_views, views

app_name = 'bookings'

urlpatterns = [
    path('create/<int:instance_id>/', views.CreateBookingView.as_view(), name='create'),
    path('basket/', views.BookingBasketView.as_view(), name='basket'),
    path('basket/remove/<str:item_id>/', views.BookingBasketRemoveView.as_view(), name='basket_remove'),
    path('basket/update/<str:item_id>/', views.BookingBasketUpdateView.as_view(), name='basket_update'),
    path('basket/voucher/', views.BookingBasketVoucherView.as_view(), name='basket_voucher'),
    path('basket/checkout/', views.BookingBasketCheckoutView.as_view(), name='basket_checkout'),
    path('confirm/<str:booking_ref>/', views.BookingConfirmationView.as_view(), name='confirm'),
    path(
        'follow-up/<str:token>/rate/<int:rating>/',
        follow_up_views.FollowUpRateView.as_view(),
        name='follow_up_rate',
    ),
    path(
        'follow-up/<str:token>/feedback/',
        follow_up_views.FollowUpFeedbackView.as_view(),
        name='follow_up_feedback',
    ),
    path(
        'follow-up/<str:token>/thanks/',
        follow_up_views.FollowUpThanksView.as_view(),
        name='follow_up_thanks',
    ),

    # API endpoints for React components
    path('api/create/', views.CreateBookingAPIView.as_view(), name='api_create'),
]
