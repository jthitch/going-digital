from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.forms_student import BookingCameraForm


def _booking(**kwargs):
    defaults = {
        'student_first_name': 'Alex',
        'student_last_name': 'Smith',
        'camera_make': '',
        'camera_model': '',
        'loan_camera': False,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _valid_names():
    return {'student_first_name': 'Alex', 'student_last_name': 'Smith'}


def _other_camera():
    return {
        'camera_make_choice': '__other__',
        'camera_make_other': 'Canon',
        'camera_model_choice': '__other__',
        'camera_model_other': 'R6',
    }


class BookingCameraFormTests(SimpleTestCase):
    @patch('bookings.camera_catalog.make_select_choices', return_value=[
        ('', 'Select make'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.model_select_choices', return_value=[
        ('', 'Select model'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.selection_from_stored', return_value={
        'make_choice': '',
        'make_other': '',
        'model_choice': '',
        'model_other': '',
    })
    def test_requires_camera_when_not_loan(self, *_mocks):
        form = BookingCameraForm(_booking(), _valid_names())
        self.assertFalse(form.is_valid())
        self.assertTrue(form.errors)

    @patch('bookings.camera_catalog.make_select_choices', return_value=[
        ('', 'Select make'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.model_select_choices', return_value=[
        ('', 'Select model'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.selection_from_stored', return_value={
        'make_choice': '',
        'make_other': '',
        'model_choice': '',
        'model_other': '',
    })
    def test_optional_camera_for_loan_booking(self, *_mocks):
        form = BookingCameraForm(
            _booking(loan_camera=True),
            _valid_names(),
        )
        self.assertTrue(form.is_valid())

    @patch('bookings.camera_catalog.make_select_choices', return_value=[
        ('', 'Select make'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.model_select_choices', return_value=[
        ('', 'Select model'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.selection_from_stored', return_value={
        'make_choice': '',
        'make_other': '',
        'model_choice': '',
        'model_other': '',
    })
    def test_accepts_other_camera_values(self, *_mocks):
        form = BookingCameraForm(
            _booking(),
            {
                **_valid_names(),
                **_other_camera(),
            },
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['camera_make'], 'Canon')
        self.assertEqual(form.cleaned_data['camera_model'], 'R6')

    @patch('bookings.camera_catalog.make_select_choices', return_value=[
        ('', 'Select make'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.model_select_choices', return_value=[
        ('', 'Select model'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.selection_from_stored', return_value={
        'make_choice': '',
        'make_other': '',
        'model_choice': '',
        'model_other': '',
    })
    def test_accepts_unknown(self, *_mocks):
        form = BookingCameraForm(
            _booking(),
            {
                **_valid_names(),
                'camera_make_choice': '__unknown__',
                'camera_model_choice': '__unknown__',
            },
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['camera_make'], 'Unknown')
        self.assertEqual(form.cleaned_data['camera_model'], 'Unknown')

    @patch('bookings.camera_catalog.make_select_choices', return_value=[
        ('', 'Select make'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.model_select_choices', return_value=[
        ('', 'Select model'),
        ('__unknown__', 'Unknown'),
        ('__other__', 'Other'),
    ])
    @patch('bookings.camera_catalog.selection_from_stored', return_value={
        'make_choice': '',
        'make_other': '',
        'model_choice': '',
        'model_other': '',
    })
    def test_requires_student_name(self, *_mocks):
        form = BookingCameraForm(
            _booking(),
            {
                'student_first_name': '',
                'student_last_name': '',
                **_other_camera(),
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn('student_first_name', form.errors)
        self.assertIn('student_last_name', form.errors)
