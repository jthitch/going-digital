from django.test import SimpleTestCase, override_settings
from django.test.client import RequestFactory

from website.middleware import (
    PhotographyWorkshopsRedirectMiddleware,
    _canonical_photography_courses_path,
)


class PhotographyWorkshopsPathMappingTests(SimpleTestCase):
    def test_list_with_trailing_slash(self):
        self.assertEqual(
            _canonical_photography_courses_path('/photography-workshops/'),
            '/photography-courses/',
        )

    def test_list_without_trailing_slash(self):
        self.assertEqual(
            _canonical_photography_courses_path('/photography-workshops'),
            '/photography-courses/',
        )

    def test_course_overview(self):
        self.assertEqual(
            _canonical_photography_courses_path('/photography-workshops/macro-close-up-courses/'),
            '/photography-courses/macro-close-up-courses/',
        )

    def test_course_overview_without_trailing_slash(self):
        self.assertEqual(
            _canonical_photography_courses_path('/photography-workshops/macro-close-up-courses'),
            '/photography-courses/macro-close-up-courses/',
        )

    def test_course_at_venue(self):
        self.assertEqual(
            _canonical_photography_courses_path('/photography-workshops/get-off-auto/cardiff-docks/'),
            '/photography-courses/get-off-auto/cardiff-docks/',
        )

    def test_unrelated_path_unchanged(self):
        self.assertIsNone(_canonical_photography_courses_path('/photography-courses/foo/'))


@override_settings(
    MIDDLEWARE=[
        'website.middleware.PhotographyWorkshopsRedirectMiddleware',
    ],
)
class PhotographyWorkshopsRedirectMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = PhotographyWorkshopsRedirectMiddleware(lambda request: None)

    def test_permanent_redirect_preserves_query_string(self):
        request = self.factory.get(
            '/photography-workshops/macro-close-up-courses?ref=email',
        )
        response = self.middleware.process_request(request)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response['Location'],
            '/photography-courses/macro-close-up-courses/?ref=email',
        )
