from django.http import HttpResponse
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.client import RequestFactory
from django.urls import reverse

from website.middleware import AdminNoIndexMiddleware


class AdminNoIndexMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AdminNoIndexMiddleware(lambda request: HttpResponse('ok'))

    def test_sets_header_on_admin_index(self):
        request = self.factory.get('/admin/')
        response = self.middleware(request)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')

    def test_sets_header_on_admin_login(self):
        request = self.factory.get('/admin/login/')
        response = self.middleware(request)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')

    def test_does_not_set_header_on_public_pages(self):
        request = self.factory.get('/photography-courses/')
        response = self.middleware(request)
        self.assertNotIn('X-Robots-Tag', response)


@override_settings(ROOT_URLCONF='photocourses.urls')
class RobotsTxtAdminDisallowTests(TestCase):
    def test_disallows_admin(self):
        response = self.client.get(reverse('robots_txt'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('Disallow: /admin', body)
