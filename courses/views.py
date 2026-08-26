"""
Course views - server-rendered for SEO.
"""
import json
from pathlib import Path
from urllib.parse import urlencode

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
from courses.html_text import rich_html_to_plain_text
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Course, Workshop, Venue, CourseCategory, LEVEL_NAME_TO_ID, LEVEL_DISPLAY_NAMES
from .forms import ContactForm, GiftVoucherRequestForm, VOUCHER_AMOUNT_CHOICES
from .utils import get_promoted_occasions, workshop_calendar_date
from .venue_schema import venue_place_schema
from .workshop_querysets import (
    OPEN_DATED_LABEL,
    apply_workshop_list_date_range,
    bookable_workshop_ordering,
    bookable_workshop_visibility_q,
    bookable_workshops_queryset,
    workshop_is_open_dated,
)
from website.models import GiftVoucherPageImage, HeroImage, BeforeAfterImage, FAQ
from website.seo import (
    HOMEPAGE_FAQ_ITEMS,
    ORGANIZATION_NAME,
    absolute_url,
    breadcrumb_schema,
    dumps_json_ld,
    homepage_faq_schema,
    local_business_schema,
    organization_schema,
    site_base_url,
)
from website.google_reviews import get_google_reviews_display
from .serializers import WorkshopSerializer
from .display_images import attach_gd_images_to_workshops, collect_header_images, primary_image_url
from .duration import duration_iso8601
from .list_card import serialize_list_card

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


def filter_instances_by_near(instances, lat, lng, radius_miles):
    """Keep workshops whose venue is within radius_miles of (lat, lng)."""
    from courses.venue_list import haversine_miles

    result = []
    for inst in instances:
        venue = inst.venue
        if not venue or venue.latitude is None or venue.longitude is None:
            continue
        try:
            distance = haversine_miles(
                float(lat),
                float(lng),
                float(venue.latitude),
                float(venue.longitude),
            )
        except (TypeError, ValueError):
            continue
        if distance <= radius_miles:
            result.append(inst)
    return result


def filter_instances_by_date_range(instances, dt_from=None, dt_to=None):
    """Match course-list date filters; open-dated workshops always remain."""
    if not dt_from and not dt_to:
        return instances
    result = []
    for inst in instances:
        if workshop_is_open_dated(inst):
            result.append(inst)
            continue
        start = getattr(inst, 'start_date', None) or getattr(inst, 'date', None)
        if not start:
            continue
        if dt_from and start < dt_from:
            continue
        if dt_to and start > dt_to:
            continue
        result.append(inst)
    return result


def _resolved_near_coords_from_request(request):
    """
    Near-me coords from ?lat=&lng=, or from place search via ?q= (e.g. London).
    Returns (lat, lng, radius, place_query_or_empty).
    """
    from courses.search_location import resolve_search_place
    from courses.venue_list import parse_near_me

    near_lat, near_lng, near_radius = parse_near_me(request.GET)
    place_q = ''
    if near_lat is None or near_lng is None:
        search = (request.GET.get('q') or '').strip()
        if search:
            resolved = resolve_search_place(search)
            if resolved:
                near_lat = resolved.latitude
                near_lng = resolved.longitude
                place_q = search
    elif (request.GET.get('q') or '').strip():
        # Keep keyword when browser near-me was not the source (optional label).
        place_q = (request.GET.get('q') or '').strip()
    return near_lat, near_lng, near_radius, place_q


def course_detail_filter_querystring(request):
    """
    Query string to carry list filters onto course detail pages.
    Uses location= for exact venue (list uses city=); lat/lng/radius or q for near/place.
    """
    params = {}
    near_lat, near_lng, near_radius, place_q = _resolved_near_coords_from_request(request)
    if near_lat is not None and near_lng is not None:
        params['lat'] = f'{float(near_lat):.6f}'.rstrip('0').rstrip('.')
        params['lng'] = f'{float(near_lng):.6f}'.rstrip('0').rstrip('.')
        params['radius'] = str(near_radius)
        if place_q:
            params['q'] = place_q
    else:
        city = normalize_city_param(
            request.GET.get('city', '') or request.GET.get('location', ''),
        )
        if city:
            params['location'] = city

    date_from, date_to, _, _ = parse_course_list_date_range(request)
    if date_from:
        params['date_from'] = date_from.isoformat()
    if date_to:
        params['date_to'] = date_to.isoformat()
    return urlencode(params)


def filter_instances_for_request(instances, request, *, location_slug=''):
    """
    Apply carried list filters to course-detail workshops.
    Path location_slug wins over query filters for venue.
    Exact ?location= / ?city= wins over near-me / place search.
    """
    instances = list(instances)
    if location_slug:
        instances = filter_instances_by_location(instances, location_slug)
    else:
        location_raw = (
            (request.GET.get('location') or '').strip()
            or (request.GET.get('city') or '').strip()
        )
        if location_raw:
            instances = filter_instances_by_location(instances, location_raw)
        else:
            near_lat, near_lng, near_radius, _place_q = _resolved_near_coords_from_request(
                request,
            )
            if near_lat is not None and near_lng is not None:
                instances = filter_instances_by_near(
                    instances, near_lat, near_lng, near_radius,
                )

    _, _, dt_from, dt_to = parse_course_list_date_range(request)
    if dt_from or dt_to:
        instances = filter_instances_by_date_range(instances, dt_from, dt_to)
    return instances


def bookable_workshops_for_request(request, *, apply_location_filter=True):
    """
    Upcoming bookable workshops for the course list.
    All workshop-level filters are applied on one queryset so a course only matches
    when the same workshop satisfies date, venue, and status constraints.
    Open-dated workshops are always included in date-filtered results.

    When `q` is a town, city or postcode (and browser near-me is not set), workshops
    are limited to venues near that place.
    """
    from courses.search_location import resolve_search_place
    from courses.venue_list import apply_near_me_to_workshop_queryset, parse_near_me

    date_from, date_to, dt_from, dt_to = parse_course_list_date_range(request)
    queryset = bookable_workshops_queryset()
    queryset = apply_workshop_list_date_range(queryset, dt_from, dt_to)
    is_map_view = request.GET.get('view') == 'map'
    near_lat, near_lng, near_radius = parse_near_me(request.GET)
    resolved_place = None
    if near_lat is None or near_lng is None:
        search = (request.GET.get('q') or '').strip()
        if search:
            resolved_place = resolve_search_place(search)
            if resolved_place:
                near_lat = resolved_place.latitude
                near_lng = resolved_place.longitude
    if near_lat is not None and near_lng is not None:
        # Near-me / place search applies on list and map; exact venue (?city=) is ignored.
        queryset = apply_near_me_to_workshop_queryset(
            queryset,
            lat=near_lat,
            lng=near_lng,
            radius_miles=near_radius,
        )
    elif apply_location_filter and not is_map_view:
        queryset = apply_venue_filter_to_workshop_qs(
            queryset, request.GET.get('city', ''),
        )
    return queryset, (date_from, date_to), resolved_place


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
        """Active hero slides for the homepage slider (url + screen orientation)."""
        heroes = HeroImage.objects.filter(is_active=True).order_by('order', 'created_at')
        return [
            {
                'url': hero.image.url,
                'orientation': hero.screen_orientation or HeroImage.ORIENTATION_BOTH,
            }
            for hero in heroes
            if hero.image
        ]
    
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
        
        google_reviews = get_google_reviews_display()
        base = site_base_url(self.request)
        course_count = context['course_count']
        homepage_graph = [
            {
                '@type': 'WebSite',
                '@id': f'{base}/#website',
                'url': f'{base}/',
                'name': f'{ORGANIZATION_NAME} Photography Courses',
                'description': (
                    f'Professional photography courses and workshops across the UK. '
                    f'{course_count}+ courses for beginners through to advanced photographers.'
                ),
                'publisher': {'@id': f'{base}/#organization'},
                'potentialAction': {
                    '@type': 'SearchAction',
                    'target': f'{base}/photography-courses/?q={{search_term_string}}',
                    'query-input': 'required name=search_term_string',
                },
            },
            organization_schema(self.request, google_reviews=google_reviews),
            local_business_schema(self.request, google_reviews=google_reviews),
            homepage_faq_schema(base),
        ]
        context['homepage_schema_json'] = dumps_json_ld(
            {'@context': 'https://schema.org', '@graph': homepage_graph},
        )
        context['homepage_faq_items'] = HOMEPAGE_FAQ_ITEMS
        context['og_title'] = 'Photography Courses - Start Your Photography Journey'
        context['og_description'] = (
            f'Master photography from beginner to aspiring professional. '
            f'{course_count}+ courses across the UK.'
        )
        context['og_url'] = f'{base}/'
        context['canonical_url'] = f'{base}/'

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
        detail_query = course_detail_filter_querystring(self.request)

        courses_data = [
            serialize_list_card(course, detail_query=detail_query)
            for course in page.object_list
        ]
        
        return JsonResponse({
            'courses': courses_data,
            'has_next': page.has_next(),
            'next_page': page.number + 1 if page.has_next() else None,
        })
    
    def get_queryset(self):
        workshop_qs, _, resolved_place = bookable_workshops_for_request(self.request)
        self._workshop_qs = workshop_qs
        self._resolved_search_place = resolved_place
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

        search = (self.request.GET.get('q') or '').strip()
        # Place keywords (town/city/postcode) already filtered workshops by distance;
        # don't also require the place name to appear in course text.
        if search and not resolved_place:
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

    def _map_workshops_queryset(self):
        """
        All bookable workshops matching the current list filters.

        Map markers must not be limited to the paginated course page, or venues
        for courses beyond page 1 (e.g. Dartmoor) disappear until a search
        shrinks the result set.
        """
        workshop_qs = getattr(self, '_workshop_qs', None)
        resolved_place = getattr(self, '_resolved_search_place', None)
        if workshop_qs is None:
            workshop_qs, _, resolved_place = bookable_workshops_for_request(self.request)

        search = (self.request.GET.get('q') or '').strip()
        if search and not resolved_place:
            workshop_qs = workshop_qs.filter(
                Q(course__course_name__icontains=search)
                | Q(course__course_description__icontains=search)
                | Q(course__description_for_workshop__icontains=search)
            )

        category = self.request.GET.get('category', '')
        if category:
            try:
                workshop_qs = workshop_qs.filter(course__course_category_id=int(category))
            except (ValueError, TypeError):
                pass

        level = self.request.GET.get('level', '')
        if level and level in LEVEL_NAME_TO_ID:
            workshop_qs = workshop_qs.filter(
                course__course_skill_level_id=LEVEL_NAME_TO_ID[level],
            )

        return (
            workshop_qs.filter(course__active=True)
            .exclude(venue_id__isnull=True)
            .exclude(venue__latitude__isnull=True)
            .exclude(venue__longitude__isnull=True)
            .select_related(
                'venue',
                'course',
                'course__course_category',
                'course__course_skill_level',
                'course__image',
            )
            .prefetch_related('course__media', 'gallery_images__image')
            .order_by(*bookable_workshop_ordering())
        )
    
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
        
        # Prepare instance data for map from ALL matching workshops (not the
        # paginated course page — otherwise venues for later courses never appear).
        import json
        instances_data = []
        map_workshops = list(self._map_workshops_queryset())
        attach_gd_images_to_workshops(map_workshops)

        for instance in map_workshops:
            course = instance.course
            if not course:
                continue
            is_bookable = (
                instance.enrollment_open
                and instance.venue
                and instance.venue.latitude is not None
                and instance.venue.longitude is not None
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
            byline_text = rich_html_to_plain_text(instance.byline or '')
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
                'duration_display': course.duration_display,
                'image_url': image_url,
                'course_url': instance_url,
                'location_name': v.name if v else 'TBC',
                'city': v.city if v else '',
                'address': v.venue_address if v else '',
                'latitude': float(v.latitude) if v and v.latitude is not None else 0,
                'longitude': float(v.longitude) if v and v.longitude is not None else 0,
                'postcode': '',
                'start_date': start_date_str,
                'date_display': date_display,
                'open_dated': workshop_is_open_dated(instance),
                'price': float(instance_price),
                'spaces_available': instance.spaces_available,
                'enrollment_open': instance.enrollment_open,
                'is_full': instance.is_full,
            })

        context['instances_data'] = dumps_json_ld(instances_data)
        context['map_workshop_count'] = len(instances_data)
        
        # Current filters
        from courses.venue_list import (
            MAX_NEAR_RADIUS_MILES,
            MIN_NEAR_RADIUS_MILES,
            NEAR_RADIUS_STEP_MILES,
            parse_near_me,
        )

        near_lat, near_lng, near_radius = parse_near_me(self.request.GET)
        near_me_active = near_lat is not None and near_lng is not None
        resolved_place = getattr(self, '_resolved_search_place', None)
        # Browser near-me wins; keyword place search only when lat/lng were not supplied.
        place_search_active = bool(resolved_place) and not near_me_active
        location_search_active = near_me_active or place_search_active

        context['current_category'] = self.request.GET.get('category', '')
        context['current_level'] = self.request.GET.get('level', '')
        # Exact venue filter is suppressed while near-me / place search is active.
        context['current_city'] = (
            '' if location_search_active else normalize_city_param(self.request.GET.get('city', ''))
        )
        context['current_search'] = self.request.GET.get('q', '')
        context['near_me_active'] = near_me_active
        context['place_search_active'] = place_search_active
        context['location_search_active'] = location_search_active
        context['place_search_label'] = resolved_place.label if place_search_active else ''
        context['near_lat'] = near_lat if near_me_active else ''
        context['near_lng'] = near_lng if near_me_active else ''
        context['near_radius'] = near_radius
        context['near_radius_min'] = MIN_NEAR_RADIUS_MILES
        context['near_radius_max'] = MAX_NEAR_RADIUS_MILES
        context['near_radius_step'] = NEAR_RADIUS_STEP_MILES
        context['near_radius_decrease'] = max(
            MIN_NEAR_RADIUS_MILES,
            near_radius - NEAR_RADIUS_STEP_MILES,
        )
        context['near_radius_increase'] = min(
            MAX_NEAR_RADIUS_MILES,
            near_radius + NEAR_RADIUS_STEP_MILES,
        )
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
            if location_search_active:
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
            exclude=('category', 'level', 'city', 'q', 'date_from', 'date_to', 'lat', 'lng', 'radius'),
            force_map=is_map_view,
        )

        category_labels = dict(context['categories'])
        level_labels = dict(context['levels'])
        filter_venues = list(context['filter_venues'])
        active_filter_chips = []
        if context['current_search']:
            if place_search_active:
                active_filter_chips.append({
                    'type': 'Near',
                    'label': f'{context["place_search_label"]} · within {near_radius} miles',
                    'url': _filter_url(exclude=('q', 'radius'), force_map=is_map_view),
                })
            else:
                active_filter_chips.append({
                    'type': 'Search',
                    'label': context['current_search'],
                    'url': _filter_url(exclude=('q',), force_map=is_map_view),
                })
        if near_me_active:
            active_filter_chips.append({
                'type': 'Near me',
                'label': f'Within {near_radius} miles',
                'url': _filter_url(exclude=('lat', 'lng', 'radius'), force_map=is_map_view),
            })
        elif context['current_city'] and not is_map_view:
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
        context['active_filter_chips'] = active_filter_chips
        context['active_filter_count'] = len(active_filter_chips)

        paginator = context.get('paginator')
        context['filter_results_count'] = paginator.count if paginator else len(context.get('courses', []))
        
        # Base URL for infinite scroll (preserve filters, JS adds format=json&page=N)
        params = {k: v for k, v in self.request.GET.items() if k != 'page'}
        if location_search_active:
            params.pop('city', None)
        base = reverse('courses:course_list')
        context['infinite_scroll_url'] = (base + '?' + urlencode(params)) if params else base
        context['course_detail_query'] = course_detail_filter_querystring(self.request)

        filter_keys = ('q', 'category', 'level', 'city', 'date_from', 'date_to', 'view', 'lat', 'lng')
        has_filters = any((self.request.GET.get(key) or '').strip() for key in filter_keys)
        context['seo_noindex'] = has_filters
        list_base = reverse('courses:course_list')
        page_obj = context.get('page_obj')

        def _list_page_url(page_number):
            query = {k: v for k, v in self.request.GET.items() if k != 'page' and v}
            if page_number > 1:
                query['page'] = str(page_number)
            qs = urlencode(query)
            path = f'{list_base}?{qs}' if qs else list_base
            return self.request.build_absolute_uri(path)

        if has_filters:
            context['canonical_url'] = self.request.build_absolute_uri(list_base)
        elif page_obj:
            context['canonical_url'] = _list_page_url(page_obj.number)
            if page_obj.has_previous():
                context['seo_prev_url'] = _list_page_url(page_obj.previous_page_number())
            if page_obj.has_next():
                context['seo_next_url'] = _list_page_url(page_obj.next_page_number())
        else:
            context['canonical_url'] = self.request.build_absolute_uri(list_base)

        context['og_title'] = 'Browse Photography Courses Across the UK'
        context['og_description'] = (
            'Browse hands-on photography courses and workshops across the UK. '
            'Filter by date, skill level, category, or map.'
        )
        context['og_url'] = context['canonical_url']

        courses_on_page = list(context.get('courses') or [])
        if courses_on_page:
            item_list = [
                {
                    '@type': 'ListItem',
                    'position': index,
                    'name': course.title,
                    'url': absolute_url(
                        self.request,
                        'courses:course_detail',
                        kwargs={'slug': course.slug},
                    ),
                }
                for index, course in enumerate(courses_on_page, start=1)
            ]
            context['course_list_schema_json'] = dumps_json_ld(
                {
                    '@context': 'https://schema.org',
                    '@type': 'CollectionPage',
                    'name': 'Photography Courses',
                    'description': context['og_description'],
                    'url': context['canonical_url'],
                    'mainEntity': {
                        '@type': 'ItemList',
                        'itemListElement': item_list,
                    },
                },
            )

        pagination_links = []
        if page_obj and page_obj.paginator.num_pages > 1 and not has_filters:
            for num in page_obj.paginator.page_range:
                pagination_links.append({
                    'number': num,
                    'url': _list_page_url(num),
                    'current': num == page_obj.number,
                })
        context['pagination_links'] = pagination_links
        
        return context


def redirect_old_course_location_url(request, location, location_slug, slug):
    """Redirect old URL format /photography-courses/<location>/<location_slug>/<slug>/ to new format."""
    new_url = reverse('courses:course_detail_by_location', kwargs={'slug': slug, 'location_slug': location_slug})
    return HttpResponsePermanentRedirect(new_url)


def _redirect_with_query(request, url):
    from website.middleware import _redirect_url_with_query
    return HttpResponsePermanentRedirect(_redirect_url_with_query(request, url))


def redirect_photography_workshops_slug(request, slug):
    """301 redirect /photography-workshops/<slug>/ to /photography-courses/<slug>/ (fallback if middleware disabled)."""
    new_url = reverse('courses:course_detail', kwargs={'slug': slug})
    return _redirect_with_query(request, new_url)


def redirect_photography_workshops_course_at_venue(request, slug, location_slug):
    """301 redirect /photography-workshops/<slug>/<venue>/ to course-at-venue URL (fallback)."""
    new_url = reverse(
        'courses:course_detail_by_location',
        kwargs={'slug': slug, 'location_slug': location_slug},
    )
    return _redirect_with_query(request, new_url)


class VenueListView(ListView):
    """
    Venue list page: /venues/
    Shows active venues with a slug, grouped by region.
    Optional ?q= text or place search (town/postcode) and near-me (?lat=&lng=&radius=).
    Place keywords use the same resolve_search_place() behaviour as photography-courses.
    """
    model = Venue
    context_object_name = 'venues'
    template_name = 'courses/venue_list.html'

    def get_queryset(self):
        from .search_location import resolve_search_place
        from .venue_list import filter_venues_by_search, parse_near_me, public_venues_queryset

        self.search_query = (self.request.GET.get('q') or '').strip()
        self.near_lat, self.near_lng, self.near_radius = parse_near_me(self.request.GET)
        self.near_me_active = self.near_lat is not None and self.near_lng is not None
        self.resolved_place = None

        if not self.near_me_active and self.search_query:
            self.resolved_place = resolve_search_place(self.search_query)
            if self.resolved_place:
                self.near_lat = self.resolved_place.latitude
                self.near_lng = self.resolved_place.longitude

        qs = public_venues_queryset()
        # Place keywords already filter by distance in get_context_data; don't also
        # require the place name to appear in venue text (same as course list).
        if self.search_query and not self.resolved_place:
            qs = filter_venues_by_search(qs, self.search_query)
        return qs.prefetch_related('media').order_by('venue_name')

    def get_context_data(self, **kwargs):
        from .venue_list import (
            DEFAULT_NEAR_RADIUS_MILES,
            MAX_NEAR_RADIUS_MILES,
            MIN_NEAR_RADIUS_MILES,
            NEAR_RADIUS_STEP_MILES,
            filter_venues_near,
            group_venues_by_region,
        )

        context = super().get_context_data(**kwargs)
        # One evaluation for both count and template (no separate COUNT query).
        venues = list(context['venues'])
        near_me_active = getattr(self, 'near_me_active', False)
        resolved_place = getattr(self, 'resolved_place', None)
        place_search_active = bool(resolved_place) and not near_me_active
        location_search_active = near_me_active or place_search_active
        near_lat = getattr(self, 'near_lat', None)
        near_lng = getattr(self, 'near_lng', None)
        near_radius = getattr(self, 'near_radius', DEFAULT_NEAR_RADIUS_MILES)

        if location_search_active and near_lat is not None and near_lng is not None:
            venues = filter_venues_near(
                venues,
                lat=near_lat,
                lng=near_lng,
                radius_miles=near_radius,
            )
            if near_me_active:
                group_name = f'Within {near_radius} miles of you'
            else:
                place_label = resolved_place.label if resolved_place else self.search_query
                group_name = f'Within {near_radius} miles of {place_label}'
            context['venue_groups'] = [{
                'name': group_name,
                'venues': venues,
            }] if venues else []
        else:
            context['venue_groups'] = group_venues_by_region(venues)
            # Only link region headings to SEO landings that have bookable workshops.
            from .location_landings import indexable_region_slugs
            indexable_slugs = indexable_region_slugs()
            for group in context['venue_groups']:
                if group.get('slug') and group['slug'] not in indexable_slugs:
                    group['slug'] = None

        context['venues'] = venues
        context['venue_count'] = len(venues)
        context['current_search'] = getattr(self, 'search_query', '')
        context['near_me_active'] = near_me_active
        context['place_search_active'] = place_search_active
        context['location_search_active'] = location_search_active
        context['place_search_label'] = (
            resolved_place.label if place_search_active else ''
        )
        # Only expose browser coords when Near me is active (not place search).
        context['near_lat'] = near_lat if near_me_active else ''
        context['near_lng'] = near_lng if near_me_active else ''
        context['near_radius'] = near_radius
        context['near_radius_min'] = MIN_NEAR_RADIUS_MILES
        context['near_radius_max'] = MAX_NEAR_RADIUS_MILES
        context['near_radius_step'] = NEAR_RADIUS_STEP_MILES
        context['near_radius_decrease'] = max(
            MIN_NEAR_RADIUS_MILES,
            near_radius - NEAR_RADIUS_STEP_MILES,
        )
        context['near_radius_increase'] = min(
            MAX_NEAR_RADIUS_MILES,
            near_radius + NEAR_RADIUS_STEP_MILES,
        )
        context['seo_noindex'] = bool(context['current_search'] or location_search_active)
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
        venue_url = absolute_url(
            self.request,
            'courses:venue_detail',
            kwargs={'location_slug': venue.slug},
        )
        context['canonical_url'] = venue_url
        context['og_title'] = context['meta_title']
        context['og_description'] = context['meta_description']
        context['og_url'] = venue_url
        if context['venue_images']:
            context['og_image'] = self.request.build_absolute_uri(context['venue_images'][0].image.url)

        place_schema = venue_place_schema(
            venue,
            description=context['meta_description'],
            url=venue_url,
        )
        graph = [
            place_schema,
            breadcrumb_schema([
                ('Photography courses', absolute_url(self.request, 'courses:course_list')),
                ('Venues', absolute_url(self.request, 'courses:venue_list')),
                (venue.venue_name, None),
            ]),
        ]
        context['venue_schema_json'] = dumps_json_ld(
            {'@context': 'https://schema.org', '@graph': graph},
        )
        return context


def _location_landing_context(
    request,
    *,
    place_name,
    place_kind,
    venues,
    workshops,
    page_url,
    breadcrumb_tail,
):
    """Shared SEO + list context for city/region landings."""
    venue_count = len(venues)
    course_titles = []
    seen_courses = set()
    for workshop in workshops:
        course = workshop.course
        if not course or course.pk in seen_courses:
            continue
        seen_courses.add(course.pk)
        course_titles.append(course.title)

    meta_title = f'Photography Courses in {place_name} | Going Digital'
    if place_kind == 'region':
        meta_description = (
            f'Browse photography courses and workshops across {place_name}. '
            f'{venue_count} venue{"s" if venue_count != 1 else ""} with hands-on training from Going Digital.'
        )
        intro = (
            f'Find hands-on photography courses across {place_name}. '
            f'Choose a venue below or book an upcoming workshop with Going Digital.'
        )
    else:
        meta_description = (
            f'Photography courses in {place_name}. '
            f'Book workshops at {venue_count} local venue{"s" if venue_count != 1 else ""} with Going Digital.'
        )
        intro = (
            f'Looking for photography courses in {place_name}? '
            f'Browse venues and upcoming workshops below, then book online.'
        )

    item_list = []
    for position, venue in enumerate(venues, start=1):
        item_list.append({
            '@type': 'ListItem',
            'position': position,
            'name': venue.venue_name,
            'url': absolute_url(
                request,
                'courses:venue_detail',
                kwargs={'location_slug': venue.slug},
            ),
        })

    graph = [
        {
            '@type': 'CollectionPage',
            '@id': f'{page_url}#webpage',
            'url': page_url,
            'name': meta_title,
            'description': meta_description,
            'isPartOf': {'@type': 'WebSite', 'name': ORGANIZATION_NAME},
            'about': {
                '@type': 'Place',
                'name': place_name,
                'address': {'@type': 'PostalAddress', 'addressCountry': 'GB'},
            },
        },
        {
            '@type': 'ItemList',
            '@id': f'{page_url}#venues',
            'name': f'Photography course venues in {place_name}',
            'numberOfItems': len(item_list),
            'itemListElement': item_list,
        },
        breadcrumb_schema([
            ('Photography courses', absolute_url(request, 'courses:course_list')),
            ('Locations', absolute_url(request, 'courses:location_landing_index')),
            breadcrumb_tail,
        ]),
    ]

    return {
        'place_name': place_name,
        'place_kind': place_kind,
        'venues': venues,
        'venue_count': venue_count,
        'instances': workshops,
        'course_count': len(course_titles),
        'intro': intro,
        'meta_title': meta_title,
        'meta_description': meta_description[:160],
        'canonical_url': page_url,
        'og_title': meta_title,
        'og_description': meta_description[:160],
        'og_url': page_url,
        'location_schema_json': dumps_json_ld(
            {'@context': 'https://schema.org', '@graph': graph},
        ),
    }


class LocationLandingIndexView(TemplateView):
    """Hub listing indexable region and city landings."""
    template_name = 'courses/location_landing_index.html'

    def get_context_data(self, **kwargs):
        from .location_landings import indexable_cities, indexable_regions

        context = super().get_context_data(**kwargs)
        regions = list(indexable_regions())
        cities = indexable_cities()
        page_url = absolute_url(self.request, 'courses:location_landing_index')
        meta_description = (
            'Browse Going Digital photography courses by UK region or city. '
            'Find venues and upcoming workshops near you.'
        )
        context.update({
            'regions': regions,
            'cities': cities,
            'meta_title': 'Photography Courses by Location | Going Digital',
            'meta_description': meta_description,
            'canonical_url': page_url,
            'og_title': 'Photography Courses by Location | Going Digital',
            'og_description': meta_description,
            'og_url': page_url,
            'location_schema_json': dumps_json_ld(
                {
                    '@context': 'https://schema.org',
                    '@graph': [
                        {
                            '@type': 'CollectionPage',
                            'url': page_url,
                            'name': 'Photography Courses by Location',
                            'description': meta_description,
                        },
                        breadcrumb_schema([
                            ('Photography courses', absolute_url(self.request, 'courses:course_list')),
                            ('Locations', None),
                        ]),
                    ],
                },
            ),
        })
        return context


class RegionLandingView(TemplateView):
    """Indexable region hub: /photography-courses/regions/<slug>/"""
    template_name = 'courses/location_landing.html'

    def get_context_data(self, **kwargs):
        from django.http import Http404
        from .location_landings import (
            get_indexable_region,
            landing_workshops_for_venues,
            region_landing_venues,
        )

        context = super().get_context_data(**kwargs)
        region = get_indexable_region(self.kwargs.get('slug', ''))
        if region is None:
            raise Http404('No photography courses found for this region.')

        venues = list(region_landing_venues(region))
        if not venues:
            raise Http404('No photography courses found for this region.')

        workshops = landing_workshops_for_venues([v.pk for v in venues])
        page_url = absolute_url(
            self.request,
            'courses:region_landing',
            kwargs={'slug': region.slug},
        )
        place_name = (region.region_name or '').strip() or region.slug
        context.update(_location_landing_context(
            self.request,
            place_name=place_name,
            place_kind='region',
            venues=venues,
            workshops=workshops,
            page_url=page_url,
            breadcrumb_tail=(place_name, None),
        ))
        context['region'] = region
        return context


class CityLandingView(TemplateView):
    """Indexable city hub: /photography-courses/in/<slug>/"""
    template_name = 'courses/location_landing.html'

    def get_context_data(self, **kwargs):
        from django.http import Http404
        from .location_landings import (
            city_landing_venues,
            get_indexable_city,
            landing_workshops_for_venues,
        )

        context = super().get_context_data(**kwargs)
        city = get_indexable_city(self.kwargs.get('slug', ''))
        if city is None:
            raise Http404('No photography courses found for this location.')

        venues = list(city_landing_venues(city))
        if not venues:
            raise Http404('No photography courses found for this location.')

        workshops = landing_workshops_for_venues([v.pk for v in venues])
        page_url = absolute_url(
            self.request,
            'courses:city_landing',
            kwargs={'slug': city.slug},
        )
        context.update(_location_landing_context(
            self.request,
            place_name=city.name,
            place_kind='city',
            venues=venues,
            workshops=workshops,
            page_url=page_url,
            breadcrumb_tail=(city.name, None),
        ))
        context['city'] = city
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
        """Get course by slug, optionally filtered by location_slug or list carry filters."""
        slug = self.kwargs.get('slug')
        location_slug = self.kwargs.get('location_slug', '')

        if queryset is None:
            queryset = self.get_queryset()

        course = get_object_or_404(queryset, slug=slug, active=True)

        all_instances = list(course.workshops.all())
        course._all_instances = all_instances

        filtered = filter_instances_for_request(
            all_instances,
            self.request,
            location_slug=location_slug,
        )
        course._filtered_instances = filtered

        if location_slug:
            course._filtered_location_slug = location_slug
            course._filtered_location = (
                filtered[0].venue.location
                if filtered and filtered[0].venue
                else None
            )
            course._current_location_filter = ''
        else:
            course._filtered_location_slug = None
            course._filtered_location = None
            location_raw = (
                (self.request.GET.get('location') or '').strip()
                or (self.request.GET.get('city') or '').strip()
            )
            course._current_location_filter = normalize_city_param(location_raw)

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

        bookable_instances = [
            instance for instance in instances_list
            if instance.enrollment_open and not instance.is_full
        ]
        context['bookable_instance_count'] = len(bookable_instances)
        context['single_bookable_instance'] = (
            bookable_instances[0] if len(bookable_instances) == 1 else None
        )

        context['instances_date_min'] = min(filter_dates) if filter_dates else None
        context['instances_date_max'] = max(filter_dates) if filter_dates else None
        context['show_instance_filters'] = len(all_instances) > 1
        
        context['schema_data'] = self.get_schema_data(course)
        context['meta_title'] = course.meta_title or f"{course.title} - Photography Courses"
        context['meta_description'] = course.meta_description or course.short_description
        context['meta_keywords'] = course.meta_keywords or f"{course.category}, {course.level}, photography course"

        if context.get('is_location_specific') and getattr(course, '_filtered_location_slug', None):
            context['canonical_url'] = absolute_url(
                self.request,
                'courses:course_detail_by_location',
                kwargs={'slug': course.slug, 'location_slug': course._filtered_location_slug},
            )
        else:
            context['canonical_url'] = absolute_url(
                self.request,
                'courses:course_detail',
                kwargs={'slug': course.slug},
            )
        context['og_title'] = context['meta_title']
        context['og_description'] = course.short_description or context['meta_description']
        context['og_url'] = context['canonical_url']
        context['og_type'] = 'product'
        
        featured = context.get('featured_instance')
        if featured:
            attach_gd_images_to_workshops([featured])
        header_images = collect_header_images(
            course,
            workshop=featured if context.get('is_location_specific') else None,
        )
        context['header_images'] = header_images
        header_url = header_images[0]['url'] if header_images else primary_image_url(
            course=course,
            workshop=featured if context.get('is_location_specific') else None,
        )
        if header_url:
            context['og_image'] = self.request.build_absolute_uri(header_url)
        
        return context
    
    def get_schema_data(self, course):
        """Generate JSON-LD structured data for schema.org."""
        course_schema = {
            "@type": "Course",
            "name": course.title,
            "description": course.description,
            "provider": {
                "@type": "Organization",
                "name": ORGANIZATION_NAME,
                "url": site_base_url(self.request),
            },
            "courseCode": course.slug,
            "educationalLevel": course.get_level_display(),
            "coursePrerequisites": course.prerequisites or None,
            "audience": {"@type": "Audience", "audienceType": course.audience}
        }
        if course.duration_iso8601:
            course_schema["timeRequired"] = course.duration_iso8601
        
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
                "location": venue_place_schema(loc) if loc else {
                    "@type": "Place",
                    "name": "TBC",
                    "address": {
                        "@type": "PostalAddress",
                        "addressCountry": "GB",
                    },
                },
            }
            workload = instance.duration_display and duration_iso8601(
                instance.start_date,
                instance.end_date,
            )
            if workload:
                instance_schema["courseWorkload"] = workload
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

        breadcrumb_items = [
            ('Photography courses', absolute_url(self.request, 'courses:course_list')),
        ]
        location_slug = getattr(course, '_filtered_location_slug', None)
        if location_slug:
            breadcrumb_items.append(
                (course.title, absolute_url(self.request, 'courses:course_detail', kwargs={'slug': course.slug})),
            )
            instances = getattr(course, '_filtered_instances', [])
            venue_name = (
                instances[0].venue.name
                if instances and instances[0].venue
                else location_slug.replace('-', ' ').title()
            )
            breadcrumb_items.append((venue_name, None))
        else:
            breadcrumb_items.append((course.title, None))

        graph = [course_schema, breadcrumb_schema(breadcrumb_items)]
        if faq_schema:
            graph.append(faq_schema)

        return dumps_json_ld(
            {'@context': 'https://schema.org', '@graph': graph},
        )


class CourseSearchAPIView(APIView):
    """API endpoint for React search/filter components."""
    def get(self, request):
        queryset, *_ = bookable_workshops_for_request(request)
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

    def form_valid(self, form):
        phone = (form.cleaned_data.get('phone') or '').strip() or '—'
        order_number = (form.cleaned_data.get('order_number') or '').strip() or '—'

        email_body = f"""New contact form submission from Going Digital website

Name: {form.cleaned_data['name']}
Email: {form.cleaned_data['email']}
Phone: {phone}
Order number: {order_number}

Message:
{form.cleaned_data['message']}

---
This enquiry was sent via the contact form. Information is not stored in the database.
"""
        contact_email = getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL)
        send_filtered_mail(
            subject=f'Going Digital Contact: {form.cleaned_data["name"]}',
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
        context['meta_description'] = (
            'Contact Going Digital for photography course bookings, workshop enquiries, '
            'gift voucher or payment queries.'
        )
        context['meta_keywords'] = (
            'contact Going Digital, photography course enquiry, workshop booking, gift voucher'
        )
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
            ('Courses by location', 'courses:location_landing_index'),
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
        context['site_map_json_ld_json'] = dumps_json_ld(site_map_json_ld)
        context['xml_sitemap_url'] = xml_url
        return context


class RobotsTxtView(TemplateView):
    """Serve robots.txt for search engine crawlers."""
    template_name = 'robots.txt'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sitemap_url'] = self.request.build_absolute_uri(reverse('sitemap'))
        context['llms_url'] = self.request.build_absolute_uri(reverse('llms_txt'))
        return context

    def render_to_response(self, context, **response_kwargs):
        response_kwargs.setdefault('content_type', 'text/plain')
        return super().render_to_response(context, **response_kwargs)


class LlmsTxtView(TemplateView):
    """Machine-readable site summary for answer engines (llms.txt)."""
    template_name = 'llms.txt'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = site_base_url(self.request)
        context['site_base_url'] = base
        context['course_count'] = Course.objects.filter(active=True).count()
        context['faq_url'] = absolute_url(self.request, 'courses:faq')
        context['course_list_url'] = absolute_url(self.request, 'courses:course_list')
        context['contact_url'] = absolute_url(self.request, 'courses:contact')
        context['gift_vouchers_url'] = absolute_url(self.request, 'courses:gift_vouchers')
        context['site_map_url'] = absolute_url(self.request, 'courses:site_map')
        context['locations_url'] = absolute_url(self.request, 'courses:location_landing_index')
        context['xml_sitemap_url'] = self.request.build_absolute_uri(reverse('sitemap'))
        return context

    def render_to_response(self, context, **response_kwargs):
        response_kwargs.setdefault('content_type', 'text/plain; charset=utf-8')
        return super().render_to_response(context, **response_kwargs)
