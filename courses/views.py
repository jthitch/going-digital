"""
Course views - server-rendered for SEO.
"""
import json
import random
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.views.generic import ListView, DetailView, TemplateView, FormView
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Course, Workshop, Venue, CourseCategory, LEVEL_NAME_TO_ID, LEVEL_DISPLAY_NAMES
from .forms import ContactForm, GiftVoucherRequestForm, CONTACT_REGION_CHOICES, VOUCHER_AMOUNT_CHOICES
from .utils import get_promoted_occasions
from website.models import GiftVoucherPageImage, HeroImage, Testimonial, BeforeAfterImage, FAQ
from .serializers import WorkshopSerializer

# Fallback when no admin image: optional legacy file in MEDIA_ROOT, then bundled static SVG.
_GIFT_VOUCHER_LEGACY_MEDIA_REL = 'gd_images/im-t8-f1-0a11ba8c74817bc2c7008aa89413e39b.jpg'
_GIFT_VOUCHER_DEFAULT_STATIC = 'img/gift-vouchers/hero-default.svg'


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
        
        # Get active testimonials (managed by platform admins)
        context['testimonials'] = Testimonial.objects.filter(
            is_active=True
        ).order_by('order', 'created_at')

        now = timezone.now()
        workshop_prefetch = Prefetch(
            'workshops',
            queryset=Workshop.objects.filter(active=1, date__gte=now).select_related('venue'),
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
            workshops__date__gte=timezone.now()
        ).values_list('location', flat=True).distinct().exclude(location__isnull=True).exclude(location='').order_by('location')[:10])

        # Course stats for marketing copy: courses across the UK, beginner to aspiring professional
        courses_with_instances = Course.objects.filter(
            active=True,
            workshops__active=1,
            workshops__date__gte=timezone.now(),
            workshops__venue__active=1
        ).distinct()
        context['course_count'] = courses_with_instances.count() or Course.objects.filter(active=True).count()
        context['location_count'] = Venue.objects.filter(
            active=1,
            workshops__active=1,
            workshops__date__gte=timezone.now()
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
        
        courses_data = []
        for course in page.object_list:
            img_url = ''
            if course.image and course.image.url:
                img_url = course.image.url
            else:
                fi = getattr(course, 'first_uploaded_image', None)
                if fi and getattr(fi, 'image', None):
                    img_url = fi.image.url
            locations = list(
                course.workshops.values_list('venue__venue_name', flat=True).distinct()
            )
            locations = [loc for loc in locations if loc]
            
            courses_data.append({
                'id': course.id,
                'title': course.title,
                'slug': course.slug,
                'category': course.get_card_category_display(),
                'short_description': (course.get_card_short_description() or '')[:200],
                'level': course.level,
                'level_display': course.get_level_display(),
                'duration_hours': course.duration_hours,
                'min_price': str(course.min_price),
                'image_url': img_url,
                'locations': locations[:5],
                'detail_url': reverse('courses:course_detail', kwargs={'slug': course.slug}),
            })
        
        return JsonResponse({
            'courses': courses_data,
            'has_next': page.has_next(),
            'next_page': page.number + 1 if page.has_next() else None,
        })
    
    def get_queryset(self):
        # Only show courses that have at least one valid instance
        # (enrollment_open=True, start_date in future, location is active)
        queryset = Course.objects.filter(
            active=True,
            workshops__active=1,
            workshops__date__gte=timezone.now(),
            workshops__venue__active=1
        ).distinct().select_related(
            'course_category', 'course_skill_level', 'image',
        ).prefetch_related(
            Prefetch('workshops', queryset=Workshop.objects.filter(
                active=1,
                date__gte=timezone.now()
            ).select_related('venue', 'course').order_by('date')),
            'media'
        ).order_by('course_category__display_order', 'course_skill_level__display_order', 'display_order', 'course_name')
        
        # Search by query parameter
        search = self.request.GET.get('q', '')
        if search:
            queryset = queryset.filter(
                Q(course_name__icontains=search) |
                Q(course_description__icontains=search) |
                Q(description_for_workshop__icontains=search)
            )
        
        # Filter by category (course_category_id from database)
        category = self.request.GET.get('category', '')
        if category:
            try:
                cat_id = int(category)
                queryset = queryset.filter(course_category_id=cat_id)
            except (ValueError, TypeError):
                pass
        
        # Filter by level (legacy course_skill_level_id)
        level = self.request.GET.get('level', '')
        if level and level in LEVEL_NAME_TO_ID:
            queryset = queryset.filter(course_skill_level_id=LEVEL_NAME_TO_ID[level])
        
        # Filter by location/city
        city = self.request.GET.get('city', '')
        if city:
            queryset = queryset.filter(
                workshops__venue__location__iexact=city,
                workshops__venue__active=1
            ).distinct()
        
        # Filter by instructor - Workshop has tutor_id (gd_tutor), no instructor FK; skip for now
        
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
            workshops__active=1,
            workshops__date__gte=timezone.now(),
            workshops__venue__active=1
        ).distinct().count()
        # Get unique cities from active locations
        context['cities'] = Venue.objects.filter(
            workshops__active=1,
            workshops__date__gte=timezone.now()
        ).values_list('location', flat=True).distinct().exclude(location__isnull=True).exclude(location='').order_by('location')
        
        # Prepare instance data for map (convert to JSON-safe format)
        # Show all bookable instances, not just one per course
        import json
        from datetime import datetime
        instances_data = []
        
        # Get all bookable instances from the filtered courses
        for course in context['courses']:
            for instance in course.workshops.all():
                if (instance.enrollment_open and 
                    instance.start_date >= timezone.now() and 
                    instance.venue and 
                    instance.venue.is_active and
                    instance.venue.latitude and 
                    instance.venue.longitude):
                    
                    # Format start date for display (dd mmmm yyyy)
                    start_date_str = instance.start_date.strftime('%d %B %Y')
                    if instance.start_date.date() == instance.end_date.date():
                        date_display = start_date_str
                    else:
                        end_date_str = instance.end_date.strftime('%d %B %Y')
                        date_display = f"{start_date_str} - {end_date_str}"
                    
                    # Get instance-specific URL
                    instance_url = instance.get_absolute_url()
                    
                    # Get price (Workshop has cost)
                    instance_price = instance.price
                    v = instance.venue
                    image_url = ''
                    if getattr(course, 'image_id', None) and course.image and getattr(course.image, 'file_name', None):
                        image_url = course.image.url
                    else:
                        fu = course.first_uploaded_image
                        if fu and fu.image:
                            image_url = fu.image.url
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
                        'price': float(instance_price),
                        'spaces_available': instance.spaces_available,
                        'instructor_name': None,
                        'enrollment_open': instance.enrollment_open,
                        'is_full': instance.is_full,
                    })
        
        context['instances_data'] = json.dumps(instances_data)
        
        # Current filters
        context['current_category'] = self.request.GET.get('category', '')
        context['current_level'] = self.request.GET.get('level', '')
        context['current_city'] = self.request.GET.get('city', '')
        context['current_search'] = self.request.GET.get('q', '')
        context['current_instructor'] = self.request.GET.get('instructor', '')
        
        # Query string for category buttons (preserves other filters, excludes category & page)
        from urllib.parse import urlencode
        other_params = {k: v for k, v in self.request.GET.items() if k not in ('category', 'page')}
        context['other_params_query'] = urlencode(other_params) if other_params else ''
        # Level buttons: preserve category etc., exclude level so links are not duplicated
        other_params_no_level = {k: v for k, v in self.request.GET.items() if k not in ('level', 'page')}
        context['other_params_for_level_query'] = (
            urlencode(other_params_no_level) if other_params_no_level else ''
        )
        
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
        instances = Workshop.objects.filter(
            venue=venue,
            course__active=True,
            active=1,
            date__gte=timezone.now()
        ).select_related('course', 'venue').order_by('date')
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
                'venue', 'course'
            ).filter(
                active=1,
                date__gte=timezone.now()
            ).order_by('date')),
            'faqs',
            'media'
        ).select_related()
    
    def get_object(self, queryset=None):
        """Get course by slug, optionally filtered by location_slug (venue-specific page)."""
        slug = self.kwargs.get('slug')
        location_slug = self.kwargs.get('location_slug', '')
        
        if queryset is None:
            queryset = self.get_queryset()
        
        course = get_object_or_404(queryset, slug=slug, active=True)
        
        # Get all workshops and convert to list for easier handling
        all_instances = list(course.workshops.all())
        
        # If location_slug is provided, filter to that venue
        if location_slug:
            course._filtered_location_slug = location_slug
            course._filtered_instances = [
                inst for inst in all_instances
                if inst.venue and inst.venue.slug == location_slug
            ]
            course._filtered_location = (
                course._filtered_instances[0].venue.location if course._filtered_instances and course._filtered_instances[0].venue else None
            )
        else:
            course._filtered_location = None
            course._filtered_location_slug = None
            course._filtered_instances = all_instances
        
        return course
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        # Convert instances to list if it's a RelatedManager
        if hasattr(course, '_filtered_instances'):
            instances_list = course._filtered_instances
        else:
            instances_list = list(course.workshops.all())
        
        context['featured_instance'] = instances_list[0] if instances_list else None
        
        # Check if this is a location-specific page (URL has location_slug, not venue.location which can be empty)
        context['is_location_specific'] = bool(getattr(course, '_filtered_location_slug', None) and instances_list)
        
        # Group instances by location/city
        instances_by_city = {}
        all_locations = []
        seen_location_ids = set()
        prices = []
        for instance in instances_list:
            city = instance.venue.location if instance.venue else 'TBC'
            if city not in instances_by_city:
                instances_by_city[city] = []
            instances_by_city[city].append(instance)
            if instance.venue_id and instance.venue_id not in seen_location_ids:
                seen_location_ids.add(instance.venue_id)
                if instance.venue:
                    all_locations.append(instance.venue)
            prices.append(instance.price)
        context['instances_by_city'] = instances_by_city
        context['all_locations'] = all_locations
        context['min_price'] = min(prices) if prices else None
        context['has_multiple_prices'] = len(set(prices)) > 1 if prices else False
        
        context['schema_data'] = self.get_schema_data(course)
        context['meta_title'] = course.meta_title or f"{course.title} - Photography Courses"
        context['meta_description'] = course.meta_description or course.short_description
        context['meta_keywords'] = course.meta_keywords or f"{course.category}, {course.level}, photography course"
        
        # Header images for course page (gd_image + CourseMedia images) - used for slider when multiple
        header_images = []
        if course.image and course.image.url:
            header_images.append({'url': course.image.url, 'alt': course.title})
        for m in course.media.all():
            if m.media_type == 'image' and m.image:
                header_images.append({'url': m.image.url, 'alt': m.caption or course.title})
        context['header_images'] = header_images
        
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
                "startDate": instance.start_date.isoformat(),
                "endDate": instance.end_date.isoformat(),
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
        queryset = Workshop.objects.filter(
            course__active=True,
            active=1,
            date__gte=timezone.now()
        ).select_related('course', 'venue')
        
        city = request.GET.get('city')
        if city:
            queryset = queryset.filter(venue__location__iexact=city)
        
        category = request.GET.get('category')
        if category:
            try:
                cat_id = int(category)
                queryset = queryset.filter(course__course_category_id=cat_id)
            except (ValueError, TypeError):
                pass
        
        level = request.GET.get('level')
        if level and level in LEVEL_NAME_TO_ID:
            queryset = queryset.filter(course__course_skill_level_id=LEVEL_NAME_TO_ID[level])
        
        date_from = request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        
        date_to = request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
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
        send_mail(
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
