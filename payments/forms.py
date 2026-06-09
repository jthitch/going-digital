from django import forms


class VoucherCheckoutForm(forms.Form):
    voucher_code = forms.CharField(
        max_length=255,
        required=False,
        label='Voucher or promo code',
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter voucher code',
            'autocomplete': 'off',
        }),
    )
