"""Month calendar data for the workshop admin calendar view."""
from __future__ import annotations

import calendar
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone

from courses.utils import UK_TZ, workshop_calendar_date


def _parse_year_month(raw_year, raw_month, *, today=None):
    today = today or timezone.localdate()
    try:
        year = int(raw_year)
        month = int(raw_month)
    except (TypeError, ValueError):
        return today.year, today.month
    if year < 2000 or year > 2100 or month < 1 or month > 12:
        return today.year, today.month
    return year, month


def _shift_month(year, month, delta):
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def _local_date(dt):
    if not dt:
        return None
    text = workshop_calendar_date(dt)
    if not text:
        return None
    return date.fromisoformat(text)


def _month_bounds(year, month):
    """Inclusive UK local start/end datetimes covering the month (naive, matching legacy storage)."""
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    start = datetime.combine(first, time.min)
    end = datetime.combine(last, time.max.replace(microsecond=0))
    return start, end


def _workshop_label(workshop):
    course = getattr(workshop, 'course', None)
    name = (course.course_name if course else None) or f'Workshop #{workshop.pk}'
    venue = getattr(workshop, 'venue', None)
    venue_name = (venue.venue_name if venue else '') or ''
    if venue_name:
        return f'{name} — {venue_name}'
    return name


def _workshop_days(workshop, month_start, month_end):
    """Calendar days this workshop occupies within the visible month."""
    start = _local_date(workshop.date)
    if not start:
        return []
    end = _local_date(workshop.get_end_date()) or start
    if end < start:
        end = start
    day = max(start, month_start)
    last = min(end, month_end)
    days = []
    while day <= last:
        days.append(day)
        day += timedelta(days=1)
    return days


def build_workshop_calendar_context(request, queryset):
    """
    Build template context for a month grid of workshops.

    queryset should already be region-scoped. Open-dated workshops are listed
    separately (no fixed calendar day).
    """
    today = timezone.localdate()
    year, month = _parse_year_month(
        request.GET.get('year'),
        request.GET.get('month'),
        today=today,
    )
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    range_start, range_end = _month_bounds(year, month)

    from django.db.models import Q

    month_qs = (
        queryset.filter(open_dated=0, date__isnull=False)
        .filter(
            Q(date__gte=range_start, date__lte=range_end)
            | Q(date__lt=range_start, end_at__isnull=False, end_at__gte=range_start)
        )
        .select_related('course', 'venue')
        .order_by('date', 'id')
    )
    workshops_by_id = {w.pk: w for w in month_qs}

    by_day = {
        month_start + timedelta(days=i): []
        for i in range((month_end - month_start).days + 1)
    }
    for workshop in workshops_by_id.values():
        change_url = reverse('admin:courses_workshop_change', args=[workshop.pk])
        entry = {
            'id': workshop.pk,
            'label': _workshop_label(workshop),
            'url': change_url,
            'active': bool(workshop.active),
            'time_label': '',
        }
        start_local = workshop.date
        if start_local:
            if timezone.is_aware(start_local):
                start_local = timezone.localtime(start_local, UK_TZ)
            entry['time_label'] = start_local.strftime('%H:%M')
        for day in _workshop_days(workshop, month_start, month_end):
            by_day.setdefault(day, []).append(entry)

    for day_entries in by_day.values():
        day_entries.sort(key=lambda e: (e['time_label'] or '99:99', e['label'].lower()))

    open_dated = list(
        queryset.filter(open_dated=1)
        .select_related('course', 'venue')
        .order_by('course__course_name', 'id')[:50]
    )
    open_dated_items = [
        {
            'id': w.pk,
            'label': _workshop_label(w),
            'url': reverse('admin:courses_workshop_change', args=[w.pk]),
            'active': bool(w.active),
        }
        for w in open_dated
    ]

    cal = calendar.Calendar(firstweekday=0)  # Monday
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        days = []
        for day in week:
            days.append({
                'date': day,
                'in_month': day.month == month,
                'is_today': day == today,
                'workshops': by_day.get(day, []) if day.month == month else [],
            })
        weeks.append(days)

    prev_year, prev_month = _shift_month(year, month, -1)
    next_year, next_month = _shift_month(year, month, 1)
    calendar_path = reverse('admin:courses_workshop_calendar')

    def month_url(y, m):
        return f'{calendar_path}?{urlencode({"year": y, "month": m})}'

    return {
        'calendar_year': year,
        'calendar_month': month,
        'calendar_title': date(year, month, 1).strftime('%B %Y'),
        'calendar_weeks': weeks,
        'calendar_weekday_labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'calendar_prev_url': month_url(prev_year, prev_month),
        'calendar_next_url': month_url(next_year, next_month),
        'calendar_today_url': month_url(today.year, today.month),
        'calendar_workshop_count': len(workshops_by_id),
        'calendar_open_dated': open_dated_items,
        'calendar_open_dated_count': queryset.filter(open_dated=1).count(),
    }
