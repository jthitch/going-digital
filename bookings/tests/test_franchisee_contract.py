from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from bookings.franchisee_contract import (
    franchisee_contract_details,
    franchisee_contract_notice,
    franchisee_contract_notice_from_details,
)
from core.models import User


class FranchiseeContractTests(SimpleTestCase):
    def test_display_address_uses_legacy_when_address1_blank(self):
        user = User(
            firstname='Sam',
            lastname='Franchisee',
            email='sam@example.com',
            address='Old Road\nTown',
            address1='',
            address2='',
            town_city='',
            postcode='',
        )
        self.assertEqual(user.get_display_address(), 'Old Road\nTown')

    def test_display_address_prefers_structured_fields(self):
        user = User(
            firstname='Sam',
            lastname='Franchisee',
            email='sam@example.com',
            address='Legacy ignored',
            address1='12 High Street',
            address2='Flat 2',
            town_city='Bath',
            postcode='BA1 1AA',
        )
        self.assertEqual(
            user.get_display_address(),
            '12 High Street, Flat 2, Bath, BA1 1AA',
        )

    def test_notice_includes_name_and_legacy_address(self):
        user = User(
            pk=7,
            firstname='Sam',
            lastname='Franchisee',
            email='sam@example.com',
            active=1,
            address='1 Legacy Lane, Bath',
            address1='',
        )
        workshop = SimpleNamespace(user_id=7, createdby_id=None)
        with patch(
            'bookings.franchisee_contract.User.objects.filter',
        ) as filter_mock:
            filter_mock.return_value.first.return_value = user
            notice = franchisee_contract_notice(workshop)
        self.assertIn('Sam Franchisee', notice)
        self.assertIn('1 Legacy Lane, Bath', notice)
        self.assertTrue(
            notice.startswith(
                'You have entered into a contract with a Going Digital franchise, '
                'owned and operated under licence by'
            )
        )

    def test_notice_from_details_without_address(self):
        notice = franchisee_contract_notice_from_details({
            'name': 'Sam Franchisee',
            'address': '',
        })
        self.assertEqual(
            notice,
            'You have entered into a contract with a Going Digital franchise, '
            'owned and operated under licence by Sam Franchisee',
        )

    def test_details_none_without_franchisee(self):
        workshop = SimpleNamespace(user_id=None, createdby_id=None)
        self.assertIsNone(franchisee_contract_details(workshop))
        self.assertEqual(franchisee_contract_notice(workshop), '')
