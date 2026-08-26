from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import Http404, HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from courses.admin_training import (
    GUIDE_CATALOG,
    get_guide,
    guides_for_context,
    render_guide_html,
    training_url_context,
)
from courses.admin_training_views import TrainingGuideView, TrainingIndexView


class TrainingCatalogTests(SimpleTestCase):
    def test_catalog_has_expected_guides(self):
        slugs = {g.slug for g in GUIDE_CATALOG}
        self.assertEqual(
            slugs,
            {
                'create-venue',
                'create-course',
                'create-workshop',
                'venue-approval',
                'discount-codes',
                'workshop-feedback',
            },
        )

    def test_get_guide(self):
        self.assertIsNone(get_guide('missing'))
        guide = get_guide('create-venue')
        self.assertEqual(guide.title, 'Create a venue')
        self.assertIn('venue', guide.contexts)

    def test_guides_for_context(self):
        venue_guides = guides_for_context('venue')
        self.assertEqual(
            [g.slug for g in venue_guides],
            ['create-venue', 'venue-approval'],
        )
        self.assertEqual(
            [g.slug for g in guides_for_context('workshop')],
            ['create-workshop', 'discount-codes'],
        )
        self.assertEqual(
            [g.slug for g in guides_for_context('discount_code')],
            ['discount-codes'],
        )
        self.assertEqual(
            [g.slug for g in guides_for_context('workshop_feedback')],
            ['workshop-feedback'],
        )


class TrainingRenderTests(SimpleTestCase):
    def test_render_includes_deep_links(self):
        guide = get_guide('create-venue')
        html = render_guide_html(guide)
        self.assertIn('Add venue', html)
        self.assertIn('/admin/courses/venue/add/', html)
        self.assertIn('/admin/training/', html)

    def test_url_context_includes_per_guide_keys(self):
        urls = training_url_context()
        self.assertEqual(urls['guide_create_workshop'], '/admin/training/create-workshop/')
        self.assertEqual(urls['training_index'], '/admin/training/')


class TrainingViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self._each_context = patch(
            'django.contrib.admin.sites.AdminSite.each_context',
            return_value={
                'site_header': 'Going Digital',
                'site_title': 'Going Digital Admin',
                'site_url': '/',
                'has_permission': True,
                'available_apps': [],
                'is_popup': False,
                'is_nav_sidebar_enabled': True,
            },
        )
        self._each_context.start()
        self.addCleanup(self._each_context.stop)

    def _staff_user(self):
        return SimpleNamespace(
            is_active=True,
            is_staff=True,
            is_superuser=True,
            is_authenticated=True,
            pk=1,
            id=1,
            username='trainer',
        )

    def test_index_requires_staff(self):
        request = self.factory.get('/admin/training/')
        request.user = AnonymousUser()
        response = TrainingIndexView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    @patch('courses.admin_training_views.render')
    def test_index_ok_for_staff(self, mock_render):
        mock_render.return_value = HttpResponse('ok')
        request = self.factory.get('/admin/training/')
        request.user = self._staff_user()
        response = TrainingIndexView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()
        _req, template_name, context = mock_render.call_args.args
        self.assertEqual(template_name, 'admin/training/index.html')
        self.assertEqual(len(context['guides']), len(GUIDE_CATALOG))
        self.assertEqual(context['title'], 'Training guides')

    @patch('courses.admin_training_views.render')
    def test_guide_ok_for_staff(self, mock_render):
        mock_render.return_value = HttpResponse('ok')
        request = self.factory.get('/admin/training/create-course/')
        request.user = self._staff_user()
        response = TrainingGuideView.as_view()(request, slug='create-course')
        self.assertEqual(response.status_code, 200)
        _req, template_name, context = mock_render.call_args.args
        self.assertEqual(template_name, 'admin/training/guide.html')
        self.assertEqual(context['guide'].slug, 'create-course')
        self.assertIn('Create a course', context['guide_html'])

    def test_unknown_guide_404(self):
        request = self.factory.get('/admin/training/nope/')
        request.user = self._staff_user()
        with self.assertRaises(Http404):
            TrainingGuideView.as_view()(request, slug='nope')

    def test_admin_urls_resolve(self):
        self.assertEqual(reverse('admin:admin_training_index'), '/admin/training/')
        self.assertEqual(
            reverse('admin:admin_training_guide', kwargs={'slug': 'create-venue'}),
            '/admin/training/create-venue/',
        )
