"""
Sitemaps for courses app - XML sitemap for search engines.
"""
from django.db.models import Q
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

from .models import Course, Venue
from .workshop_querysets import bookable_workshop_ordering, bookable_workshops_queryset


class StaticViewSitemap(Sitemap):
    """Static pages that don't correspond to model instances."""
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return [
            'courses:homepage',
            'courses:course_list',
            'courses:venue_list',
            'courses:contact',
            'courses:gift_vouchers',
            'courses:faq',
            'courses:terms_and_conditions',
            'courses:privacy_policy',
            'courses:editing_course_page',
            'courses:site_map',
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return timezone.now()


class CourseOverviewSitemap(Sitemap):
    """Course overview pages: /photography-courses/<slug>/"""
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Course.objects.filter(active=True)

    def location(self, obj):
        return reverse('courses:course_detail', kwargs={'slug': obj.slug})

    def lastmod(self, obj):
        return obj.updated_at


class WorkshopSitemap(Sitemap):
    """Workshop pages: /photography-courses/<course_slug>/<location_slug>/"""
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return bookable_workshops_queryset().filter(
            venue__active=1,
        ).select_related('course', 'venue').order_by(*bookable_workshop_ordering())

    def location(self, obj):
        return obj.get_absolute_url()

    def lastmod(self, obj):
        return obj.updated_at


class VenueSitemap(Sitemap):
    """Venue pages: /photography-courses/venues/<location_slug>/ - all active venues with slug"""
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Venue.objects.filter(
            active=1,
        ).exclude(
            Q(slug='') | Q(slug__isnull=True),
        ).order_by('slug')

    def location(self, obj):
        return reverse('courses:venue_detail', kwargs={'location_slug': obj.slug})

    def lastmod(self, obj):
        return obj.updated_at
