"""
Course views - server-rendered for SEO.
"""
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, TemplateView
from django.db.models import Q, Prefetch
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Course, CourseInstance, Location, FAQ, HeroImage, Testimonial, BeforeAfterImage
from .serializers import CourseInstanceSerializer


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
        
        # Get "Get Off Auto" course (Step 1 - Introduction to Photography)
        context['intro_course'] = Course.objects.filter(
            is_active=True,
            slug__icontains='get-off-auto'
        ).prefetch_related('instances').first()
        
        # If not found by slug, try by title
        if not context['intro_course']:
            context['intro_course'] = Course.objects.filter(
                is_active=True,
                title__icontains='Get Off Auto'
            ).prefetch_related('instances').first()
        
        # Get courses organized by level-based structure
        # Level 1, 2, 3 correspond to beginner, intermediate, advanced
        context['level_1_courses'] = Course.objects.filter(
            is_active=True,
            level='beginner'
        ).prefetch_related('instances')
        
        context['level_2_courses'] = Course.objects.filter(
            is_active=True,
            level='intermediate'
        ).prefetch_related('instances')
        
        context['level_3_courses'] = Course.objects.filter(
            is_active=True,
            level='advanced'
        ).prefetch_related('instances')
        
        # Editing, Residentials, Bespoke - search by title keywords
        context['editing_courses'] = Course.objects.filter(
            is_active=True
        ).filter(
            Q(title__icontains='editing') | Q(title__icontains='edit') | 
            Q(short_description__icontains='editing') | Q(description__icontains='editing')
        ).prefetch_related('instances')
        
        context['residentials_courses'] = Course.objects.filter(
            is_active=True
        ).filter(
            Q(title__icontains='residential') | Q(title__icontains='residentials') |
            Q(short_description__icontains='residential') | Q(description__icontains='residential')
        ).prefetch_related('instances')
        
        context['bespoke_courses'] = Course.objects.filter(
            is_active=True
        ).filter(
            Q(title__icontains='bespoke') | Q(title__icontains='custom') |
            Q(short_description__icontains='bespoke') | Q(description__icontains='bespoke')
        ).prefetch_related('instances')
        
        # Get featured courses by level (for other sections)
        context['beginner_courses'] = Course.objects.filter(
            is_active=True,
            level='beginner'
        ).prefetch_related('instances')[:6]
        
        context['intermediate_courses'] = Course.objects.filter(
            is_active=True,
            level='intermediate'
        ).prefetch_related('instances')[:6]
        
        context['advanced_courses'] = Course.objects.filter(
            is_active=True,
            level='advanced'
        ).prefetch_related('instances')[:6]
        
        # Get all categories
        context['categories'] = Course.CATEGORY_CHOICES
        
        # Get cities with active courses
        context['cities'] = Location.objects.filter(
            is_active=True,
            course_instances__enrollment_open=True,
            course_instances__start_date__gte=timezone.now()
        ).values_list('city', flat=True).distinct().order_by('city')[:10]
        
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
            is_active=True
        ).filter(
            Q(title__icontains='editing') | Q(title__icontains='edit') | 
            Q(short_description__icontains='editing') | Q(description__icontains='editing')
        ).prefetch_related('instances')
        
        # Get before/after images for the interactive slider
        context['before_after_images'] = BeforeAfterImage.objects.filter(
            is_active=True
        ).order_by('order', 'created_at')
        
        return context


class CourseListView(ListView):
    """
    List all active courses with search/filter capability.
    Supports server-side filtering for SEO.
    """
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'
    paginate_by = 12
    
    def get_queryset(self):
        # Only show courses that have at least one valid instance
        # (enrollment_open=True, start_date in future, location is active)
        queryset = Course.objects.filter(
            is_active=True,
            instances__enrollment_open=True,
            instances__start_date__gte=timezone.now(),
            instances__location__is_active=True
        ).distinct().prefetch_related(
            Prefetch('instances', queryset=CourseInstance.objects.filter(
                enrollment_open=True,
                start_date__gte=timezone.now()
            ).select_related('location').order_by('start_date'))
        )
        
        # Search by query parameter
        search = self.request.GET.get('q', '')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(short_description__icontains=search)
            )
        
        # Filter by category
        category = self.request.GET.get('category', '')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by level
        level = self.request.GET.get('level', '')
        if level:
            queryset = queryset.filter(level=level)
        
        # Filter by location/city
        city = self.request.GET.get('city', '')
        if city:
            queryset = queryset.filter(
                instances__location__city__iexact=city,
                instances__location__is_active=True
            ).distinct()
        
        # Filter by instructor
        instructor = self.request.GET.get('instructor', '')
        if instructor:
            queryset = queryset.filter(
                Q(instances__instructor__user__first_name__icontains=instructor) |
                Q(instances__instructor__user__last_name__icontains=instructor) |
                Q(instances__instructor__user__username__icontains=instructor)
            ).distinct()
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Course.CATEGORY_CHOICES
        context['levels'] = Course.LEVEL_CHOICES
        # Get unique cities from active locations
        context['cities'] = Location.objects.filter(
            is_active=True,
            course_instances__enrollment_open=True,
            course_instances__start_date__gte=timezone.now()
        ).values_list('city', flat=True).distinct().order_by('city')
        
        # Prepare location data for map (convert to JSON-safe format)
        import json
        locations_data = []
        for course in context['courses']:
            # Get first available instance for each course
            first_instance = course.instances.first()
            if first_instance and first_instance.location:
                location = first_instance.location
                if location.latitude and location.longitude:
                    locations_data.append({
                        'course_title': course.title,
                        'course_slug': course.slug,
                        'course_url': course.get_absolute_url(),  # Use general course URL to show all instances
                        'location_name': location.name,
                        'city': location.city,
                        'address': location.full_address,
                        'latitude': float(location.latitude),
                        'longitude': float(location.longitude),
                        'postcode': location.postal_code,
                    })
        context['locations_data'] = json.dumps(locations_data)
        
        # Current filters
        context['current_category'] = self.request.GET.get('category', '')
        context['current_level'] = self.request.GET.get('level', '')
        context['current_city'] = self.request.GET.get('city', '')
        context['current_search'] = self.request.GET.get('q', '')
        context['current_instructor'] = self.request.GET.get('instructor', '')
        
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
            Prefetch('instances', queryset=CourseInstance.objects.select_related(
                'location', 'location__franchise', 'instructor', 'instructor__user'
            ).filter(
                enrollment_open=True,
                start_date__gte=timezone.now()
            ).order_by('start_date')),
            'faqs'
        ).select_related()
    
    def get_object(self, queryset=None):
        """Get course by slug, optionally filtered by location, location slug, and postcode."""
        slug = self.kwargs.get('slug')
        location = self.kwargs.get('location', '').lower().replace('-', ' ')
        location_slug = self.kwargs.get('location_slug', '')
        postcode = self.kwargs.get('postcode', '').upper()
        
        if queryset is None:
            queryset = self.get_queryset()
        
        course = get_object_or_404(queryset, slug=slug, is_active=True)
        
        # Get all instances and convert to list for easier handling
        all_instances = list(course.instances.all())
        
        # If location, location_slug, and postcode are provided, filter instances
        if location and location_slug and postcode:
            course._filtered_location = location
            course._filtered_location_slug = location_slug
            course._filtered_postcode = postcode
            # Filter by matching city, slug, and postcode
            course._filtered_instances = [
                inst for inst in all_instances 
                if inst.location.city.lower() == location 
                and inst.location.slug == location_slug
                and inst.location.postal_code.replace(' ', '').upper() == postcode
            ]
        else:
            course._filtered_location = None
            course._filtered_location_slug = None
            course._filtered_postcode = None
            course._filtered_instances = all_instances
        
        return course
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        # Convert instances to list if it's a RelatedManager
        if hasattr(course, '_filtered_instances'):
            instances_list = course._filtered_instances
        else:
            instances_list = list(course.instances.all())
        
        context['featured_instance'] = instances_list[0] if instances_list else None
        
        # Check if this is a location-specific page (has location filters)
        context['is_location_specific'] = hasattr(course, '_filtered_location') and course._filtered_location is not None
        
        # Group instances by location/city
        instances_by_city = {}
        for instance in instances_list:
            city = instance.location.city
            if city not in instances_by_city:
                instances_by_city[city] = []
            instances_by_city[city].append(instance)
        context['instances_by_city'] = instances_by_city
        
        context['schema_data'] = self.get_schema_data(course)
        context['meta_description'] = course.meta_description or course.short_description
        context['meta_keywords'] = course.meta_keywords or f"{course.category}, {course.level}, photography course"
        
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
        
        if course.image:
            course_schema["image"] = self.request.build_absolute_uri(course.image.url)
        
        instances_list = getattr(course, '_filtered_instances', list(course.instances.all()))
        offers = []
        course_instances_schema = []
        
        for instance in instances_list[:10]:
            instance_schema = {
                "@type": "CourseInstance",
                "courseMode": "onsite",
                "courseWorkload": f"PT{course.duration_hours}H",
                "startDate": instance.start_date.isoformat(),
                "endDate": instance.end_date.isoformat(),
                "location": {
                    "@type": "Place",
                    "name": instance.location.name,
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": instance.location.address_line_1,
                        "addressLocality": instance.location.city,
                        "addressRegion": instance.location.state,
                        "postalCode": instance.location.postal_code,
                        "addressCountry": instance.location.country
                    }
                }
            }
            
            if instance.instructor:
                instance_schema["instructor"] = {
                    "@type": "Person",
                    "name": instance.instructor.user.get_full_name() or instance.instructor.user.username,
                    "description": instance.instructor.bio
                }
            
            course_instances_schema.append(instance_schema)
            
            offer = {
                "@type": "Offer",
                "price": str(instance.price),
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
        queryset = CourseInstance.objects.filter(
            course__is_active=True,
            enrollment_open=True,
            start_date__gte=timezone.now()
        ).select_related('course', 'location', 'location__franchise', 'instructor')
        
        city = request.GET.get('city')
        if city:
            queryset = queryset.filter(location__city__iexact=city)
        
        category = request.GET.get('category')
        if category:
            queryset = queryset.filter(course__category=category)
        
        level = request.GET.get('level')
        if level:
            queryset = queryset.filter(course__level=level)
        
        date_from = request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)
        
        date_to = request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(start_date__lte=date_to)
        
        serializer = CourseInstanceSerializer(queryset[:50], many=True)
        return Response(serializer.data)
