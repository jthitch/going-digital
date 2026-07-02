"""
Course views - server-rendered for SEO.
"""
import json
import random
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from core.mail import send_filtered_mail
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.views.generic import ListView, DetailView, TemplateView, FormView
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils.dateparse import parse_date
from datetime import datetime, time
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Course, Workshop, Venue, CourseCategory, LEVEL_NAME_TO_ID, LEVEL_DISPLAY_NAMES
from .forms import ContactForm, GiftVoucherRequestForm, CONTACT_REGION_CHOICES, VOUCHER_AMOUNT_CHOICES
from .utils import get_promoted_occasions, workshop_calendar_date
from .workshop_querysets import (
    OPEN_DATED_LABEL,
    apply_workshop_list_date_range,
    bookable_workshop_ordering,
    bookable_workshop_visibility_q,
    bookable_workshops_queryset,
    workshop_is_open_dated,
)
from website.models import GiftVoucherPageImage, HeroImage, BeforeAfterImage, FAQ
from .serializers import WorkshopSerializer
from .display_images import attach_gd_images_to_workshops, collect_header_images, primary_image_url
from .list_card import list_card_workshops, serialize_list_card

# Fallback when no admin image: optional legacy file in MEDIA_ROOT, then bundled static SVG.
_GIFT_VOUCHER_LEGACY_MEDIA_REL = 'gd_images/im-t8-f1-0a11ba8c74817bc2c7008aa89413e39b.jpg'
_GIFT_VOUCHER_DEFAULT_STATIC = 'img/gift-vouchers/hero-default.svg'


def parse_course_list_date_range(request):
    """Return (date_from, date_to, dt_from, dt_to) for course list date filters."""
    raw_from = (request.GET.get('date_from') or '').strip()
    raw_to = (request.GET.get('date_to') or '').strip()
    date_from = parse_date(raw_from) if raw_from else None
    date_to = parse_date(raw_to) if raw_to else None
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from
    tz = timezone.get_current_timezone()
    dt_from = (
        timezone.make_aware(datetime.combine(date_from, time.min), tz)
        if date_from else None
    )
    dt_to = (
        timezone.make_aware(datetime.combine(date_to, time.max), tz)
        if date_to else None
    )
    return date_from, date_to, dt_from, dt_to


def format_date_range_label(date_from, date_to):
    fmt = '%d %b %Y'
    if date_from and date_to:
        if date_from == date_to:
            return date_from.strftime(fmt)
        return f"{date_from.strftime(fmt)} – {date_to.strftime(fmt)}"
    if date_from:
        return f"From {date_from.strftime(fmt)}"
    if date_to:
        return f"Until {date_to.strftime(fmt)}"
    return ''


def parse_venue_filter(raw):
    """
    Parse ?city= into a venue id, list of ids (duplicate slugs), None, or -1 (no match).
    Prefer numeric venue ids in URLs; slugs are supported for legacy links.
    """
    raw = (raw or '').strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    ids = list(Venue.objects.filter(slug=raw).values_list('id', flat=True))
    if not ids:
        return -1
    if len(ids) == 1:
        return ids[0]
    return ids


def apply_venue_filter_to_workshop_qs(queryset, raw_filter):
    """Restrict workshops to a single venue (or matching slug ids)."""
    parsed = parse_venue_filter(raw_filter)
    if parsed is None:
        return queryset
    if parsed == -1:
        return queryset.none()
    if isinstance(parsed, list):
        return queryset.filter(venue_id__in=parsed)
    return queryset.filter(venue_id=parsed)


def filter_instances_by_location(instances, raw_filter):
    """Filter workshop instances to a venue id or slug (?location= / path segment)."""
    parsed = parse_venue_filter(raw_filter)
    if parsed is None:
        return instances
    if parsed == -1:
        return []
    if isinstance(parsed, list):
        id_set = set(parsed)
        return [inst for inst in instances if inst.venue_id in id_set]
    return [inst for inst in instances if inst.venue_id == parsed]


def bookable_workshops_for_request(request, *, apply_location_filter=True):
    """
    Upcoming bookable workshops for the course list.
    All workshop-level filters are applied on one queryset so a course only matches
    when the same workshop satisfies date, venue, and status constraints.
    Open-dated workshops are always included in date-filtered results.
    """
    date_from, date_to, dt_from, dt_to = parse_course_list_date_range(request)
    queryset = bookable_workshops_queryset()
    queryset = apply_workshop_list_date_range(queryset, dt_from, dt_to)
    is_map_view = request.GET.get('view') == 'map'
    if apply_location_filter and not is_map_view:
        queryset = apply_venue_filter_to_workshop_qs(
            queryset, request.GET.get('city', ''),
        )
    return queryset, (date_from, date_to)


def normalize_city_param(raw):
    """Canonical ?city= value for templates (numeric venue id as string)."""
    parsed = parse_venue_filter(raw)
    if parsed is None or parsed == -1:
        return ''
    if isinstance(parsed, list):
        return str(parsed[0])
    return str(parsed)


def filter_venues_for_course_list():
    """Venues that have at least one upcoming bookable or open-dated workshop."""
    venue_ids = (
        bookable_workshops_queryset()
        .exclude(venue_id__isnull=True)
        .values_list('venue_id', flat=True)
        .distinct()
    )
    return (
        Venue.objects.filter(id__in=venue_ids)
        .exclude(venue_name='')
        .order_by('venue_name')
        .values('id', 'slug', 'venue_name')
    )


def venue_label_for_filter(raw_filter, venues):
    """Human-readable venue name for active filter chips."""
    parsed = parse_venue_filter(raw_filter)
    if parsed is None or parsed == -1:
        return ''
    ids = parsed if isinstance(parsed, list) else [parsed]
    id_set = {str(i) for i in ids}
    for venue in venues:
        if str(venue['id']) in id_set:
            return venue['venue_name']
    try:
        venue = Venue.objects.filter(pk=ids[0]).values_list('venue_name', flat=True).first()
        return venue or ''
    except (IndexError, TypeError):
        return ''


def gift_voucher_page_image_url():
    row = GiftVoucherPageImage.objects.first()
    if row and row.image.name:
        return row.image.url
    legacy = Path(settings.MEDIA_ROOT) / _GIFT_VOUCHER_LEGACY_MEDIA_REL
    if legacy.is_file():
        return f'{settings.MEDIA_URL.rstrip("/")}/{_GIFT_VOUCHER_LEGACY_MEDIA_REL}'
    return staticfiles_storage.url(_GIFT_VOUCHER_DEFAULT_STATIC)


class HomePageView(TemplateView):
    """
    Beautiful, modern homepage with hero images and photography journey guide.
    Hero images are managed by platform admins in Django admin.
    """
    template_name = 'courses/homepage.html'
    
    def get_hero_images(self):
        """Get hero images from database (managed by platform admins)."""
        hero_images = HeroImage.objects.filter(is_active=True).order_by('order', 'created_at')
        return [hero.image.url for hero in hero_images if hero.image]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get hero images from database (managed by platform admins)
        context['hero_images'] = self.get_hero_images()

        now = timezone.now()
        workshop_prefetch = Prefetch(
            'workshops',
            queryset=bookable_workshops_queryset().select_related('venue').order_by(*bookable_workshop_ordering()),
        )
        homepage_course_qs = (
            Course.objects.filter(active=True)
            .select_related('image', 'course_category', 'course_skill_level')
            .prefetch_related(workshop_prefetch, 'media')
        )

        def level_courses(level_key):
            pk = LEVEL_NAME_TO_ID.get(level_key)
            return list(homepage_course_qs.filter(course_skill_level_id=pk))

        level_1 = level_courses('beginner')
        level_2 = level_courses('intermediate')
        level_3 = level_courses('advanced')

        context['level_1_courses'] = level_1
        context['level_2_courses'] = level_2
        context['level_3_courses'] = level_3

        context['editing_courses'] = list(
            homepage_course_qs.filter(
                Q(course_name__icontains='editing') | Q(course_name__icontains='edit') |
                Q(course_description__icontains='editing') | Q(description_for_workshop__icontains='editing')
            )
        )
        context['residentials_courses'] = list(
            homepage_course_qs.filter(
                Q(course_name__icontains='residential') | Q(course_name__icontains='residentials') |
                Q(course_description__icontains='residential') | Q(description_for_workshop__icontains='residential')
            )
        )
        context['bespoke_courses'] = list(
            homepage_course_qs.filter(
                Q(course_name__icontains='bespoke') | Q(course_name__icontains='custom') |
                Q(course_description__icontains='bespoke') | Q(description_for_workshop__icontains='bespoke')
            )
        )

        context['beginner_courses'] = level_1[:6]
        context['intermediate_courses'] = level_2[:6]
        context['advanced_courses'] = level_3[:6]

        intro = homepage_course_qs.filter(slug__icontains='get-off-auto').first()
        if not intro:
            intro = homepage_course_qs.filter(course_name__icontains='Get Off Auto').first()
        context['intro_course'] = intro
        
        # Get all categories from database (id, name) for templates
        context['categories'] = [
            (str(cat.id), cat.course_category)
            for cat in CourseCategory.objects.filter(
                active=1, exclude_from_course_list=0
            ).order_by('display_order', 'course_category')
        ]
        
        # Get locations/venues with active workshops
        context['cities'] = list(Venue.objects.filter(
            workshops__active=1,
        ).filter(
            Q(workshops__open_dated=1) | Q(workshops__date__gte=timezone.now())
        ).values_list('location', flat=True).distinct().exclude(location__isnull=True).exclude(location='').order_by('location')[:10])

        # Course stats for marketing copy: courses across the UK, beginner to aspiring professional
        bookable_workshop_exists = Exists(
            bookable_workshops_queryset().filter(course_id=OuterRef('pk'))
        )
        courses_with_instances = Course.objects.filter(
            active=True,
        ).filter(bookable_workshop_exists).distinct()
        context['course_count'] = courses_with_instances.count() or Course.objects.filter(active=True).count()
        context['location_count'] = Venue.objects.filter(
            active=1,
            workshops__active=1,
        ).filter(
            Q(workshops__open_dated=1) | Q(workshops__date__gte=timezone.now())
        ).distinct().count()
        
        return context


class EditingCoursePageView(TemplateView):
    """
    Static page for editing courses information.
    """
    template_name = 'courses/editing_course_page.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get editing courses for context if needed
        context['editing_courses'] = Course.objects.filter(
            active=True
        ).filter(
            Q(course_name__icontains='editing') | Q(course_name__icontains='edit') |
            Q(course_description__icontains='editing') | Q(description_for_workshop__icontains='editing')
        ).prefetch_related('workshops')
        
        # Get before/after images for the interactive slider
        context['before_after_images'] = BeforeAfterImage.objects.filter(
            is_active=True
        ).order_by('order', 'created_at')
        
        return context


class CourseListView(ListView):
    """
    List all active courses with search/filter capability.
    Supports server-side filtering for SEO.
    Infinite scroll: ?format=json&page=N returns JSON for that page.
    """
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'
    paginate_by = 24
    
    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if request.GET.get('format') == 'json':
            return self.render_to_json_response()
        context = self.get_context_data()
        return self.render_to_response(context)
    
    def render_to_json_response(self):
        """Return paginated courses as JSON for infinite scroll."""
        paginator = self.get_paginator(self.object_list, self.paginate_by)
        page_num = self.request.GET.get('page', 1)
        try:
            page_num = int(page_num)
        except (ValueError, TypeError):
            page_num = 1
        page = paginator.get_page(page_num)
        
        courses_data = [
            serialize_list_card(course)
            for course in page.object_list
        ]
        
        return JsonResponse({
            'courses': courses_data,
            'has_next': page.has_next(),
            'next_page': page.number + 1 if page.has_next() else None,
        })
    
    def get_queryset(self):
        workshop_qs, _ = bookable_workshops_for_request(self.request)
        prefetch_qs = workshop_qs.select_related('venue', 'course').order_by(*bookable_workshop_ordering())

        queryset = Course.objects.filter(
            active=True,
        ).filter(
            Exists(workshop_qs.filter(course_id=OuterRef('pk')))
        ).distinct().select_related(
            'course_category', 'course_skill_level', 'image',
        ).prefetch_related(
            Prefetch(
                'workshops',
                queryset=prefetch_qs,
                to_attr='list_workshops',
            ),
            'media',
        ).order_by(
            'course_category__display_order',
            'course_skill_level__display_order',
            'display_order',
            'course_name',
        )

        search = self.request.GET.get('q', '')
        if search:
            queryset = queryset.filter(
                Q(course_name__icontains=search) |
                Q(course_description__icontains=search) |
                Q(description_for_workshop__icontains=search)
            )

        category = self.request.GET.get('category', '')
        if category:
            try:
                cat_id = int(category)
                queryset = queryset.filter(course_category_id=cat_id)
            except (ValueError, TypeError):
                pass

        level = self.request.GET.get('level', '')
        if level and level in LEVEL_NAME_TO_ID:
            queryset = queryset.filter(course_skill_level_id=LEVEL_NAME_TO_ID[level])

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = [
            (str(cat.id), cat.course_category)
            for cat in CourseCategory.objects.filter(
                active=1, exclude_from_course_list=0
            ).order_by('display_order', 'course_category')
        ]
        context['levels'] = [(k, LEVEL_DISPLAY_NAMES.get(v, k.title())) for k, v in LEVEL_NAME_TO_ID.items()]
        # Course stats for copy
        context['total_course_count'] = Course.objects.filter(
            active=True,
        ).filter(
            Exists(bookable_workshops_queryset().filter(course_id=OuterRef('pk')))
        ).distinct().count()
        context['filter_venues'] = filter_venues_for_course_list()
        
        # Prepare instance data for map (convert to JSON-safe format)
        # Show all bookable instances, not just one per course
        import json
        from datetime import datetime
        instances_data = []
        
        all_map_workshops = []
        for course in context['courses']:
            all_map_workshops.extend(list_card_workshops(course))
        attach_gd_images_to_workshops(all_map_workshops)

        # Get all bookable instances from the filtered courses
        for course in context['courses']:
            for instance in list_card_workshops(course):
                is_bookable = (
                    instance.enrollment_open
                    and instance.venue
                    and instance.venue.latitude
                    and instance.venue.longitude
                    and (
                        workshop_is_open_dated(instance)
                        or (instance.start_date and instance.start_date >= timezone.now())
                    )
                )
                if not is_bookable:
                    continue

                if workshop_is_open_dated(instance):
                    date_display = OPEN_DATED_LABEL
                    start_date_str = OPEN_DATED_LABEL
                else:
                    start_date_str = instance.start_date.strftime('%d %B %Y')
                    if instance.start_date.date() == instance.end_date.date():
                        date_display = start_date_str
                    else:
                        end_date_str = instance.end_date.strftime('%d %B %Y')
                        date_display = f"{start_date_str} - {end_date_str}"

                instance_url = instance.get_absolute_url()
                instance_price = instance.price
                v = instance.venue
                image_url = primary_image_url(workshop=instance, course=course)
                card_desc = course.get_card_short_description() or ''
                if card_desc:
                    words = card_desc.split()
                    if len(words) > 20:
                        card_desc = ' '.join(words[:20]) + '…'
                byline_text = strip_tags(instance.byline or '').strip()
                instances_data.append({
                        'instance_id': instance.id,
                        'course_title': course.title,
                        'byline': byline_text,
                        'course_slug': course.slug,
                        'course_level': course.level,
                        'level_display': course.get_level_display(),
                        'category': course.get_card_category_display(),
                        'short_description': card_desc,
                        'duration_hours': course.duration_hours,
                        'image_url': image_url,
                        'course_url': instance_url,
                        'location_name': v.name if v else 'TBC',
                        'city': v.city if v else '',
                        'address': v.venue_address if v else '',
                        'latitude': float(v.latitude) if v and v.latitude else 0,
                        'longitude': float(v.longitude) if v and v.longitude else 0,
                        'postcode': '',
                        'start_date': start_date_str,
                        'date_display': date_display,
                        'open_dated': workshop_is_open_dated(instance),
                        'price': float(instance_price),
                        'spaces_available': instance.spaces_available,
                        'instructor_name': None,
                        'enrollment_open': instance.enrollment_open,
                        'is_full': instance.is_full,
                    })
        
        context['instances_data'] = json.dumps(instances_data)
        context['map_workshop_count'] = len(instances_data)
        
        # Current filters
        context['current_category'] = self.request.GET.get('category', '')
        context['current_level'] = self.request.GET.get('level', '')
        context['current_city'] = normalize_city_param(self.request.GET.get('city', ''))
        context['current_search'] = self.request.GET.get('q', '')
        context['current_instructor'] = self.request.GET.get('instructor', '')
        date_from, date_to, _, _ = parse_course_list_date_range(self.request)
        context['current_date_from'] = date_from.isoformat() if date_from else ''
        context['current_date_to'] = date_to.isoformat() if date_to else ''
        context['date_range_display'] = format_date_range_label(date_from, date_to)
        context['map_view_active'] = self.request.GET.get('view') == 'map'
        is_map_view = context['map_view_active']
        
        # Query string for category buttons (preserves other filters, excludes category & page)
        from urllib.parse import urlencode

        def _filter_params(exclude=(), force_map=False):
            skip = set(exclude) | {'page'}
            params = {k: v for k, v in self.request.GET.items() if k not in skip and v}
            if force_map:
                params['view'] = 'map'
                params.pop('city', None)
            return params

        def _filter_url(exclude=(), force_map=False):
            params = _filter_params(exclude, force_map)
            base = reverse('courses:course_list')
            qs = urlencode(params)
            return f'{base}?{qs}' if qs else base

        filter_other_params = _filter_params(exclude=('category',), force_map=is_map_view)
        context['filter_other_params_query'] = urlencode(filter_other_params) if filter_other_params else ''
        filter_other_params_no_level = _filter_params(exclude=('level',), force_map=is_map_view)
        context['filter_other_params_for_level_query'] = (
            urlencode(filter_other_params_no_level) if filter_other_params_no_level else ''
        )
        context['clear_filters_url'] = _filter_url(
            exclude=('category', 'level', 'city', 'q', 'instructor', 'date_from', 'date_to'),
            force_map=is_map_view,
        )

        category_labels = dict(context['categories'])
        level_labels = dict(context['levels'])
        filter_venues = list(context['filter_venues'])
        active_filter_chips = []
        if context['current_search']:
            active_filter_chips.append({
                'type': 'Search',
                'label': context['current_search'],
                'url': _filter_url(exclude=('q',), force_map=is_map_view),
            })
        if context['current_city'] and not is_map_view:
            location_label = venue_label_for_filter(context['current_city'], filter_venues)
            if location_label:
                active_filter_chips.append({
                    'type': 'Location',
                    'label': location_label,
                    'url': _filter_url(exclude=('city',), force_map=is_map_view),
                })
        if context['current_category']:
            active_filter_chips.append({
                'type': 'Category',
                'label': category_labels.get(context['current_category'], context['current_category']),
                'url': _filter_url(exclude=('category',), force_map=is_map_view),
            })
        if context['current_level']:
            active_filter_chips.append({
                'type': 'Level',
                'label': level_labels.get(context['current_level'], context['current_level']),
                'url': _filter_url(exclude=('level',), force_map=is_map_view),
            })
        if date_from or date_to:
            active_filter_chips.append({
                'type': 'Dates',
                'label': format_date_range_label(date_from, date_to),
                'url': _filter_url(exclude=('date_from', 'date_to'), force_map=is_map_view),
            })
        if context['current_instructor']:
            active_filter_chips.append({
                'type': 'Instructor',
                'label': context['current_instructor'],
                'url': _filter_url(exclude=('instructor',), force_map=is_map_view),
            })
        context['active_filter_chips'] = active_filter_chips
        context['active_filter_count'] = len(active_filter_chips)

        paginator = context.get('paginator')
        context['filter_results_count'] = paginator.count if paginator else len(context.get('courses', []))
        
        # Base URL for infinite scroll (preserve filters, JS adds format=json&page=N)
        params = {k: v for k, v in self.request.GET.items() if k != 'page'}
        base = reverse('courses:course_list')
        context['infinite_scroll_url'] = (base + '?' + urlencode(params)) if params else base
        
        return context


def redirect_old_course_location_url(request, location, location_slug, slug):
    """Redirect old URL format /photography-courses/<location>/<location_slug>/<slug>/ to new format."""
    new_url = reverse('courses:course_detail_by_location', kwargs={'slug': slug, 'location_slug': location_slug})
    return HttpResponsePermanentRedirect(new_url)


def redirect_photography_workshops_slug(request, slug):
    """301 redirect /photography-workshops/<slug>/ to /photography-courses/<slug>/."""
    new_url = reverse('courses:course_detail', kwargs={'slug': slug})
    return HttpResponsePermanentRedirect(new_url)


class VenueListView(ListView):
    """
    Venue list page: /venues/
    Shows all active venues with a slug.
    """
    model = Venue
    context_object_name = 'venues'
    template_name = 'courses/venue_list.html'

    def get_queryset(self):
        return Venue.objects.filter(
            active=1,
        ).exclude(
            Q(slug='') | Q(slug__isnull=True),
        ).prefetch_related('media').order_by('venue_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # One evaluation for both count and template (no separate COUNT query).
        venues = list(context['venues'])
        context['venues'] = venues
        context['venue_count'] = len(venues)
        return context


class VenueDetailView(DetailView):
    """
    Venue page: /photography-courses/venues/<location_slug>/
    Shows venue info and upcoming workshops at this venue.
    """
    model = Venue
    context_object_name = 'venue'
    template_name = 'courses/venue_detail.html'
    slug_url_kwarg = 'location_slug'

    def get_object(self, queryset=None):
        location_slug = self.kwargs.get('location_slug')
        venue = Venue.objects.filter(
            slug=location_slug,
            active=1,
        ).exclude(slug='').prefetch_related('media').first()
        if venue is None:
            from django.http import Http404
            raise Http404('No active venue found for this slug.')
        return venue

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        venue = self.object
        gd_content = venue.get_content()
        context['venue_content'] = gd_content
        context['venue_images'] = list(venue.media.all())
        instances = bookable_workshops_queryset().filter(
            venue=venue,
        ).select_related('course', 'venue').order_by(*bookable_workshop_ordering())
        context['instances'] = instances
        if gd_content and gd_content.meta_description:
            context['meta_description'] = gd_content.meta_description[:160]
        else:
            context['meta_description'] = (
                f"Photography courses at {venue.venue_name}, {venue.location or ''}. "
                f"View dates and book {venue.venue_name} workshops."
            )
        context['meta_title'] = (
            (gd_content.meta_title or '').strip() if gd_content else ''
        ) or f"{venue.venue_name} - Photography Courses Venue"
        return context


class CourseDetailView(DetailView):
    """
    Course detail page - server-rendered with JSON-LD structured data.
    SEO-critical: must render full HTML on server.
    """
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        """Get course with related data for optimal performance."""
        return Course.objects.prefetch_related(
            Prefetch('workshops', queryset=Workshop.objects.select_related(
                'venue', 'course',
            ).prefetch_related('gallery_images__image').filter(
                bookable_workshop_visibility_q(),
            ).order_by(*bookable_workshop_ordering())),
            'faqs',
            'media',
        ).select_related('image', 'content')
    
    def get_object(self, queryset=None):
        """Get course by slug, optionally filtered by location_slug (venue-specific page)."""
        slug = self.kwargs.get('slug')
        location_slug = self.kwargs.get('location_slug', '')
        location_query = self.request.GET.get('location', '').strip()

        if queryset is None:
            queryset = self.get_queryset()

        course = get_object_or_404(queryset, slug=slug, active=True)

        all_instances = list(course.workshops.all())
        course._all_instances = all_instances

        if location_slug:
            course._filtered_location_slug = location_slug
            course._filtered_instances = filter_instances_by_location(
                all_instances, location_slug,
            )
            course._filtered_location = (
                course._filtered_instances[0].venue.location
                if course._filtered_instances and course._filtered_instances[0].venue
                else None
            )
            course._current_location_filter = ''
        elif location_query:
            course._filtered_location_slug = None
            course._filtered_location = None
            course._filtered_instances = filter_instances_by_location(
                all_instances, location_query,
            )
            course._current_location_filter = normalize_city_param(location_query)
        else:
            course._filtered_location = None
            course._filtered_location_slug = None
            course._filtered_instances = all_instances
            course._current_location_filter = ''

        return course
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        # Convert instances to list if it's a RelatedManager
        if hasattr(course, '_filtered_instances'):
            instances_list = course._filtered_instances
        else:
            instances_list = list(course.workshops.all())

        all_instances = getattr(course, '_all_instances', instances_list)

        context['featured_instance'] = instances_list[0] if instances_list else None

        # Check if this is a location-specific page (URL has location_slug, not venue.location which can be empty)
        context['is_location_specific'] = bool(getattr(course, '_filtered_location_slug', None) and instances_list)

        filter_location_venues = []
        seen_filter_venue_ids = set()
        for instance in all_instances:
            if instance.venue_id and instance.venue_id not in seen_filter_venue_ids:
                seen_filter_venue_ids.add(instance.venue_id)
                if instance.venue:
                    filter_location_venues.append(instance.venue)

        display_locations = []
        seen_display_venue_ids = set()
        prices = []
        filter_dates = []
        instances_by_city = {}
        for instance in instances_list:
            instance.filter_date = '' if workshop_is_open_dated(instance) else workshop_calendar_date(instance.start_date)
            if instance.filter_date:
                filter_dates.append(instance.filter_date)
            city = instance.venue.location if instance.venue else 'TBC'
            if city not in instances_by_city:
                instances_by_city[city] = []
            instances_by_city[city].append(instance)
            if instance.venue_id and instance.venue_id not in seen_display_venue_ids:
                seen_display_venue_ids.add(instance.venue_id)
                if instance.venue:
                    display_locations.append(instance.venue)
            prices.append(instance.price)
        context['instances_by_city'] = instances_by_city
        context['all_locations'] = filter_location_venues
        context['display_locations'] = display_locations
        context['current_location_filter'] = getattr(course, '_current_location_filter', '')
        context['min_price'] = min(prices) if prices else None
        context['has_multiple_prices'] = len(set(prices)) > 1 if prices else False

        context['instances_date_min'] = min(filter_dates) if filter_dates else None
        context['instances_date_max'] = max(filter_dates) if filter_dates else None
        context['show_instance_filters'] = len(all_instances) > 1
        
        context['schema_data'] = self.get_schema_data(course)
        context['meta_title'] = course.meta_title or f"{course.title} - Photography Courses"
        context['meta_description'] = course.meta_description or course.short_description
        context['meta_keywords'] = course.meta_keywords or f"{course.category}, {course.level}, photography course"
        
        featured = context.get('featured_instance')
        if featured:
            attach_gd_images_to_workshops([featured])
        context['header_images'] = collect_header_images(
            course,
            workshop=featured if context.get('is_location_specific') else None,
        )
        
        return context
    
    def get_schema_data(self, course):
        """Generate JSON-LD structured data for schema.org."""
        import json
        from decimal import Decimal
        
        course_schema = {
            "@context": "https://schema.org",
            "@type": "Course",
            "name": course.title,
            "description": course.description,
            "provider": {"@type": "Organization", "name": "Photography Courses"},
            "courseCode": course.slug,
            "educationalLevel": course.get_level_display(),
            "coursePrerequisites": course.prerequisites or None,
            "timeRequired": f"PT{course.duration_hours}H",
            "audience": {"@type": "Audience", "audienceType": course.audience}
        }
        
        if course.image and course.image.url:
            course_schema["image"] = self.request.build_absolute_uri(course.image.url)
        
        instances_list = getattr(course, '_filtered_instances', list(course.workshops.all()))
        offers = []
        course_instances_schema = []
        
        for instance in instances_list[:10]:
            loc = instance.venue
            instance_schema = {
                "@type": "CourseInstance",
                "courseMode": "onsite",
                "courseWorkload": f"PT{course.duration_hours}H",
                "location": {
                    "@type": "Place",
                    "name": loc.venue_name if loc else "TBC",
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": loc.venue_address if loc else "",
                        "addressLocality": loc.location if loc else "",
                        "addressRegion": "",
                        "postalCode": "",
                        "addressCountry": "GB"
                    }
                }
            }
            if workshop_is_open_dated(instance):
                instance_schema["description"] = OPEN_DATED_LABEL
            elif instance.start_date:
                instance_schema["startDate"] = instance.start_date.isoformat()
                if instance.end_date:
                    instance_schema["endDate"] = instance.end_date.isoformat()
            
            course_instances_schema.append(instance_schema)
            
            offer = {
                "@type": "Offer",
                "price": str(instance.price) if instance.price else "0",
                "priceCurrency": "GBP",
                "availability": "https://schema.org/InStock" if not instance.is_full else "https://schema.org/SoldOut",
                "url": self.request.build_absolute_uri(instance.get_absolute_url()),
                "validFrom": timezone.now().isoformat(),
                "validThrough": instance.start_date.isoformat() if instance.start_date else None
            }
            offers.append(offer)
        
        if course_instances_schema:
            course_schema["hasCourseInstance"] = course_instances_schema
            course_schema["offers"] = offers[0] if offers else None
        
        faq_schema = None
        if course.faqs.exists():
            faq_schema = {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": faq.question,
                        "acceptedAnswer": {"@type": "Answer", "text": faq.answer}
                    }
                    for faq in course.faqs.all()
                ]
            }
        
        schemas = [course_schema]
        if faq_schema:
            schemas.append(faq_schema)
        
        return json.dumps(schemas, indent=2)


class CourseSearchAPIView(APIView):
    """API endpoint for React search/filter components."""
    def get(self, request):
        queryset, _ = bookable_workshops_for_request(request)
        queryset = queryset.select_related('course', 'venue')

        category = request.GET.get('category')
        if category:
            try:
                cat_id = int(category)
                queryset = queryset.filter(course__course_category_id=cat_id)
            except (ValueError, TypeError):
                pass

        level = request.GET.get('level')
        if level and level in LEVEL_NAME_TO_ID:
            queryset = queryset.filter(
                course__course_skill_level_id=LEVEL_NAME_TO_ID[level],
            )

        serializer = WorkshopSerializer(queryset[:50], many=True)
        return Response(serializer.data)


class ContactView(FormView):
    """Contact form for booking and workshop enquiries."""
    template_name = 'courses/contact.html'
    form_class = ContactForm
    extra_context = {'page_title': 'Contact Going Digital'}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == 'GET':
            # Generate new security question
            num1 = random.randint(1, 12)
            num2 = random.randint(1, 12)
            self.request.session['contact_security'] = {
                'question': f'{num1} + {num2}',
                'answer': num1 + num2
            }
            kwargs['security_question'] = f'{num1} + {num2}'
            kwargs['expected_answer'] = num1 + num2
        else:
            # Validate against session
            security = self.request.session.get('contact_security', {})
            kwargs['security_question'] = security.get('question', '')
            kwargs['expected_answer'] = security.get('answer')
        return kwargs

    def form_valid(self, form):
        # Clear security data
        if 'contact_security' in self.request.session:
            del self.request.session['contact_security']

        region = form.cleaned_data['region']
        region_label = dict(CONTACT_REGION_CHOICES).get(region, region)

        email_body = f"""New contact form submission from Going Digital website

Region/Contact: {region_label}
Name: {form.cleaned_data['name']}
Email: {form.cleaned_data['email']}
Phone: {form.cleaned_data['phone']}

Message:
{form.cleaned_data['message']}

---
This enquiry was sent via the contact form. Information is not stored in the database.
"""
        contact_email = getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL)
        send_filtered_mail(
            subject=f'Going Digital Contact: {region_label} - {form.cleaned_data["name"]}',
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[contact_email],
            fail_silently=False,
        )
        messages.success(
            self.request,
            'Thank you for your message. We will get back to you as soon as possible.'
        )
        return redirect(reverse('courses:contact'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meta_description'] = 'Contact Going Digital for photography course bookings, workshop enquiries, gift voucher or payment queries. Get in touch with your regional team.'
        context['meta_keywords'] = 'contact Going Digital, photography course enquiry, workshop booking, gift voucher'
        return context


class GiftVoucherView(FormView):
    """Gift vouchers page with purchase request form."""
    template_name = 'courses/gift_vouchers.html'
    form_class = GiftVoucherRequestForm

    def form_valid(self, form):
        amount = int(form.cleaned_data['amount'])
        quantity = form.cleaned_data['quantity']
        total = amount * quantity

        # Only use gd_user for authenticated purchasers; guests are in gd_customer only
        user = self.request.user if self.request.user.is_authenticated else None

        from bookings.gift_voucher_basket import (
            get_or_create_customer,
            create_gift_voucher_basket,
            parse_device_and_browser,
        )
        name = form.cleaned_data['name'] or 'Customer'
        name_parts = name.strip().split(maxsplit=1)
        firstname = name_parts[0]
        lastname = name_parts[1] if len(name_parts) > 1 else ''
        customer_id, _ = get_or_create_customer(
            email=form.cleaned_data['email'],
            firstname=firstname,
            lastname=lastname,
            phone=form.cleaned_data.get('phone', ''),
        )
        user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        device_type, browser = parse_device_and_browser(user_agent)
        basket_id = create_gift_voucher_basket(
            customer_id=customer_id,
            user_id=user.id if user else None,
            amount=amount,
            quantity=quantity,
            total=total,
            purchaser_name=name,
            purchaser_email=form.cleaned_data['email'],
            purchaser_phone=form.cleaned_data.get('phone', ''),
            recipient_name=form.cleaned_data.get('recipient_name', ''),
            gift_message=form.cleaned_data.get('message', ''),
            device_type=device_type,
            browser=browser,
        )

        return redirect('payments:create_gift_voucher_checkout', basket_id=basket_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['promoted_occasions'] = get_promoted_occasions()
        context['gift_voucher_image_url'] = gift_voucher_page_image_url()
        return context


class FAQView(TemplateView):
    """Frequently Asked Questions page."""
    template_name = 'courses/faq.html'


class TermsAndConditionsView(TemplateView):
    """Terms and conditions for workshop bookings and gift vouchers."""
    template_name = 'courses/legal_page.html'

    def get_context_data(self, **kwargs):
        from website.models import LegalPage
        from website.legal_pages import get_legal_page_context

        context = super().get_context_data(**kwargs)
        context.update(get_legal_page_context(LegalPage.TERMS))
        return context


class PrivacyPolicyView(TemplateView):
    """Privacy policy and cookie statement."""
    template_name = 'courses/legal_page.html'

    def get_context_data(self, **kwargs):
        from website.models import LegalPage
        from website.legal_pages import get_legal_page_context

        context = super().get_context_data(**kwargs)
        context.update(get_legal_page_context(LegalPage.PRIVACY))
        return context


class SiteMapPageView(TemplateView):
    """
    Human-readable site map: clear hierarchy for users, crawlers that follow links,
    and structured data (ItemList) for answer engines.
    """
    template_name = 'courses/site_map.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        entries = [
            ('Home', 'courses:homepage'),
            ('Photography courses', 'courses:course_list'),
            ('Venues', 'courses:venue_list'),
            ('Gift vouchers', 'courses:gift_vouchers'),
            ('FAQ', 'courses:faq'),
            ('Terms and conditions', 'courses:terms_and_conditions'),
            ('Privacy policy', 'courses:privacy_policy'),
            ('Contact', 'courses:contact'),
            ('Editing courses', 'courses:editing_course_page'),
        ]
        sections = [
            {
                'heading': 'Main pages',
                'items': [],
            },
        ]
        item_list_schema = []
        position = 1
        for name, urlname in entries:
            path = reverse(urlname)
            abs_url = request.build_absolute_uri(path)
            row = {'name': name, 'path': path, 'absolute_url': abs_url}
            sections[0]['items'].append(row)
            item_list_schema.append({
                '@type': 'ListItem',
                'position': position,
                'name': name,
                'item': abs_url,
            })
            position += 1
        xml_url = request.build_absolute_uri(reverse('sitemap'))
        meta_description = (
            'Site map for Going Digital: photography courses, venues, gift vouchers, '
            'and support pages. An XML sitemap is also available for search engines.'
        )
        page_url = request.build_absolute_uri()
        site_map_json_ld = {
            '@context': 'https://schema.org',
            '@graph': [
                {
                    '@type': 'WebPage',
                    '@id': page_url + '#webpage',
                    'url': page_url,
                    'name': 'Site map',
                    'description': meta_description,
                    'isPartOf': {'@type': 'WebSite', 'name': 'Going Digital'},
                },
                {
                    '@type': 'ItemList',
                    '@id': page_url + '#main-pages',
                    'name': 'Main pages',
                    'numberOfItems': len(item_list_schema),
                    'itemListElement': item_list_schema,
                },
            ],
        }
        context['meta_description'] = meta_description
        context['sections'] = sections
        context['site_map_json_ld_json'] = json.dumps(site_map_json_ld, ensure_ascii=False)
        context['xml_sitemap_url'] = xml_url
        return context


class RobotsTxtView(TemplateView):
    """Serve robots.txt for search engine crawlers."""
    template_name = 'robots.txt'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sitemap_url'] = self.request.build_absolute_uri(reverse('sitemap'))
        return context

    def render_to_response(self, context, **response_kwargs):
        response_kwargs.setdefault('content_type', 'text/plain')
        return super().render_to_response(context, **response_kwargs)
