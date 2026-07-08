"""Workshop/course duration helpers from start and end datetimes."""
from datetime import timedelta

_DAY_LABELS = {
    2: 'Two days',
    3: 'Three days',
    4: 'Four days',
    5: 'Five days',
    6: 'Six days',
    7: 'Seven days',
}

DEFAULT_WORKSHOP_HOURS = 6


def resolve_workshop_end(workshop, *, default_hours=DEFAULT_WORKSHOP_HOURS):
    """Return workshop end datetime (stored end_at, or legacy start + default hours)."""
    if not workshop:
        return None
    stored_end = getattr(workshop, 'end_at', None)
    if stored_end:
        return stored_end
    start = getattr(workshop, 'date', None)
    if start:
        return start + timedelta(hours=default_hours)
    return None


def calendar_day_span(start, end):
    if not start or not end:
        return 0
    return (end.date() - start.date()).days + 1


def format_duration(start, end, *, default_hours=DEFAULT_WORKSHOP_HOURS):
    """Human-readable duration: hours for single-day, 'Two days' etc. for multi-day."""
    if not start:
        return ''
    if not end:
        end = start + timedelta(hours=default_hours)
    if end < start:
        return ''

    day_count = calendar_day_span(start, end)
    if day_count >= 2:
        return _DAY_LABELS.get(day_count, f'{day_count} days')

    hours = (end - start).total_seconds() / 3600
    hours = max(0, round(hours, 1))
    if hours == int(hours):
        count = int(hours)
        return '1 hour' if count == 1 else f'{count} hours'
    return f'{hours} hours'


def duration_hours_value(start, end, *, default_hours=DEFAULT_WORKSHOP_HOURS):
    """Whole hours for APIs; 0 when the span covers two or more calendar days."""
    if not start:
        return 0
    if not end:
        end = start + timedelta(hours=default_hours)
    if end < start:
        return 0
    if calendar_day_span(start, end) >= 2:
        return 0
    hours = (end - start).total_seconds() / 3600
    hours = max(0, round(hours, 1))
    return int(hours) if hours == int(hours) else hours


def duration_iso8601(start, end, *, default_hours=DEFAULT_WORKSHOP_HOURS):
    """ISO 8601 duration for schema.org (e.g. PT6H or P2D)."""
    if not start:
        return None
    if not end:
        end = start + timedelta(hours=default_hours)
    if end < start:
        return None

    day_count = calendar_day_span(start, end)
    if day_count >= 2:
        return f'P{day_count}D'

    hours = max(1, round((end - start).total_seconds() / 3600))
    return f'PT{hours}H'
