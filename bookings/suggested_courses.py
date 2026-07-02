"""Suggested courses for students based on existing bookings."""
from django.db.models import Prefetch, Q
from django.utils import timezone

from courses.models import Course, Workshop

VARIOUS_LEVEL_ID = 5


def _booking_region_id(booking):
    workshop = booking.workshop
    if not workshop:
        return None
    course = workshop.course
    venue = workshop.venue
    for rid in (
        workshop.region_id,
        course.region_id if course else None,
        venue.region_id if venue else None,
    ):
        if rid:
            return rid
    return None


def _normalize_dt(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def suggested_courses_for_user_bookings(bookings, *, limit=6):
    """
    Courses in the same region as any booking, same skill level or higher,
    with a workshop date after the user's latest booked course, excluding
    courses already booked.
    """
    eligible = [
        b for b in bookings
        if b.status != 'cancelled' and getattr(b, 'workshop', None) and b.workshop
    ]
    if not eligible:
        return []

    booked_course_ids = set()
    region_ids = set()
    level_ids = []
    latest_booked_date = None

    for booking in eligible:
        workshop = booking.workshop
        course = workshop.course
        if course:
            booked_course_ids.add(course.pk)
            level_id = course.course_skill_level_id
            if level_id and level_id != VARIOUS_LEVEL_ID:
                level_ids.append(level_id)

        rid = _booking_region_id(booking)
        if rid:
            region_ids.add(rid)

        if workshop.open_dated:
            continue
        start = _normalize_dt(workshop.start_date)
        if start and (latest_booked_date is None or start > latest_booked_date):
            latest_booked_date = start

    if not region_ids:
        return []

    min_level = min(level_ids) if level_ids else 1
    now = timezone.now()
    if latest_booked_date is None:
        latest_booked_date = now

    workshop_qs = (
        Workshop.objects.filter(
            active=1,
            course__isnull=False,
            course__active=True,
        ).filter(
            Q(open_dated=1)
            | Q(date__gt=latest_booked_date, date__gte=now),
        )
        .exclude(course_id__in=booked_course_ids)
        .filter(
            Q(region_id__in=region_ids)
            | Q(course__region_id__in=region_ids)
            | Q(venue__region_id__in=region_ids)
        )
        .filter(
            Q(course__course_skill_level_id__gte=min_level)
            | Q(course__course_skill_level_id=VARIOUS_LEVEL_ID)
            | Q(course__course_skill_level_id__isnull=True)
        )
        .select_related('venue', 'course')
        .order_by('-open_dated', 'date')
    )

    course_ids = []
    seen = set()
    for course_id in workshop_qs.values_list('course_id', flat=True):
        if not course_id or course_id in seen:
            continue
        seen.add(course_id)
        course_ids.append(course_id)
        if len(course_ids) >= limit:
            break

    if not course_ids:
        return []

    courses = list(
        Course.objects.filter(pk__in=course_ids, active=True)
        .select_related('course_category', 'course_skill_level', 'image')
        .prefetch_related(
            Prefetch(
                'workshops',
                queryset=workshop_qs.filter(course_id__in=course_ids).order_by('date'),
            ),
            'media',
        )
    )

    order = {pk: idx for idx, pk in enumerate(course_ids)}
    courses.sort(key=lambda c: order.get(c.pk, 999))
    return courses
