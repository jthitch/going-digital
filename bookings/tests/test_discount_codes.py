from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from bookings.discount_codes import (
    calculate_discount_amount,
    validate_discount_code_for_basket,
)
from bookings.forms import DiscountCodeAdminForm
from bookings.models import DiscountCode
from bookings.workshop_basket import _allocate_discounts


def _code(**kwargs):
    defaults = {
        'id': 1,
        'code': 'SAVE10',
        'discount_type': DiscountCode.DISCOUNT_FIXED,
        'amount': Decimal('10.00'),
        'is_active': True,
        'expiry_date': None,
    }
    defaults.update(kwargs)
    code = SimpleNamespace(**defaults)
    workshops = MagicMock()
    workshops.filter.return_value.exists.return_value = True
    workshops.values_list.return_value = [10]
    code.workshops = workshops
    return code


class DiscountCodeCalculationTests(SimpleTestCase):
    def test_fixed_amount_capped_at_eligible_total(self):
        code = _code(discount_type=DiscountCode.DISCOUNT_FIXED, amount=Decimal('50'))
        self.assertEqual(calculate_discount_amount(code, Decimal('40')), Decimal('40.00'))

    def test_percent_off(self):
        code = _code(discount_type=DiscountCode.DISCOUNT_PERCENT, amount=Decimal('10'))
        self.assertEqual(calculate_discount_amount(code, Decimal('100')), Decimal('10.00'))

    def test_allocate_only_to_eligible_bookings(self):
        allocations = _allocate_discounts(
            [Decimal('100'), Decimal('80')],
            Decimal('10'),
            eligible_mask=[False, True],
        )
        self.assertEqual(allocations, [Decimal('0.00'), Decimal('10.00')])

    def test_basket_rejects_code_for_other_workshops(self):
        code = _code()
        code.workshops.values_list.return_value = [99]
        workshops = {
            10: SimpleNamespace(pk=10, price=Decimal('100.00'), region_id=1, course_id=1),
        }
        items = [{'workshop_id': 10, 'quantity': 1}]
        with self.assertRaises(ValidationError):
            validate_discount_code_for_basket(code, workshops, items)

    @patch('bookings.discount_codes.timezone')
    def test_basket_applies_percent_to_eligible_total(self, mock_timezone):
        mock_timezone.now.return_value.date.return_value = __import__('datetime').date(2026, 7, 1)
        code = _code(discount_type=DiscountCode.DISCOUNT_PERCENT, amount=Decimal('10'))
        code.workshops.values_list.return_value = [10]
        workshops = {
            10: SimpleNamespace(pk=10, price=Decimal('100.00'), region_id=1, course_id=1),
            20: SimpleNamespace(pk=20, price=Decimal('50.00'), region_id=1, course_id=1),
        }
        items = [
            {'workshop_id': 10, 'quantity': 1},
            {'workshop_id': 20, 'quantity': 1},
        ]
        discount, allowed = validate_discount_code_for_basket(code, workshops, items)
        self.assertEqual(discount, Decimal('10.00'))
        self.assertEqual(allowed, {10})


class DiscountCodeAdminFormTests(SimpleTestCase):
    def test_code_is_uppercased_by_clean(self):
        form = DiscountCodeAdminForm()
        form.cleaned_data = {'code': ' spring10 '}
        self.assertEqual(form.clean_code(), 'SPRING10')

    def test_percent_over_100_adds_amount_error(self):
        form = DiscountCodeAdminForm()
        form.cleaned_data = {
            'discount_type': DiscountCode.DISCOUNT_PERCENT,
            'amount': Decimal('150'),
            'workshops': None,
        }
        from django.forms.utils import ErrorDict
        form._errors = ErrorDict()
        form.clean()
        self.assertIn('amount', form.errors)
