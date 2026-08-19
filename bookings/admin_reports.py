"""Admin reports views."""
import csv
from urllib.parse import urlencode

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render

from bookings.forms_reports import (
    BookingReportFilterForm,
    PaymentGatewayReportFilterForm,
)
from bookings.reports import (
    build_franchisee_booking_report,
    build_gift_voucher_purchased_report,
    build_monthly_report,
    build_payment_gateway_report,
    build_refunds_report,
    default_payment_gateway_date_range,
    iter_franchisee_booking_report_csv,
    iter_gift_voucher_purchased_report_csv,
    iter_monthly_report_csv,
    iter_payment_gateway_report_csv,
    iter_refunds_report_csv,
    report_totals,
    user_can_view_franchisee_booking_report,
    user_can_view_gift_voucher_purchased_report,
    user_can_view_payment_gateway_report,
    user_can_view_refunds_report,
    user_can_view_reports,
)


REPORT_MONTHLY = 'monthly'
REPORT_PAYMENT_GATEWAY = 'payment_gateway'
REPORT_FRANCHISEE = 'franchisee'
REPORT_REFUNDS = 'refunds'
REPORT_GIFT_VOUCHERS = 'gift_vouchers'


def reports_admin_view(request):
    if not user_can_view_reports(request.user):
        raise PermissionDenied

    report_type = request.GET.get('report', REPORT_MONTHLY)
    if report_type not in {
        REPORT_MONTHLY,
        REPORT_PAYMENT_GATEWAY,
        REPORT_FRANCHISEE,
        REPORT_REFUNDS,
        REPORT_GIFT_VOUCHERS,
    }:
        report_type = REPORT_MONTHLY

    if report_type == REPORT_PAYMENT_GATEWAY:
        return _payment_gateway_report(request)
    if report_type == REPORT_FRANCHISEE:
        return _franchisee_booking_report(request)
    if report_type == REPORT_REFUNDS:
        return _refunds_report(request)
    if report_type == REPORT_GIFT_VOUCHERS:
        return _gift_voucher_purchased_report(request)

    return _monthly_report(request)


def _monthly_report(request):
    form = BookingReportFilterForm(request.user, request.GET or None)
    rows = []
    totals = None
    filters_applied = False
    region_id = None
    tutor_id = None
    months_back = 12
    start_date = None
    end_date = None

    if form.is_valid():
        filters_applied = True
        region_id = form.cleaned_region_id()
        tutor_id = form.cleaned_tutor_id()
        custom_range = form.cleaned_custom_date_range()
        if custom_range:
            start_date, end_date = custom_range
            months_back = None
            rows = build_monthly_report(
                request.user,
                region_id=region_id,
                tutor_id=tutor_id,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            months_back = form.cleaned_months_back()
            rows = build_monthly_report(
                request.user,
                region_id=region_id,
                tutor_id=tutor_id,
                months_back=months_back,
            )
        totals = report_totals(rows)
    elif not request.GET:
        form = BookingReportFilterForm(request.user)
        rows = build_monthly_report(request.user, months_back=months_back)
        totals = report_totals(rows)
        filters_applied = True

    export_csv_url = _monthly_export_url(
        region_id,
        tutor_id,
        months_back,
        start_date=start_date,
        end_date=end_date,
    )

    if request.GET.get('export') == 'csv' and filters_applied:
        return _csv_response(
            'monthly-booking-report.csv',
            iter_monthly_report_csv(rows, totals),
        )

    return _render_report(
        request,
        template_name='admin/bookings/reports_monthly.html',
        context={
            'report_type': REPORT_MONTHLY,
            'form': form,
            'rows': rows,
            'totals': totals,
            'filters_applied': filters_applied,
            'export_csv_url': export_csv_url,
            'custom_date_range': start_date is not None and end_date is not None,
            'start_date': start_date,
            'end_date': end_date,
        },
    )


def _payment_gateway_report(request):
    if not user_can_view_payment_gateway_report(request.user):
        raise PermissionDenied

    return _dated_booking_report(
        request,
        report_type=REPORT_PAYMENT_GATEWAY,
        template_name='admin/bookings/reports_payment_gateway.html',
        build_report=build_payment_gateway_report,
        csv_filename_prefix='bookings-by-payment-gateway',
        csv_iter=iter_payment_gateway_report_csv,
    )


def _franchisee_booking_report(request):
    if not user_can_view_franchisee_booking_report(request.user):
        raise PermissionDenied

    return _dated_booking_report(
        request,
        report_type=REPORT_FRANCHISEE,
        template_name='admin/bookings/reports_franchisee.html',
        build_report=build_franchisee_booking_report,
        csv_filename_prefix='bookings-by-franchisee',
        csv_iter=iter_franchisee_booking_report_csv,
    )


def _refunds_report(request):
    if not user_can_view_refunds_report(request.user):
        raise PermissionDenied

    return _dated_booking_report(
        request,
        report_type=REPORT_REFUNDS,
        template_name='admin/bookings/reports_refunds.html',
        build_report=build_refunds_report,
        csv_filename_prefix='refunds',
        csv_iter=iter_refunds_report_csv,
    )


def _gift_voucher_purchased_report(request):
    if not user_can_view_gift_voucher_purchased_report(request.user):
        raise PermissionDenied

    return _dated_booking_report(
        request,
        report_type=REPORT_GIFT_VOUCHERS,
        template_name='admin/bookings/reports_gift_vouchers.html',
        build_report=build_gift_voucher_purchased_report,
        csv_filename_prefix='gift-vouchers-purchased',
        csv_iter=iter_gift_voucher_purchased_report_csv,
    )


def _dated_booking_report(
    request,
    *,
    report_type,
    template_name,
    build_report,
    csv_filename_prefix,
    csv_iter,
):
    default_start, default_end = default_payment_gateway_date_range()
    initial = {'start_date': default_start, 'end_date': default_end}
    date_params_present = 'start_date' in request.GET and 'end_date' in request.GET
    form = PaymentGatewayReportFilterForm(request.GET or None, initial=initial)

    rows = []
    totals = None
    filters_applied = False
    start_date = default_start
    end_date = default_end

    if form.is_valid():
        filters_applied = True
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        rows, totals = build_report(request.user, start_date, end_date)
    elif not date_params_present:
        form = PaymentGatewayReportFilterForm(initial=initial)
        rows, totals = build_report(request.user, default_start, default_end)
        filters_applied = True

    if request.GET.get('export') == 'csv' and filters_applied:
        filename = (
            f'{csv_filename_prefix}-'
            f'{start_date:%Y-%m-%d}-to-{end_date:%Y-%m-%d}.csv'
        )
        return _csv_response(filename, csv_iter(rows))

    export_csv_url = _dated_export_url(report_type, start_date, end_date)

    return _render_report(
        request,
        template_name=template_name,
        context={
            'report_type': report_type,
            'form': form,
            'rows': rows,
            'totals': totals,
            'filters_applied': filters_applied,
            'start_date': start_date,
            'end_date': end_date,
            'export_csv_url': export_csv_url,
        },
    )


def _monthly_export_url(region_id, tutor_id, months_back, *, start_date=None, end_date=None):
    from bookings.forms_reports import MONTHS_CUSTOM

    params = {
        'report': REPORT_MONTHLY,
        'export': 'csv',
    }
    if start_date is not None and end_date is not None:
        params['months'] = MONTHS_CUSTOM
        params['start_date'] = start_date.isoformat()
        params['end_date'] = end_date.isoformat()
    else:
        params['months'] = months_back if months_back is not None else 12
    if region_id:
        params['region'] = region_id
    if tutor_id:
        params['tutor'] = tutor_id
    return f'?{urlencode(params)}'


def _dated_export_url(report_type, start_date, end_date):
    params = {
        'report': report_type,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'export': 'csv',
    }
    return f'?{urlencode(params)}'


def _csv_response(filename, row_iterable):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    writer = csv.writer(response)
    for row in row_iterable:
        writer.writerow(row)
    return response


def _render_report(request, *, template_name, context):
    from bookings.models import Booking

    context = {
        **admin.site.each_context(request),
        'title': 'Booking reports',
        'opts': Booking._meta,
        'app_label': 'bookings',
        'show_payment_gateway_report': user_can_view_payment_gateway_report(
            request.user,
        ),
        'show_franchisee_booking_report': user_can_view_franchisee_booking_report(
            request.user,
        ),
        'show_refunds_report': user_can_view_refunds_report(
            request.user,
        ),
        'show_gift_voucher_purchased_report': user_can_view_gift_voucher_purchased_report(
            request.user,
        ),
        **context,
    }
    return render(request, template_name, context)
