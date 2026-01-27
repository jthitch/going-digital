"""
Course models: Course (abstract definition) and CourseInstance (scheduled).
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from decimal import Decimal
from franchises.models import Location
from core.models import User


class Instructor(models.Model):
    """Instructor for photography courses."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instructor_profile')
    bio = models.TextField()
    photo = models.ImageField(upload_to='instructors/', blank=True, null=True)
    specialties = models.CharField(max_length=255, help_text="Comma-separated list of specialties")
    years_experience = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'instructors'
        ordering = ['user__last_name', 'user__first_name']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"


class Course(models.Model):
    """
    Abstract course definition - reusable across locations and dates.
    Maps to schema.org Course.
    """
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    CATEGORY_CHOICES = [
        ('portrait', 'Portrait Photography'),
        ('landscape', 'Landscape Photography'),
        ('wedding', 'Wedding Photography'),
        ('street', 'Street Photography'),
        ('product', 'Product Photography'),
        ('wildlife', 'Wildlife Photography'),
        ('macro', 'Macro Photography'),
        ('astrophotography', 'Astrophotography'),
        ('general', 'General Photography'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(help_text="Full course description")
    short_description = models.CharField(
        max_length=500,
        help_text="Brief summary for listings"
    )
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    duration_hours = models.PositiveIntegerField(help_text="Course duration in hours")
    max_students = models.PositiveIntegerField(default=12)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Course content
    what_youll_learn = models.JSONField(
        default=list,
        help_text="List of learning outcomes (e.g., ['Learn aperture', 'Understand composition'])"
    )
    audience = models.TextField(help_text="Who this course is for")
    prerequisites = models.TextField(blank=True, help_text="Required knowledge/equipment")
    
    # SEO & Media
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    meta_description = models.CharField(max_length=160, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'courses'
        ordering = ['title']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self, location=None, location_slug=None, postcode=None):
        """Generate SEO-friendly URL for course."""
        if location and location_slug and postcode:
            return reverse('courses:course_detail_by_location', kwargs={
                'location': location.lower().replace(' ', '-'),
                'location_slug': location_slug,
                'postcode': postcode.replace(' ', '').upper(),
                'slug': self.slug
            })
        return reverse('courses:course_detail', kwargs={'slug': self.slug})


class CourseInstance(models.Model):
    """
    Scheduled course instance at a specific location and date.
    Maps to schema.org CourseInstance.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='instances')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='course_instances')
    instructor = models.ForeignKey(
        Instructor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teaching_instances'
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    enrollment_open = models.BooleanField(default=True)
    current_students = models.PositiveIntegerField(default=0)
    
    # Override base course price if needed
    price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Override base course price for this instance"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'course_instances'
        ordering = ['start_date']
        indexes = [
            models.Index(fields=['start_date', 'location']),
            models.Index(fields=['course', 'location']),
        ]
    
    def __str__(self):
        return f"{self.course.title} - {self.location.city} ({self.start_date.strftime('%Y-%m-%d')})"
    
    @property
    def price(self):
        """Return instance price or fall back to course base price."""
        return self.price_override if self.price_override is not None else self.course.price
    
    @property
    def is_full(self):
        """Check if course instance is at capacity."""
        return self.current_students >= self.course.max_students
    
    @property
    def spaces_available(self):
        """Calculate remaining spaces."""
        return max(0, self.course.max_students - self.current_students)
    
    def get_absolute_url(self):
        """Generate URL for this course instance with location, location slug, and postcode."""
        return self.course.get_absolute_url(
            location=self.location.city,
            location_slug=self.location.slug,
            postcode=self.location.postal_code
        )


