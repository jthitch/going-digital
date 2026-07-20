from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from bookings.attendee_details import (
    AttendeePlaceForm,
    build_attendee_place_forms,
    bookings_need_attendee_details,
    group_bookings_for_attendee_form,
    next_post_booking_step_url,
    validate_attendee_details_post,
)


def _booking(**kwargs):
    defaults = {
        'id': 1,
        'workshop_id': 10,
        'status': 'confirmed',
        'student_first_name': 'Alex',
        'student_last_name': 'Smith',
        'loan_camera': False,
        'camera_make': '',
        'camera_model': '',
        'attendee_details_collected_at': None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class AttendeeDetailsTests(SimpleTestCase):
    def test_bookings_need_details_when_not_collected(self):
        bookings = [_booking(id=1), _booking(id=2, attendee_details_collected_at=None)]
        self.assertTrue(bookings_need_attendee_details(bookings))

    def test_bookings_skip_details_when_all_collected(self):
        from django.utils import timezone

        collected = timezone.now()
        bookings = [_booking(attendee_details_collected_at=collected)]
        self.assertFalse(bookings_need_attendee_details(bookings))

    def test_group_bookings_by_workshop(self):
        bookings = [
            _booking(id=1, workshop_id=10),
            _booking(id=2, workshop_id=10),
            _booking(id=3, workshop_id=20),
        ]
        groups = group_bookings_for_attendee_form(bookings)
        self.assertEqual([len(group) for group in groups], [2, 1])

    def test_multi_place_shows_name_fields_for_place_two(self):
        primary = AttendeePlaceForm(
            booking=_booking(id=1),
            place_number=1,
            place_total=2,
            is_primary=True,
            workshop_title='Test course',
            workshop_date='',
        )
        additional = AttendeePlaceForm(
            booking=_booking(id=2),
            place_number=2,
            place_total=2,
            is_primary=False,
            workshop_title='Test course',
            workshop_date='',
        )
        self.assertFalse(primary.show_name_fields)
        self.assertTrue(additional.show_name_fields)

    def test_validate_requires_camera_for_non_loan_place(self):
        places = [
            AttendeePlaceForm(
                booking=_booking(id=1),
                place_number=1,
                place_total=1,
                is_primary=True,
                workshop_title='Test course',
                workshop_date='',
            ),
        ]
        errors = validate_attendee_details_post({}, places)
        self.assertIn('camera_make_1', errors)
        self.assertIn('camera_model_1', errors)

    def test_validate_accepts_unknown_camera(self):
        places = [
            AttendeePlaceForm(
                booking=_booking(id=1),
                place_number=1,
                place_total=1,
                is_primary=True,
                workshop_title='Test course',
                workshop_date='',
            ),
        ]
        errors = validate_attendee_details_post(
            {
                'camera_make_choice_1': '__unknown__',
                'camera_model_choice_1': '__unknown__',
            },
            places,
        )
        self.assertEqual(errors, {})

    def test_validate_requires_names_for_additional_places(self):
        places = [
            AttendeePlaceForm(
                booking=_booking(id=1),
                place_number=1,
                place_total=2,
                is_primary=True,
                workshop_title='Test course',
                workshop_date='',
            ),
            AttendeePlaceForm(
                booking=_booking(id=2),
                place_number=2,
                place_total=2,
                is_primary=False,
                workshop_title='Test course',
                workshop_date='',
            ),
        ]
        errors = validate_attendee_details_post(
            {
                'camera_make_choice_1': '__unknown__',
                'camera_model_choice_1': '__unknown__',
                'camera_make_choice_2': '__other__',
                'camera_make_other_2': 'Nikon',
                'camera_model_choice_2': '__other__',
                'camera_model_other_2': 'D850',
            },
            places,
        )
        self.assertIn('student_first_name_2', errors)
        self.assertIn('student_last_name_2', errors)

    def test_next_step_prefers_attendee_details(self):
        bookings = [_booking()]
        with patch('bookings.attendee_details.reverse', return_value='/details'):
            url = next_post_booking_step_url(bookings)
        self.assertEqual(url, '/details')
