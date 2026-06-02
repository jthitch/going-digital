"""Payment KPIs for the admin dashboard."""
from datetime import date, datetime, time
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from courses.region_scope import get_user_region_ids, user_has_full_region_access
from payments.models import Payment
from payments.scope import filter_payments_for_user


def _month_start(year, month):
    return date(year, month, 1)


def _next_month_start(year, month):
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def _aware_range(start_day, end_day):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(start_day, time.min), tz)
    end = timezone.make_aware(datetime.combine(end_day, time.min), tz)
    return start, end


def _period_stats(queryset, start, end):
    qs = queryset.filter(
        status='succeeded',
        received_at__gte=start,
        received_at__lt=end,
    )
    agg = qs.aggregate(count=Count('id'), total=Sum('amount'))
    return {
        'count': agg['count'] or 0,
        'total': agg['total'] if agg['total'] is not None else Decimal('0.00'),
    }


def _received_payments_queryset(user):
    qs = Payment.objects.annotate(
        received_at=Coalesce('succeeded_at', 'created_at'),
    )
    return filter_payments_for_user(qs, user)


def get_payment_kpis_dashboard_context(request):
    user = request.user
    if not user.is_authenticated:
        return {'payment_kpis_show': False}

    if not user_has_full_region_access(user) and not get_user_region_ids(user):
        return {'payment_kpis_show': False}

    today = timezone.localdate()
    this_start_day = _month_start(today.year, today.month)
    this_end_day = _next_month_start(today.year, today.month)
    this_start, this_end = _aware_range(this_start_day, this_end_day)

    stats = _period_stats(_received_payments_queryset(user), this_start, this_end)

    if user_has_full_region_access(user):
        panel_title = _('Payments this month')
    else:
        panel_title = _('Your payments this month')

    return {
        'payment_kpis_show': True,
        'payment_kpis_title': panel_title,
        'payment_kpis_month_label': date_format(this_start_day, format='F Y'),
        'payment_kpis_count': stats['count'],
        'payment_kpis_total': stats['total'],
        'payment_kpis_changelist_url': 'admin:payments_payment_changelist',
    }
