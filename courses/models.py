"""
Course models: Course (abstract definition) and Workshop (scheduled - gd_workshop).
Course table matches legacy gd_course structure for DB integration.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from decimal import Decimal
import re

from core.models import User

# Legacy gd_course_category / descriptions sometimes store "Skill level 1", "Level 2", etc.;
# level is already on the card badge.
_CARD_SKILL_LEVEL_REDUNDANT = re.compile(
    r'^\s*(?:skill\s*level\s*\d+|level\s*\d+)\s*$',
    re.I,
)
# Strip leading "Level 2 …" / "Skill level 1 …" from card blurb (same redundancy as badge).
_CARD_LEADING_LEVEL_PREFIX = re.compile(
    r'^\s*(?:skill\s*level\s*\d+|level\s*\d+)\s*[\.:\-–]?\s*',
    re.I,
)


def _safe_datetime_parser(value, expression, connection):
    """Parse datetime, returning None for MySQL '0000-00-00' (year 0)."""
    if value is None:
        return None
    s = str(value).strip()
    if s.startswith('0000-00-00') or s == '':
        return None
    try:
        parsed = parse_datetime(s)
        if parsed is None or parsed.year < 1:
            return None
        return parsed
    except (ValueError, TypeError):
        return None


def _safe_date_parser(value, expression, connection):
    """Parse date, returning None for MySQL '0000-00-00' (year 0)."""
    if value is None:
        return None
    s = str(value).strip()
    if s.startswith('0000-00-00') or s == '':
        return None
    try:
        parsed = parse_date(s)
        if parsed is None or parsed.year < 1:
            return None
        return parsed
    except (ValueError, TypeError):
        return None


class SafeDateTimeField(models.DateTimeField):
    """
    DateTimeField that tolerates MySQL '0000-00-00 00:00:00' (year 0) - returns None.
    Uses get_db_converters for the MySQL backend.
    """
    def get_db_converters(self, connection):
        return [_safe_datetime_parser]


class SafeDateField(models.DateField):
    """
    DateField that tolerates MySQL '0000-00-00' (year 0) - returns None.
    """
    def get_db_converters(self, connection):
        return [_safe_date_parser]


# Legacy skill level ID mapping (gd_course.course_skill_level_id)
# Order: 1=Beginner, 2=Intermediate, 3=Advanced, 4=Masterclass, 5=Various
SKILL_LEVEL_IDS = {1: 'Beginner', 2: 'Intermediate', 3: 'Advanced', 4: 'Masterclass', 5: 'Various'}
LEVEL_DISPLAY_NAMES = {1: 'Beginner', 2: 'Intermediate', 3: 'Advanced', 4: 'Masterclass', 5: 'Various'}
# Reverse map for filtering (level name -> legacy id)
LEVEL_NAME_TO_ID = {'beginner': 1, 'intermediate': 2, 'advanced': 3, 'masterclass': 4, 'various': 5}
# Level id -> slug (for data-level attribute, matches homepage CSS)
LEVEL_ID_TO_SLUG = {1: 'beginner', 2: 'intermediate', 3: 'advanced', 4: 'masterclass', 5: 'various'}
# Legacy category ID mapping (gd_course.course_category_id) - used when filtering by slug
CATEGORY_IDS = {
    'portrait': 1, 'landscape': 2, 'wedding': 3, 'street': 4, 'product': 5,
    'wildlife': 6, 'macro': 7, 'astrophotography': 8, 'general': 9,
}
# Legacy gd_course.status_id (also used on gd_page, gd_venue, gd_region)
COURSE_STATUS_DISPLAY_NAMES = {1: 'Published', 2: 'Unpublished'}
COURSE_STATUS_CHOICES = tuple(COURSE_STATUS_DISPLAY_NAMES.items())


class CourseCategory(models.Model):
    """
    Course category - maps to legacy table gd_course_category.
    Referenced by gd_course.course_category_id.
    """
    id = models.AutoField(primary_key=True, db_column='id')  # legacy int(11) AUTO_INCREMENT
    active = models.IntegerField(default=1, db_column='active')  # int(1) in legacy
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children', db_column='parent_id'
    )
    exclude_from_course_list = models.SmallIntegerField(default=0, db_column='exclude_from_course_list')
    course_category = models.CharField(max_length=255, default='', db_column='course_category')
    display_order = models.IntegerField(default=99, db_column='display_order')
    createdby_id = models.IntegerField(null=True, blank=True, db_column='createdby_id')
    updatedby_id = models.IntegerField(null=True, blank=True, db_column='updatedby_id')
    created_at = models.DateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='updated_at')

    class Meta:
        db_table = 'gd_course_category'
        ordering = ['display_order', 'course_category']
        verbose_name = 'Course category'
        verbose_name_plural = 'Course categories'

    def __str__(self):
        return self.course_category or ''


class CourseSkillLevel(models.Model):
    """
    Course skill level - maps to legacy table gd_course_skill_level.
    Referenced by gd_course.course_skill_level_id.
    """
    id = models.AutoField(primary_key=True, db_column='id')
    active = models.IntegerField(default=1, db_column='active')
    skill_level = models.CharField(max_length=255, default='', db_column='skill_level')
    display_order = models.IntegerField(default=0, db_column='display_order')
    createdby_id = models.IntegerField(null=True, blank=True, db_column='createdby_id')
    updatedby_id = models.IntegerField(null=True, blank=True, db_column='updatedby_id')
    created_at = models.DateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='updated_at')

    class Meta:
        db_table = 'gd_course_skill_level'
        ordering = ['display_order', 'skill_level']
        verbose_name = 'Course skill level'
        verbose_name_plural = 'Course skill levels'

    def __str__(self):
        """Prefer legacy ID labels (Beginner, Intermediate, …) over numeric skill_level values."""
        return LEVEL_DISPLAY_NAMES.get(self.pk) or self.skill_level or ''


class Region(models.Model):
    """
    Franchise region - maps to legacy table gd_region.
    Referenced by gd_course.region_id (integer FK, not a DB constraint).
    """
    id = models.AutoField(primary_key=True, db_column='id')
    active = models.SmallIntegerField(default=1, db_column='active')
    region_name = models.CharField(max_length=255, default='', db_column='region_name')
    slug = models.CharField(max_length=255, default='', db_column='slug')

    class Meta:
        db_table = 'gd_region'
        managed = False
        ordering = ['region_name']
        verbose_name = 'Region'
        verbose_name_plural = 'Regions'

    def __str__(self):
        return self.region_name or ''


class RegionUser(models.Model):
    """
    Legacy user–region assignments (gd_region_user).
    Franchisees may be linked to multiple regions.
    """
    id = models.AutoField(primary_key=True, db_column='id')
    region_id = models.IntegerField(db_column='region_id')
    user_id = models.IntegerField(db_column='user_id')
    createdby_id = models.IntegerField(null=True, blank=True, db_column='createdby_id')
    updatedby_id = models.IntegerField(null=True, blank=True, db_column='updatedby_id')
    created_at = models.DateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='updated_at')

    class Meta:
        db_table = 'gd_region_user'
        managed = False
        verbose_name = 'Region user'
        verbose_name_plural = 'Region users'

    def __str__(self):
        return f'user_id={self.user_id} region_id={self.region_id}'


class County(models.Model):
    """
    County - maps to legacy table gd_county.
    Referenced by gd_venue.county_id (integer FK, not a DB constraint).
    """
    id = models.AutoField(primary_key=True, db_column='id')
    active = models.SmallIntegerField(default=1, db_column='active')
    county = models.CharField(max_length=255, db_column='county')

    class Meta:
        db_table = 'gd_county'
        managed = False
        ordering = ['county']
        verbose_name = 'County'
        verbose_name_plural = 'Counties'

    def __str__(self):
        return self.county or f'County #{self.id}'


class Tutor(models.Model):
    """
    Workshop tutor - maps to legacy table gd_tutor.
    Referenced by gd_workshop.tutor_id (integer FK, not a DB constraint).
    """
    id = models.AutoField(primary_key=True, db_column='id')
    active = models.SmallIntegerField(default=1, db_column='active')
    firstname = models.CharField(max_length=255, default='', db_column='firstname')
    lastname = models.CharField(max_length=255, default='', db_column='lastname')
    email = models.CharField(max_length=255, null=True, blank=True, db_column='email')

    class Meta:
        db_table = 'gd_tutor'
        managed = False
        ordering = ['lastname', 'firstname']
        verbose_name = 'Tutor'
        verbose_name_plural = 'Tutors'

    def __str__(self):
        name = f'{self.firstname} {self.lastname}'.strip()
        return name or f'Tutor #{self.id}'


class Assistant(models.Model):
    """
    Workshop assistant - maps to legacy table gd_assistant.
    Referenced by gd_workshop.assistant_id (integer FK, not a DB constraint).
    """
    id = models.AutoField(primary_key=True, db_column='id')
    active = models.SmallIntegerField(default=1, db_column='active')
    firstname = models.CharField(max_length=255, default='', db_column='firstname')
    lastname = models.CharField(max_length=255, default='', db_column='lastname')
    email = models.CharField(max_length=255, null=True, blank=True, db_column='email')

    class Meta:
        db_table = 'gd_assistant'
        managed = False
        ordering = ['lastname', 'firstname']
        verbose_name = 'Assistant'
        verbose_name_plural = 'Assistants'

    def __str__(self):
        name = f'{self.firstname} {self.lastname}'.strip()
        return name or f'Assistant #{self.id}'


class WorkshopType(models.Model):
    """
    Workshop type - maps to legacy table gd_workshop_type.
    Referenced by gd_workshop.workshop_type_id.
    """
    id = models.AutoField(primary_key=True, db_column='id')
    workshop_type = models.CharField(max_length=255, db_column='workshop_type')
    display_on_site = models.SmallIntegerField(default=1, db_column='display_on_site')

    class Meta:
        db_table = 'gd_workshop_type'
        managed = False
        ordering = ['workshop_type']
        verbose_name = 'Workshop type'
        verbose_name_plural = 'Workshop types'

    def __str__(self):
        return self.workshop_type or ''


class Content(models.Model):
    """
    Page/content block - maps to legacy table gd_content.
    Referenced by gd_course.content_id and gd_venue.content_id (page content, meta, etc.).
    """
    id = models.AutoField(primary_key=True, db_column='id')
    content_type_id = models.IntegerField(null=True, blank=True, db_column='content_type_id')
    content_master_ref_id = models.IntegerField(null=True, blank=True, db_column='content_master_ref_id')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children', db_column='parent_id'
    )
    active = models.SmallIntegerField(default=1, db_column='active')  # tinyint(1)
    exclude_from_search = models.SmallIntegerField(default=0, db_column='exclude_from_search')
    requests = models.IntegerField(default=0, db_column='requests')
    header_image_type = models.SmallIntegerField(default=1, db_column='header_image_type')
    PageTitleX = models.CharField(max_length=1000, null=True, blank=True, db_column='PageTitleX')
    content_title = models.CharField(max_length=1000, null=True, blank=True, db_column='content_title')
    header_image_id = models.IntegerField(null=True, blank=True, db_column='header_image_id')
    header_content = models.TextField(null=True, blank=True, db_column='header_content')
    strapline = models.TextField(null=True, blank=True, db_column='strapline')
    main_content = models.TextField(null=True, blank=True, db_column='main_content')
    sub_content = models.TextField(null=True, blank=True, db_column='sub_content')
    side_content = models.TextField(null=True, blank=True, db_column='side_content')
    footer_content = models.TextField(null=True, blank=True, db_column='footer_content')
    youtube_code = models.CharField(max_length=255, null=True, blank=True, db_column='youtube_code')
    meta_image_id = models.IntegerField(null=True, blank=True, db_column='meta_image_id')
    meta_title = models.TextField(null=True, blank=True, db_column='meta_title')
    meta_description = models.TextField(null=True, blank=True, db_column='meta_description')
    meta_keywords = models.TextField(null=True, blank=True, db_column='meta_keywords')
    social_title = models.TextField(null=True, blank=True, db_column='social_title')
    search_keywords = models.TextField(null=True, blank=True, db_column='search_keywords')
    change_frequency_id = models.IntegerField(default=3, db_column='change_frequency_id')
    createdby_id = models.IntegerField(null=True, blank=True, db_column='createdby_id')
    updatedby_id = models.IntegerField(null=True, blank=True, db_column='updatedby_id')
    created_at = models.DateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='updated_at')
    date_last_viewed = models.DateTimeField(null=True, blank=True, db_column='date_last_viewed')
    video_url = models.CharField(max_length=200, null=True, blank=True, db_column='video_url')
    video_inline = models.IntegerField(null=True, blank=True, db_column='video_inline')
    video_image_id = models.IntegerField(null=True, blank=True, db_column='video_image_id')

    class Meta:
        db_table = 'gd_content'
        ordering = ['id']
        verbose_name = 'Content'
        verbose_name_plural = 'Content'

    def __str__(self):
        return self.content_title or f'Content #{self.id}'


class ImageCategory(models.Model):
    """
    Image category - maps to legacy table gd_image_category.
    Referenced by gd_image.image_category_id (integer FK, not a DB constraint).
    """
    id = models.AutoField(primary_key=True, db_column='id')
    image_type_id = models.IntegerField(null=True, blank=True, db_column='image_type_id')
    category = models.CharField(max_length=255, db_column='category')

    class Meta:
        db_table = 'gd_image_category'
        managed = False
        ordering = ['category']
        verbose_name = 'Image category'
        verbose_name_plural = 'Image categories'

    def __str__(self):
        return self.category or f'Category #{self.id}'


class ImageType(models.Model):
    """
    Image type - maps to legacy table gd_image_type.
    Referenced by gd_image.image_type_id (integer FK, not a DB constraint).
    """
    id = models.AutoField(primary_key=True, db_column='id')
    active = models.SmallIntegerField(default=1, db_column='active')
    image_type = models.CharField(max_length=255, db_column='image_type')

    class Meta:
        db_table = 'gd_image_type'
        managed = False
        ordering = ['image_type']
        verbose_name = 'Image type'
        verbose_name_plural = 'Image types'

    def __str__(self):
        return self.image_type or ''


class Image(models.Model):
    """
    Image record - maps to legacy table gd_image.
    Referenced by gd_course.image_id (course image).
    Stores file metadata; file_name is the stored filename.
    """
    id = models.AutoField(primary_key=True, db_column='id')
    image_type_id = models.IntegerField(
        null=True, blank=True, db_column='image_type_id', verbose_name='Image type',
    )
    link_to = models.CharField(max_length=200, null=True, blank=True, db_column='link_to')
    image_category_id = models.IntegerField(
        null=True, blank=True, db_column='image_category_id', verbose_name='Image category',
    )
    active = models.SmallIntegerField(default=1, db_column='active')
    user_id = models.IntegerField(null=True, blank=True, db_column='user_id', verbose_name='User')
    source_name = models.CharField(max_length=1000, null=True, blank=True, db_column='source_name')
    file_name = models.CharField(max_length=1000, db_column='file_name')
    description = models.CharField(max_length=1000, null=True, blank=True, db_column='description')
    mime_type = models.CharField(max_length=20, db_column='mime_type')
    file_size = models.IntegerField(db_column='file_size')
    height = models.IntegerField(null=True, blank=True, db_column='height')
    width = models.IntegerField(null=True, blank=True, db_column='width')
    checksum = models.CharField(max_length=255, null=True, blank=True, db_column='checksum')
    createdby_id = models.IntegerField(null=True, blank=True, db_column='createdby_id')
    updatedby_id = models.IntegerField(null=True, blank=True, db_column='updatedby_id')
    created_at = models.DateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='updated_at')
    converted = models.IntegerField(default=0, db_column='converted')

    class Meta:
        db_table = 'gd_image'
        ordering = ['id']
        verbose_name = 'Image'
        verbose_name_plural = 'Images'

    def __str__(self):
        return self.file_name or self.source_name or f'Image #{self.id}'

    def get_image_type_display(self):
        """Return image type name from gd_image_type, or empty if unset."""
        if not self.image_type_id:
            return '—'
        try:
            return str(ImageType.objects.get(pk=self.image_type_id))
        except ImageType.DoesNotExist:
            return f'Type #{self.image_type_id}'

    get_image_type_display.short_description = 'Image type'
    get_image_type_display.admin_order_field = 'image_type_id'

    def get_image_category_display(self):
        """Return image category name from gd_image_category, or empty if unset."""
        if not self.image_category_id:
            return '—'
        try:
            return str(ImageCategory.objects.get(pk=self.image_category_id))
        except ImageCategory.DoesNotExist:
            return f'Category #{self.image_category_id}'

    get_image_category_display.short_description = 'Image category'
    get_image_category_display.admin_order_field = 'image_category_id'

    def get_user_display(self):
        """Return gd_user name for image.user_id."""
        if not self.user_id:
            return '—'
        try:
            user = User.objects.get(pk=self.user_id)
            return user.get_full_name() or user.email or f'User #{self.user_id}'
        except User.DoesNotExist:
            return f'User #{self.user_id}'

    get_user_display.short_description = 'User'
    get_user_display.admin_order_field = 'user_id'

    @property
    def url(self):
        """Build URL for schema/templates; adjust path to match your media setup."""
        if not self.file_name:
            return ''
        from django.conf import settings
        base = getattr(settings, 'GD_IMAGE_MEDIA_PREFIX', '/media/gd_images/')
        return f"{base.rstrip('/')}/{self.file_name}"


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
        ordering = ['user__lastname', 'user__firstname']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email}"


class Venue(models.Model):
    """
    Legacy venue - maps to gd_venue.
    Used by Workshop for location/venue display.
    """
    id = models.AutoField(primary_key=True, db_column='id')
    active = models.SmallIntegerField(default=1, db_column='active')
    status_id = models.SmallIntegerField(default=2, db_column='status_id', verbose_name='Status')
    region_id = models.IntegerField(null=True, blank=True, db_column='region_id', verbose_name='Region')
    user_id = models.IntegerField(null=True, blank=True, db_column='user_id', verbose_name='User')
    content_id = models.IntegerField(
        null=True, blank=True, db_column='content_id',
        verbose_name='Content',
        help_text='Legacy FK to gd_content.id',
    )
    county_id = models.IntegerField(null=True, blank=True, db_column='county_id', verbose_name='County')
    venue_name = models.CharField(max_length=255, default='', db_column='venue_name')
    location = models.CharField(max_length=255, null=True, blank=True, db_column='location')
    slug = models.CharField(max_length=255, default='', db_column='slug')
    venue_address = models.TextField(null=True, blank=True, db_column='venue_address')
    venue_telephone = models.CharField(max_length=255, null=True, blank=True, db_column='venue_telephone')
    venue_url = models.TextField(null=True, blank=True, db_column='venue_url')
    latitude = models.FloatField(null=True, blank=True, db_column='latitude')
    longitude = models.FloatField(null=True, blank=True, db_column='longitude')
    show_workshops = models.SmallIntegerField(default=1, db_column='show_workshops')
    approval_requested = models.SmallIntegerField(default=0, db_column='approval_requested')
    approved = models.SmallIntegerField(default=0, db_column='approved')
    rejected = models.SmallIntegerField(default=0, db_column='rejected')
    reject_reason = models.TextField(null=True, blank=True, db_column='reject_reason')
    approval_requested_by_id = models.IntegerField(
        null=True, blank=True, db_column='approval_requested_by_id',
    )
    approval_requested_at = SafeDateTimeField(null=True, blank=True, db_column='approval_requested_at')
    approvedby_id = models.IntegerField(null=True, blank=True, db_column='approvedby_id')
    approved_at = SafeDateTimeField(null=True, blank=True, db_column='approved_at')
    createdby_id = models.IntegerField(null=True, blank=True, db_column='createdby_id')
    updatedby_id = models.IntegerField(null=True, blank=True, db_column='updatedby_id')
    created_at = SafeDateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = SafeDateTimeField(null=True, blank=True, db_column='updated_at')

    class Meta:
        db_table = 'gd_venue'
        managed = False
        ordering = ['venue_name']
        verbose_name = 'Venue'
        verbose_name_plural = 'Venues'

    def __str__(self):
        return self.venue_name or f'Venue #{self.id}'

    @property
    def is_approved(self):
        return self.approved == 1

    @property
    def is_pending_approval(self):
        return self.approval_requested == 1 and self.approved != 1 and self.rejected != 1

    def get_approval_display(self):
        if self.approved == 1:
            return 'Approved'
        if self.rejected == 1:
            return 'Rejected'
        if self.approval_requested == 1:
            return 'Pending approval'
        return 'Not submitted'

    get_approval_display.short_description = 'Approval'

    @property
    def city(self):
        """City-like display from location or venue_address."""
        return self.location or (self.venue_address[:50] + '...' if self.venue_address and len(self.venue_address) > 50 else self.venue_address or '')

    @property
    def name(self):
        return self.venue_name or ''

    @property
    def is_active(self):
        """Compatibility: gd_venue uses 'active' (0/1), expose as is_active."""
        return self.active == 1

    def get_region_display(self):
        if not self.region_id:
            return '—'
        try:
            return Region.objects.get(pk=self.region_id).region_name
        except Region.DoesNotExist:
            return f'Region #{self.region_id}'

    get_region_display.short_description = 'Region'
    get_region_display.admin_order_field = 'region_id'

    def get_status_display(self):
        return COURSE_STATUS_DISPLAY_NAMES.get(self.status_id, f'Status #{self.status_id}')

    get_status_display.short_description = 'Status'
    get_status_display.admin_order_field = 'status_id'

    def get_user_display(self):
        if not self.user_id:
            return '—'
        try:
            user = User.objects.get(pk=self.user_id)
            return user.get_full_name() or user.email or f'User #{self.user_id}'
        except User.DoesNotExist:
            return f'User #{self.user_id}'

    get_user_display.short_description = 'User'
    get_user_display.admin_order_field = 'user_id'

    def get_county_display(self):
        if not self.county_id:
            return '—'
        try:
            return str(County.objects.get(pk=self.county_id))
        except County.DoesNotExist:
            return f'County #{self.county_id}'

    get_county_display.short_description = 'County'
    get_county_display.admin_order_field = 'county_id'

    def get_content(self):
        """Return linked gd_content row, or None."""
        if not self.content_id:
            return None
        try:
            return Content.objects.get(pk=self.content_id)
        except Content.DoesNotExist:
            return None


class VenueContent(models.Model):
    """
    Optional content block for a venue page.
    Managed via admin - description, meta fields, etc.
    """
    venue = models.OneToOneField(
        Venue,
        on_delete=models.CASCADE,
        related_name='content_block',
        primary_key=True,
    )
    description = models.TextField(blank=True, help_text='Main description for the venue page')
    meta_title = models.CharField(max_length=255, blank=True, help_text='SEO title (optional)')
    meta_description = models.TextField(max_length=500, blank=True, help_text='SEO description (optional)')

    class Meta:
        verbose_name = 'Venue content'
        verbose_name_plural = 'Venue contents'

    def __str__(self):
        return f"Content for {self.venue.venue_name}"


class VenueMedia(models.Model):
    """
    Images for a venue - managed via admin.
    """
    venue = models.ForeignKey(
        Venue,
        on_delete=models.CASCADE,
        related_name='media',
    )
    image = models.ImageField(upload_to='venues/images/', blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'Venue image'
        verbose_name_plural = 'Venue images'

    def __str__(self):
        return self.caption or f"Image for {self.venue.venue_name}"


class Workshop(models.Model):
    """
    Scheduled workshop - maps to legacy gd_workshop.
    Replaces CourseInstance for workshop/instance display.
    """
    id = models.AutoField(primary_key=True, db_column='id')
    region_id = models.IntegerField(null=True, blank=True, db_column='region_id')
    user_id = models.IntegerField(null=True, blank=True, db_column='user_id')
    course = models.ForeignKey(
        'Course',
        on_delete=models.CASCADE,
        related_name='workshops',
        null=True,
        blank=True,
        db_column='course_id'
    )
    alt_course_id = models.IntegerField(default=0, db_column='alt_course_id')
    tutor_id = models.IntegerField(null=True, blank=True, db_column='tutor_id')
    assistant_id = models.IntegerField(null=True, blank=True, db_column='assistant_id')
    venue = models.ForeignKey(
        Venue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workshops',
        db_column='venue_id'
    )
    workshop_type_id = models.IntegerField(null=True, blank=True, db_column='workshop_type_id')
    cameras_available = models.SmallIntegerField(default=0, db_column='cameras_available')
    number_of_loan_cameras_available = models.IntegerField(default=0, db_column='number_of_loan_cameras_available')
    sticky = models.SmallIntegerField(default=0, db_column='sticky')
    active = models.SmallIntegerField(db_column='active')
    checksum = models.CharField(max_length=32, null=True, blank=True, db_column='checksum')
    date = SafeDateTimeField(null=True, blank=True, db_column='date')
    cost = models.IntegerField(default=0, db_column='cost')
    deposit_required = models.IntegerField(default=0, db_column='deposit_required')
    max_places = models.IntegerField(null=True, blank=True, db_column='max_places')
    places_booked = models.IntegerField(null=True, blank=True, db_column='places_booked')
    strapline = models.TextField(null=True, blank=True, db_column='strapline')
    byline = models.TextField(null=True, blank=True, db_column='byline')
    comments = models.TextField(null=True, blank=True, db_column='comments')
    reminder_message = models.TextField(null=True, blank=True, db_column='reminder_message')
    approve = models.SmallIntegerField(default=1, db_column='approve')
    blurb = models.CharField(max_length=500, null=True, blank=True, db_column='blurb')
    cloned_from_workshop_id = models.IntegerField(null=True, blank=True, db_column='cloned_from_workshop_id')
    createdby_id = models.IntegerField(null=True, blank=True, db_column='createdby_id')
    updatedby_id = models.IntegerField(null=True, blank=True, db_column='updatedby_id')
    created_at = SafeDateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = SafeDateTimeField(null=True, blank=True, db_column='updated_at')
    image_id = models.IntegerField(default=0, db_column='image_id')

    class Meta:
        db_table = 'gd_workshop'
        managed = False
        ordering = ['date']
        verbose_name = 'Workshop'
        verbose_name_plural = 'Workshops'

    def __str__(self):
        venue_name = self.venue.name if self.venue else 'Unknown'
        return f"{self.course.title if self.course else 'Workshop'} - {venue_name} ({self.date.strftime('%d %B %Y') if self.date else '?'})"

    def get_region_display(self):
        """Return region name from gd_region, or empty if unset."""
        if not self.region_id:
            return ''
        try:
            return Region.objects.get(pk=self.region_id).region_name
        except Region.DoesNotExist:
            return f'Region #{self.region_id}'

    def get_tutor_display(self):
        """Return tutor name from gd_tutor, or empty if unset."""
        if not self.tutor_id:
            return '—'
        try:
            return str(Tutor.objects.get(pk=self.tutor_id))
        except Tutor.DoesNotExist:
            return f'Tutor #{self.tutor_id}'

    get_tutor_display.short_description = 'Tutor'
    get_tutor_display.admin_order_field = 'tutor_id'

    def get_assistant_display(self):
        """Return assistant name from gd_assistant, or empty if unset."""
        if not self.assistant_id:
            return '—'
        try:
            return str(Assistant.objects.get(pk=self.assistant_id))
        except Assistant.DoesNotExist:
            return f'Assistant #{self.assistant_id}'

    get_assistant_display.short_description = 'Assistant'
    get_assistant_display.admin_order_field = 'assistant_id'

    def _user_name(self, user_id):
        if not user_id:
            return '—'
        try:
            user = User.objects.get(pk=user_id)
            return user.get_full_name() or user.email or f'User #{user_id}'
        except User.DoesNotExist:
            return f'User #{user_id}'

    def get_user_display(self):
        """Return gd_user name for workshop.user_id."""
        return self._user_name(self.user_id)

    def get_createdby_display(self):
        return self._user_name(self.createdby_id)

    def get_updatedby_display(self):
        return self._user_name(self.updatedby_id)

    # Compatibility properties for code expecting CourseInstance-like API
    @property
    def start_date(self):
        return self.date

    @property
    def end_date(self):
        """Assume 6-hour workshop if no end time stored."""
        if self.date:
            from datetime import timedelta
            return self.date + timedelta(hours=6)
        return None

    @property
    def enrollment_open(self):
        return bool(self.active)

    @property
    def current_students(self):
        return self.places_booked or 0

    @property
    def price(self):
        return Decimal(str(self.cost or 0))

    @property
    def is_full(self):
        max_p = self.max_places or 0
        booked = self.places_booked or 0
        return max_p > 0 and booked >= max_p

    @property
    def spaces_available(self):
        max_p = self.max_places or 0
        booked = self.places_booked or 0
        return max(0, max_p - booked)

    @property
    def location(self):
        """Compatibility: return venue as location-like object (has .name, .city)."""
        return self.venue

    def get_absolute_url(self):
        """URL for workshop - course detail with venue slug if available."""
        if self.course and self.course.slug:
            if self.venue and self.venue.slug:
                return reverse('courses:course_detail_by_location', kwargs={
                    'slug': self.course.slug,
                    'location_slug': self.venue.slug,
                })
            return reverse('courses:course_detail', kwargs={'slug': self.course.slug})
        return reverse('courses:course_list')


class Course(models.Model):
    """
    Course definition - maps to legacy table gd_course for DB integration.
    Use compatibility properties (title, description, is_active, etc.) in app code.
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
    # Legacy gd_course columns (exact names via db_column)
    CID = models.IntegerField(null=True, blank=True, db_column='CID')  # Data mining field
    active = models.BooleanField(default=True, db_column='active')
    status_id = models.SmallIntegerField(default=2, db_column='status_id')
    clickable = models.BooleanField(default=False, db_column='clickable')
    course_category = models.ForeignKey(
        CourseCategory, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='courses', db_column='course_category_id'
    )
    course_skill_level = models.ForeignKey(
        CourseSkillLevel, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='courses', db_column='course_skill_level_id'
    )
    content = models.ForeignKey(
        Content, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='courses', db_column='content_id'
    )
    image = models.ForeignKey(
        Image, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='courses', db_column='image_id'
    )
    region_id = models.IntegerField(null=True, blank=True, db_column='region_id')
    is_one_to_one = models.SmallIntegerField(default=0, db_column='is_one_to_one')
    show_workshops = models.BooleanField(default=True, db_column='show_workshops')
    display_order = models.IntegerField(default=99, db_column='display_order')
    use_on_filter = models.BooleanField(default=True, db_column='use_on_filter')
    course_name = models.CharField(max_length=255, db_column='course_name')
    course_abbr = models.CharField(max_length=16, null=True, blank=True, db_column='course_abbr')
    course_description = models.TextField(null=True, blank=True, db_column='course_description')
    description_for_workshop = models.TextField(null=True, blank=True, db_column='description_for_workshop')
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True, db_column='slug')
    link_name = models.CharField(max_length=255, null=True, blank=True, db_column='link_name')
    link_title = models.CharField(max_length=255, null=True, blank=True, db_column='link_title')
    filter_name = models.CharField(max_length=255, null=True, blank=True, db_column='filter_name')
    page_title = models.CharField(max_length=1000, null=True, blank=True, db_column='page_title')
    createdby_id = models.IntegerField(null=True, blank=True, db_column='createdby_id')
    updatedby_id = models.IntegerField(null=True, blank=True, db_column='updatedby_id')
    created_at = models.DateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='updated_at')
    workshop_image_id = models.IntegerField(default=0, db_column='workshop_image_id')

    class Meta:
        db_table = 'gd_course'
        ordering = ['display_order', 'course_name']
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'

    def save(self, *args, **kwargs):
        if self.created_at is None:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    # --- Compatibility properties for existing app code (map to gd_course columns) ---
    @property
    def title(self):
        return self.course_name or ''

    @property
    def short_description(self):
        return (self.course_description or '')[:500]

    @property
    def description(self):
        return self.description_for_workshop or self.course_description or ''

    @property
    def is_active(self):
        return self.active

    # Level: slug for CSS (beginner, intermediate, etc.) - matches homepage level colors
    @property
    def level(self):
        return LEVEL_ID_TO_SLUG.get(self.course_skill_level_id, 'various')

    def get_level_display(self):
        """Return display name: Beginner, Intermediate, Advanced, Masterclass, Various."""
        return LEVEL_DISPLAY_NAMES.get(self.course_skill_level_id, 'Various')

    def get_region_display(self):
        """Return region name from gd_region, or empty if unset."""
        if not self.region_id:
            return ''
        try:
            return Region.objects.get(pk=self.region_id).region_name
        except Region.DoesNotExist:
            return f'Region #{self.region_id}'

    def get_status_display(self):
        """Return legacy status label for gd_course.status_id."""
        return COURSE_STATUS_DISPLAY_NAMES.get(self.status_id, f'Status #{self.status_id}')

    @property
    def category(self):
        try:
            if self.course_category_id and self.course_category:
                return self.course_category.course_category or 'general'
        except CourseCategory.DoesNotExist:
            pass
        return 'general'

    def get_category_display(self):
        try:
            if self.course_category_id and self.course_category:
                return self.course_category.course_category or 'General Photography'
        except CourseCategory.DoesNotExist:
            pass
        return 'General Photography'

    def get_card_category_display(self):
        """Category label for list/map cards; omit duplicate of skill level (badge shows level)."""
        label = (self.get_category_display() or '').strip()
        if not label:
            return ''
        if _CARD_SKILL_LEVEL_REDUNDANT.match(label):
            return ''
        label = _CARD_LEADING_LEVEL_PREFIX.sub('', label).strip().lstrip('.,-– ')
        if not label or _CARD_SKILL_LEVEL_REDUNDANT.match(label):
            return ''
        return label

    def get_card_short_description(self):
        """Summary for list cards; omit when course_description is only skill-level noise (badge shows level)."""
        text = (self.course_description or '').strip()
        if not text:
            return ''
        if _CARD_SKILL_LEVEL_REDUNDANT.match(text):
            return ''
        text = _CARD_LEADING_LEVEL_PREFIX.sub('', text).strip()
        if not text or _CARD_SKILL_LEVEL_REDUNDANT.match(text):
            return ''
        return text[:500]

    @property
    def instances(self):
        """Alias for legacy related_name `instances` (CourseInstance); use workshops."""
        return self.workshops

    # Not in gd_course; calculated from workshops when available
    @property
    def duration_hours(self):
        """Calculate duration in hours from first workshop's start/end times."""
        workshop = self.workshops.order_by('date').first()
        if workshop and workshop.start_date and workshop.end_date:
            delta = workshop.end_date - workshop.start_date
            hours = delta.total_seconds() / 3600
            hours = max(0, round(hours, 1))
            return int(hours) if hours == int(hours) else hours
        return 0

    @property
    def max_students(self):
        return 12

    @property
    def price(self):
        return Decimal('0.00')

    @property
    def min_price(self):
        """Minimum price from workshops (for list/detail display)."""
        workshops = self.workshops.all()[:50]  # Limit for performance
        prices = [w.price for w in workshops if w.price is not None]
        return min(prices) if prices else Decimal('0.00')

    @property
    def what_youll_learn(self):
        return []

    @property
    def audience(self):
        return ''

    @property
    def prerequisites(self):
        return ''

    @property
    def meta_title(self):
        """Page/meta title from Content or gd_course.page_title."""
        try:
            if self.content_id and self.content and self.content.meta_title:
                return (self.content.meta_title or '').strip() or None
        except Content.DoesNotExist:
            pass
        return (self.page_title or '').strip() or None

    @property
    def meta_description(self):
        try:
            if self.content_id and self.content and self.content.meta_description:
                return (self.content.meta_description or '')[:160]
        except Content.DoesNotExist:
            pass
        return (self.page_title or self.course_description or '')[:160]

    @property
    def meta_keywords(self):
        try:
            if self.content_id and self.content and self.content.meta_keywords:
                return (self.content.meta_keywords or '')[:255]
        except Content.DoesNotExist:
            pass
        return (self.filter_name or '')[:255]

    def __str__(self):
        return self.title

    @property
    def first_uploaded_image(self):
        """First uploaded image from CourseMedia (for hero when gd_image not set)."""
        for m in self.media.all():
            if m.media_type == 'image' and m.image:
                return m
        return None

    def get_absolute_url(self, location=None, location_slug=None):
        """Generate SEO-friendly URL: /photography-courses/<course-slug>/<location-slug>/ or overview."""
        if not self.slug:
            return reverse('courses:course_list')
        if location_slug:
            return reverse('courses:course_detail_by_location', kwargs={
                'slug': self.slug,
                'location_slug': location_slug,
            })
        return reverse('courses:course_detail', kwargs={'slug': self.slug})


class CourseMedia(models.Model):
    """
    Uploaded images and videos for a course.
    Managed via Course admin inline.
    """
    MEDIA_TYPE_IMAGE = 'image'
    MEDIA_TYPE_VIDEO = 'video'
    MEDIA_TYPE_CHOICES = [
        (MEDIA_TYPE_IMAGE, 'Image'),
        (MEDIA_TYPE_VIDEO, 'Video'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default=MEDIA_TYPE_IMAGE)
    image = models.ImageField(upload_to='courses/images/', blank=True, null=True)
    video_file = models.FileField(
        upload_to='courses/videos/',
        blank=True,
        null=True,
        help_text='Upload a video file (mp4, webm, etc.)'
    )
    video_url = models.URLField(
        blank=True,
        null=True,
        help_text='Or paste a YouTube/Vimeo URL'
    )
    caption = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'Course media'
        verbose_name_plural = 'Course media'

    def __str__(self):
        if self.media_type == self.MEDIA_TYPE_IMAGE and self.image:
            return f"Image: {self.image.name}"
        if self.media_type == self.MEDIA_TYPE_VIDEO:
            return f"Video: {self.video_url or self.video_file.name or '—'}"
        return f"Course media #{self.id}"

    @property
    def video_embed_url(self):
        """Convert YouTube/Vimeo URL to embed URL."""
        if not self.video_url:
            return None
        url = self.video_url.strip()
        # YouTube: https://www.youtube.com/watch?v=VIDEO_ID -> https://www.youtube.com/embed/VIDEO_ID
        if 'youtube.com/watch' in url:
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(url)
            return f"https://www.youtube.com/embed/{parse_qs(parsed.query).get('v', [None])[0]}"
        if 'youtu.be/' in url:
            return f"https://www.youtube.com/embed/{url.split('youtu.be/')[-1].split('?')[0]}"
        # Vimeo: https://vimeo.com/123 -> https://player.vimeo.com/video/123
        if 'vimeo.com/' in url:
            vid = url.rstrip('/').split('/')[-1]
            return f"https://player.vimeo.com/video/{vid}"
        return url


