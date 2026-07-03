"""Read scoped rows from legacy gd_report__* tables for admin reports."""
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from bookings.legacy_report_constants import LEGACY_REPORT_BOOKING_ID_OFFSET
from bookings.models import (
    ReportBookingByCourse,
    ReportBookingByPaymentGateway,
    ReportBookingSummary,
)
from courses.models import Region, Workshop
from courses.region_scope import get_user_region_ids, user_has_full_region_access


def legacy_display_booking_id(booking_id):
    """Map legacy report booking_id back to new-site pk when offset."""
    if booking_id is None:
        return None
    value = int(booking_id)
    if value >= LEGACY_REPORT_BOOKING_ID_OFFSET:
        return value - LEGACY_REPORT_BOOKING_ID_OFFSET
    return value


def _scoped_workshop_ids(user, region_id=None, tutor_id=None, *, active_only=False):
    qs = Workshop.objects.all()
    if active_only:
        qs = qs.filter(active=1)
    if not user_has_full_region_access(user):
        region_ids = get_user_region_ids(user) or []
        qs = qs.filter(region_id__in=region_ids).filter(
            Q(user_id=user.pk) | Q(createdby_id=user.pk),
        )
    if region_id:
        qs = qs.filter(region_id=region_id)
    if tutor_id:
        qs = qs.filter(tutor_id=tutor_id)
    return qs.values_list('pk', flat=True)


def _region_names_for_filter(user, region_id=None):
    """Region names used to include legacy course rows when workshop join fails."""
    if user_has_full_region_access(user):
        if not region_id:
            return []
        return list(
            Region.objects.filter(pk=region_id, active=1).values_list(
                'region_name',
                flat=True,
            ),
        )

    region_ids = get_user_region_ids(user) or []
    if not region_ids:
        return []
    if region_id and region_id in region_ids:
        region_ids = [region_id]
    return list(
        Region.objects.filter(pk__in=region_ids, active=1).values_list(
            'region_name',
            flat=True,
        ),
    )


def _course_report_scope_filter(user, region_id=None, tutor_id=None):
    """
    Scope course report rows via gd_workshop.id (booking_workshop_id) and region_name.
    """
    workshop_ids = list(_scoped_workshop_ids(user, region_id, tutor_id, active_only=False))
    scope = Q()
    if workshop_ids:
        scope |= Q(booking_workshop_id__in=workshop_ids)

    region_names = _region_names_for_filter(user, region_id)
    if region_names:
        scope |= Q(region_name__in=region_names)

    return scope


def filter_course_report_queryset(queryset, user, region_id=None, tutor_id=None):
    if not user_has_full_region_access(user):
        queryset = queryset.filter(user_id=user.pk)
    if region_id or tutor_id or not user_has_full_region_access(user):
        scope = _course_report_scope_filter(user, region_id, tutor_id)
        if scope:
            queryset = queryset.filter(scope)
        elif not user_has_full_region_access(user):
            return queryset.none()
    return queryset


def filter_payment_gateway_queryset(queryset, user, region_id=None, tutor_id=None):
    if user_has_full_region_access(user):
        if not region_id and not tutor_id:
            return queryset
        workshop_ids = list(_scoped_workshop_ids(user, region_id, tutor_id, active_only=False))
        if not workshop_ids:
            return queryset.none()
        return queryset.filter(workshop_id__in=workshop_ids)

    workshop_ids = list(_scoped_workshop_ids(user, region_id, tutor_id, active_only=False))
    if not workshop_ids:
        return queryset.none()
    return queryset.filter(workshop_id__in=workshop_ids, user_id=user.pk)


def filter_summary_queryset(queryset, user):
    if user_has_full_region_access(user):
        return queryset
    workshop_ids = list(_scoped_workshop_ids(user, active_only=False))
    if not workshop_ids:
        return queryset.none()
    return queryset.filter(
        Q(franchisee_id=user.pk) | Q(user_id=user.pk),
        workshop_id__in=workshop_ids,
    )


def _legacy_report_date_filter(field_name, start_day, end_day):
    """Filter legacy datetime columns by calendar date (naive DB values)."""
    return {
        f'{field_name}__date__gte': start_day,
        f'{field_name}__date__lt': end_day,
    }


def payment_gateway_report_rows(user, start_dt, end_dt):
    qs = ReportBookingByPaymentGateway.objects.filter(
        booking_date__gte=start_dt,
        booking_date__lt=end_dt,
    ).order_by('-booking_date', '-booking_id')
    return list(filter_payment_gateway_queryset(qs, user))


def course_report_booking_rows(user, start_dt, end_dt):
    """Line-item rows from gd_report__bookings_by_course scoped via gd_workshop."""
    qs = ReportBookingByCourse.objects.filter(
        booking_date__gte=start_dt,
        booking_date__lt=end_dt,
    ).order_by('user_id', '-booking_date', '-booking_id')
    qs = filter_course_report_queryset(qs, user)
    return list(qs)


def payment_gateway_rows_for_booking_ids(user, booking_ids):
    if not booking_ids:
        return {}
    qs = ReportBookingByPaymentGateway.objects.filter(booking_id__in=booking_ids)
    rows = list(filter_payment_gateway_queryset(qs, user))
    return {row.booking_id: row for row in rows}


def workshops_by_ids(workshop_ids):
    ids = sorted({int(workshop_id) for workshop_id in workshop_ids if workshop_id})
    if not ids:
        return {}
    return Workshop.objects.in_bulk(ids)


def summary_report_rows_for_booking_ids(user, booking_ids):
    if not booking_ids:
        return []
    qs = ReportBookingSummary.objects.filter(booking_id__in=booking_ids).order_by(
        '-workshop_date',
        '-booking_id',
    )
    return list(filter_summary_queryset(qs, user))


def payment_gateway_rows_by_booking_id(rows):
    return {row.booking_id: row for row in rows}


def legacy_row_payment_date(value):
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localdate(value)


def legacy_row_workshop_date(value):
    return legacy_row_payment_date(value)


def gateway_id_from_name(name, gateway_names):
    normalized = (name or '').strip().lower()
    if not normalized or normalized == 'unknown':
        return None
    for gateway_id, gateway_name in gateway_names.items():
        if gateway_name.strip().lower() == normalized:
            return gateway_id
    return None
