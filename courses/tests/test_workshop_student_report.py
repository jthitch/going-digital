from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from courses.workshop_student_report import (
    CSV_HEADERS,
    WorkshopStudentRow,
    iter_workshop_student_report_rows,
    workshop_student_report_filename,
)


class WorkshopStudentReportTests(SimpleTestCase):
    def test_csv_rows_include_course_date_and_student_details(self):
        course = SimpleNamespace(course_name='Beginner DSLR', title='Beginner DSLR')
        venue = SimpleNamespace(venue_name='Bath Studio', name='Bath Studio')
        workshop = SimpleNamespace(
            pk=42,
            course_id=1,
            course=course,
            venue_id=2,
            venue=venue,
            is_open_dated=False,
            start_date=datetime(2026, 7, 20, 10, 0),
            date=datetime(2026, 7, 20, 10, 0),
        )
        student = WorkshopStudentRow(
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            phone='01225 000000',
            address1='12 High Street',
            address2='Flat 2',
            town_city='Bath',
            postcode='BA1 1AA',
            special_requirements='Vegetarian lunch',
            loan_camera=True,
            booking_reference='ABC12345',
            status='Confirmed',
        )

        rows = list(iter_workshop_student_report_rows(workshop, [student]))
        self.assertEqual(rows[0], CSV_HEADERS)
        self.assertEqual(
            rows[1],
            [
                'Beginner DSLR',
                '20 July 2026',
                '10:00',
                'Bath Studio',
                'Ada',
                'Lovelace',
                'ada@example.com',
                '01225 000000',
                '12 High Street',
                'Flat 2',
                'Bath',
                'BA1 1AA',
                'Vegetarian lunch',
                'Yes',
                'ABC12345',
                'Confirmed',
            ],
        )

    def test_filename_uses_course_and_date(self):
        workshop = SimpleNamespace(
            pk=7,
            course_id=1,
            course=SimpleNamespace(course_name='Portrait Lighting', title='Portrait Lighting'),
            is_open_dated=False,
            start_date=datetime(2026, 8, 1, 9, 30),
            date=datetime(2026, 8, 1, 9, 30),
        )
        self.assertEqual(
            workshop_student_report_filename(workshop),
            'students-portrait-lighting-2026-08-01-w7.csv',
        )

    def test_new_booking_objects_still_serialise(self):
        workshop = SimpleNamespace(
            pk=1,
            course_id=1,
            course=SimpleNamespace(course_name='Course', title='Course'),
            venue_id=None,
            venue=None,
            is_open_dated=True,
            start_date=None,
            date=None,
        )
        customer = SimpleNamespace(
            address1='',
            address='',
            address2='',
            town_city='',
            postcode='',
            contact_number='',
        )
        booking = SimpleNamespace(
            student_first_name='Sam',
            student_last_name='Smith',
            student_email='sam@example.com',
            student_phone='07000',
            special_requirements='',
            loan_camera=False,
            booking_reference='NEW1',
            status='confirmed',
            customer=customer,
            get_status_display=MagicMock(return_value='Confirmed'),
        )
        rows = list(iter_workshop_student_report_rows(workshop, [booking]))
        self.assertEqual(rows[1][4:7], ['Sam', 'Smith', 'sam@example.com'])
