"""
URL configuration for photocourses project.
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include, reverse_lazy
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage

from courses.sitemaps import StaticViewSitemap, CourseOverviewSitemap, WorkshopSitemap, VenueSitemap
from courses.views import RobotsTxtView, LlmsTxtView
from core.forms import GdUserPasswordResetForm
from core.views_newsletter import NewsletterSubscribeView
from website.views import DevSiteAccessView

# Customize admin site
admin.site.site_header = "Going Digital Administration"
admin.site.site_title = "Going Digital Admin"
admin.site.index_title = "Welcome to Going Digital Administration"

sitemaps = {
    'static': StaticViewSitemap,
    'courses': CourseOverviewSitemap,
    'instances': WorkshopSitemap,
    'venues': VenueSitemap,
}

urlpatterns = [
    path('dev-access/', DevSiteAccessView.as_view(), name='dev_site_access'),
    path(
        'admin/password_reset/',
        auth_views.PasswordResetView.as_view(
            form_class=GdUserPasswordResetForm,
            success_url=reverse_lazy('admin_password_reset_done'),
        ),
        name='admin_password_reset',
    ),
    path(
        'admin/password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(),
        name='admin_password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(success_url=reverse_lazy('password_reset_complete')),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(extra_context={'login_url': '/admin/'}),
        name='password_reset_complete',
    ),
    path('admin/', admin.site.urls),
    path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('img/favicon/favicon.png'), permanent=True)),
    path('robots.txt', RobotsTxtView.as_view(), name='robots_txt'),
    path('llms.txt', LlmsTxtView.as_view(), name='llms_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('', include('courses.urls')),
    path('account/', include('core.urls')),
    path('newsletter/subscribe/', NewsletterSubscribeView.as_view(), name='newsletter_subscribe'),
    path('bookings/', include('bookings.urls')),
    path('payments/', include('payments.urls')),
]

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
