"""
URL configuration for payments app.
"""
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Stripe Checkout
    path('checkout/<int:booking_id>/', views.CreateCheckoutSessionView.as_view(), name='create_checkout'),
    path('checkout/gift-voucher/<int:basket_id>/', views.CreateGiftVoucherCheckoutView.as_view(), name='create_gift_voucher_checkout'),
    
    # Stripe webhooks
    path('webhook/', views.StripeWebhookView.as_view(), name='webhook'),
    
    # Payment success/cancel
    path('success/', views.PaymentSuccessView.as_view(), name='success'),
    path('cancel/', views.PaymentCancelView.as_view(), name='cancel'),
]
