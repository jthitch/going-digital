"""
URL configuration for courses app.
SEO-friendly URL structure: /photography-courses/<location>/<location-slug>/<postcode>/<course-slug>/
"""
from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Homepage
    path('', views.HomePageView.as_view(), name='homepage'),
    
    # Editing courses page
    path('photography-editing-courses/', views.EditingCoursePageView.as_view(), name='editing_course_page'),
    
    # Course listing
    path('courses/', views.CourseListView.as_view(), name='course_list'),
    
    # Convenience route: /courses/<slug>/ redirects to /photography-courses/<slug>/
    path('courses/<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail_short'),
    
    # SEO-friendly course detail by location, location slug, and postcode
    path('photography-courses/<str:location>/<slug:location_slug>/<str:postcode>/<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail_by_location'),
    
    # Fallback course detail (without location/postcode)
    path('photography-courses/<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail'),
    
    # API endpoints for React components
    path('api/search/', views.CourseSearchAPIView.as_view(), name='course_search_api'),
]
