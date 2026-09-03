"""
URL configuration for courses app.
/photography-courses/ (list), /photography-courses/<slug>/ (overview),
/photography-courses/<course-slug>/<location-slug>/ (course at venue).
Redirects: /photography-workshops/ → /photography-courses/ via PhotographyWorkshopsRedirectMiddleware (301).
URL fallbacks below if middleware is disabled.
"""
from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'courses'

urlpatterns = [
    # Homepage
    path('', views.HomePageView.as_view(), name='homepage'),
    
    # Contact page
    path('contact/', views.ContactView.as_view(), name='contact'),

    # Gift vouchers page
    path('gift-vouchers/', views.GiftVoucherView.as_view(), name='gift_vouchers'),

    # HTML site map (users + AEO); XML remains at /sitemap.xml
    path('site-map/', views.SiteMapPageView.as_view(), name='site_map'),

    # FAQ page (frequently-asked-questions matches original site URL for SEO)
    path('frequently-asked-questions/', views.FAQView.as_view(), name='faq'),
    path('faq/', RedirectView.as_view(pattern_name='courses:faq', permanent=True)),

    # Terms and conditions (matches original site URL for SEO)
    path('terms-and-conditions/', views.TermsAndConditionsView.as_view(), name='terms_and_conditions'),

    # Privacy policy (matches original site URL for SEO)
    path('privacy-policy/', views.PrivacyPolicyView.as_view(), name='privacy_policy'),

    # Editing courses page
    path('photography-editing-courses/', views.EditingCoursePageView.as_view(), name='editing_course_page'),
    
    # Course listing and overview (canonical URLs)
    path('photography-courses/', views.CourseListView.as_view(), name='course_list'),
    # Indexable location hubs (must stay before course slug routes)
    path(
        'photography-courses/locations/',
        views.LocationLandingIndexView.as_view(),
        name='location_landing_index',
    ),
    path(
        'photography-courses/regions/',
        RedirectView.as_view(pattern_name='courses:location_landing_index', permanent=True),
    ),
    path(
        'photography-courses/regions/<slug:slug>/',
        views.RegionLandingView.as_view(),
        name='region_landing',
    ),
    path(
        'photography-courses/in/',
        RedirectView.as_view(pattern_name='courses:location_landing_index', permanent=True),
    ),
    path(
        'photography-courses/in/<slug:slug>/',
        views.CityLandingView.as_view(),
        name='city_landing',
    ),
    # Venue pages: /venues (list), /photography-courses/venues/<location_slug>/ (detail)
    path('venues/', views.VenueListView.as_view(), name='venue_list'),
    path('photography-courses/venues/<slug:location_slug>/', views.VenueDetailView.as_view(), name='venue_detail'),
    # Course at venue (two segments: must be before single-slug route)
    path('photography-courses/<slug:slug>/<slug:location_slug>/', views.CourseDetailView.as_view(), name='course_detail_by_location'),
    path('photography-courses/<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail'),
    # Legacy redirects
    path('courses/', RedirectView.as_view(pattern_name='courses:course_list', permanent=True)),
    path('courses/<slug:slug>/', RedirectView.as_view(pattern_name='courses:course_detail', permanent=True)),
    # Legacy redirect: old venue URL format to new
    path('photography-courses/<str:location>/<slug:location_slug>/<slug:slug>/', views.redirect_old_course_location_url),
    
    # 301 fallbacks for old /photography-workshops/ URLs (primary handler: middleware)
    path('photography-workshops/<slug:slug>/<slug:location_slug>/', views.redirect_photography_workshops_course_at_venue),
    path('photography-workshops/<slug:slug>/', views.redirect_photography_workshops_slug),
    
    # API endpoints for React components
    path('api/search/', views.CourseSearchAPIView.as_view(), name='course_search_api'),
]
