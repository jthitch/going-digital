from django import forms
from django.contrib import admin, messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from django.utils.translation import gettext_lazy as _

from courses.admin_changelist import GdActiveFilter, SearchFirstChangeListMixin
from courses.admin_mixins import PlatformAdminOnlyMixin
from courses.forms import BooleanToggleWidget
from courses.models import Workshop
from courses.region_scope import (
    filter_workshops_for_user,
    user_has_full_region_access,
)

from .admin_booking_list import (
    count_unified_admin_bookings,
    filters_from_request,
    load_unified_admin_bookings,
)
from .admin_mixins import RegionScopedBookingAdminMixin
from .discount_codes import (
    filter_discount_codes_for_user,
    workshops_queryset_for_discount_admin,
)
from .forms import DiscountCodeAdminForm, ManualBookingAdminForm
from .manual_booking import create_manual_booking
from .models import (
    Booking,
    BookingTermsAcceptance,
    CameraMake,
    CameraModel,
    DiscountCode,
    Voucher,
    WorkshopFeedback,
)


class CameraModelInline(admin.TabularInline):
    model = CameraModel
    extra = 1
    fields = ['name', 'sort_order', 'is_active']
    ordering = ['sort_order', 'name']


@admin.register(CameraMake)
class CameraMakeAdmin(admin.ModelAdmin):
    """Superuser-managed camera make/model catalog for student forms."""

    list_display = ['name', 'sort_order', 'is_active', 'model_count']
    list_editable = ['sort_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'models__name']
    ordering = ['sort_order', 'name']
    inlines = [CameraModelInline]

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    @admin.display(description='Models')
    def model_count(self, obj):
        return obj.models.count()


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    form = DiscountCodeAdminForm
    list_display = [
        'code',
        'discount_label_display',
        'is_active',
        'expiry_date',
        'workshop_count',
        'times_redeemed',
        'created_by',
        'created_at',
    ]
    list_filter = ['is_active', 'discount_type', 'expiry_date']
    search_fields = ['code', 'notes', 'created_by__email', 'created_by__firstname']
    filter_horizontal = []
    readonly_fields = ['times_redeemed', 'created_by', 'created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': (
                'code',
                'discount_type',
                'amount',
                'is_active',
                'expiry_date',
                'workshops',
                'notes',
            ),
        }),
        ('Usage', {
            'fields': ('times_redeemed', 'created_by', 'created_at', 'updated_at'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('created_by').prefetch_related('workshops')
        return filter_discount_codes_for_user(qs, request.user)

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        workshop_qs = workshops_queryset_for_discount_admin(request.user)

        class ScopedDiscountCodeForm(form_class):
            def __init__(self, *args, **form_kwargs):
                form_kwargs.setdefault('workshop_queryset', workshop_qs)
                super().__init__(*args, **form_kwargs)

        ScopedDiscountCodeForm.__name__ = form_class.__name__
        ScopedDiscountCodeForm.__qualname__ = form_class.__qualname__
        return ScopedDiscountCodeForm

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        if user_has_full_region_access(request.user):
            return super().has_module_permission(request)
        return bool(request.user and getattr(request.user, 'is_region_scoped', False))

    def has_view_permission(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().has_view_permission(request, obj)
        if not getattr(request.user, 'is_region_scoped', False):
            return False
        if obj is None:
            return True
        return obj.created_by_id == request.user.pk

    def has_add_permission(self, request):
        if user_has_full_region_access(request.user):
            return super().has_add_permission(request)
        return bool(getattr(request.user, 'is_region_scoped', False))

    def has_change_permission(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().has_change_permission(request, obj)
        if not getattr(request.user, 'is_region_scoped', False):
            return False
        if obj is None:
            return True
        return obj.created_by_id == request.user.pk

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    @admin.display(description='Discount')
    def discount_label_display(self, obj):
        return obj.discount_label

    @admin.display(description='Workshops')
    def workshop_count(self, obj):
        return obj.workshops.count()


@admin.register(Voucher)
class VoucherAdmin(PlatformAdminOnlyMixin, SearchFirstChangeListMixin, admin.ModelAdmin):
    """Legacy gd_voucher: read-only except active (platform admins may deactivate)."""

    list_display = [
        'id',
        'voucher_code',
        'value',
        'email',
        'active',
        'issue_date',
        'expiry_date',
        'claimed_date',
    ]
    list_filter = [GdActiveFilter]
    gd_changelist_show_date_range = True
    gd_changelist_date_field = 'issue_date'
    gd_changelist_date_range_id_prefix = 'voucher'
    gd_changelist_date_range_hint = _('Filter by issue date.')
    search_fields = ['voucher_code', 'email', 'notes']
    search_help_text = 'Search by voucher code, email, or notes.'
    fieldsets = (
        ('Status', {
            'fields': ('active',),
            'description': 'Inactive vouchers cannot be redeemed at checkout.',
        }),
        ('Voucher details', {
            'fields': (
                'id',
                'voucher_code',
                'value',
                'email',
                'issue_date',
                'expiry_date',
                'claimed_date',
                'amount_claimed',
                'claimed_booking_link',
                'actioned',
                'notes',
            ),
        }),
        ('Legacy fields', {
            'classes': ('collapse',),
            'fields': (
                'basket_id',
                'voucher_type_id',
                'use_once',
                'voucher_group_id',
                'user_id',
                'customer_id',
                'claimed_by_customer_id',
                'claimed_on_booking_id',
                'region_id',
                'course_ids',
                'workshop_id',
                'payment_gateway_id',
                'gateway_transaction_code',
                'transaction_percentage_on_creation',
                'minimum_workshops',
                'allowed_course',
                'createdby_id',
                'updatedby_id',
                'created_at',
                'updated_at',
            ),
        }),
    )
    readonly_fields = [
        'id', 'basket_id', 'voucher_type_id', 'use_once', 'voucher_group_id',
        'user_id', 'customer_id', 'claimed_by_customer_id', 'claimed_on_booking_id',
        'claimed_booking_link',
        'region_id', 'course_ids', 'workshop_id', 'actioned', 'email', 'issue_date',
        'expiry_date', 'value', 'voucher_code', 'claimed_date', 'amount_claimed',
        'payment_gateway_id', 'gateway_transaction_code', 'transaction_percentage_on_creation',
        'notes', 'minimum_workshops', 'allowed_course', 'createdby_id', 'updatedby_id',
        'created_at', 'updated_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'active':
            return forms.BooleanField(
                required=False,
                label='Active',
                widget=BooleanToggleWidget(),
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)

        class VoucherAdminForm(form_class):
            def __init__(self, *args, **form_kwargs):
                super().__init__(*args, **form_kwargs)
                if self.instance.pk and 'active' in self.fields:
                    self.fields['active'].initial = bool(self.instance.active)

        VoucherAdminForm.__name__ = form_class.__name__
        return VoucherAdminForm

    def save_model(self, request, obj, form, change):
        if 'active' in form.cleaned_data:
            obj.active = 1 if form.cleaned_data['active'] else 0
        if change:
            obj.updatedby_id = request.user.pk
            obj.updated_at = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.display(description='Claimed booking')
    def claimed_booking_link(self, obj):
        if not obj.claimed_on_booking_id:
            return '—'
        booking = Booking.objects.filter(pk=obj.claimed_on_booking_id).first()
        if not booking:
            return f'Booking #{obj.claimed_on_booking_id}'
        url = reverse('admin:bookings_booking_change', args=[booking.pk])
        return format_html('<a href="{}">{}</a>', url, booking.booking_reference)


@admin.register(Booking)
class BookingAdmin(RegionScopedBookingAdminMixin, admin.ModelAdmin):
    autocomplete_fields = ['workshop']
    change_list_template = 'admin/bookings/booking/change_list.html'
    list_per_page = 50
    actions = None
    list_display = [
        'booking_reference',
        'student_first_name',
        'student_last_name',
        'student_email',
        'course_name',
        'workshop_date',
        'status',
        'payment_status',
        'voucher_code',
        'voucher_discount',
        'price_paid',
        'loan_camera',
        'created_at',
    ]
    list_filter = ['status', 'created_at', 'workshop__course', 'workshop__venue']
    search_fields = [
        'booking_reference',
        'student_first_name',
        'student_last_name',
        'student_email',
        'voucher_code',
        'user__email',
        'workshop__course__course_name',
    ]
    # Editable on change by superusers and franchisees who can view the booking.
    student_editable_fields = (
        'student_first_name',
        'student_last_name',
        'student_phone',
        'special_requirements',
        'loan_camera',
    )
    change_readonly_fields = [
        'booking_reference',
        'workshop',
        'user',
        'payment',
        'student_email',
        'status',
        'list_price',
        'voucher_id',
        'discount_code',
        'voucher_code',
        'voucher_discount',
        'voucher_redeemed_at',
        'voucher_admin_link',
        'price_paid',
        'created_at',
        'updated_at',
        'cancelled_at',
        'workshop_summary',
    ]
    add_readonly_fields = [
        'booking_reference',
        'status',
        'created_at',
        'updated_at',
        'cancelled_at',
    ]
    fieldsets = (
        (None, {
            'fields': (
                'booking_reference',
                'status',
                'workshop_summary',
            ),
        }),
        ('Pricing', {
            'fields': (
                'list_price',
                'voucher_code',
                'voucher_discount',
                'voucher_id',
                'discount_code',
                'voucher_admin_link',
                'voucher_redeemed_at',
                'price_paid',
            ),
        }),
        ('Student', {
            'fields': (
                'student_first_name',
                'student_last_name',
                'student_email',
                'student_phone',
                'special_requirements',
                'loan_camera',
            ),
        }),
        ('Payment & account', {
            'fields': (
                'payment',
                'user',
            ),
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'cancelled_at',
            ),
        }),
    )
    add_fieldsets = (
        (None, {
            'fields': ('workshop', 'include_future_workshops'),
            'description': (
                'Add a walk-up student who paid the tutor on the day. '
                'The booking is saved as confirmed with a Cash / paid-to-tutor payment. '
                'Workshop search shows today and older dates by default.'
            ),
        }),
        ('Student', {
            'fields': (
                'student_first_name',
                'student_last_name',
                'student_email',
                'student_phone',
                'special_requirements',
                'loan_camera',
            ),
        }),
        ('Payment', {
            'fields': (
                'list_price',
                'price_paid',
                'send_confirmation_email',
            ),
        }),
    )
    date_hierarchy = 'created_at'

    class Media:
        js = ('admin/js/manual-booking-workshop.js',)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        filters = filters_from_request(request)
        per_page = self.list_per_page or 50
        total = count_unified_admin_bookings(request.user, filters)

        class _LenOnly:
            def __init__(self, n):
                self._n = int(n)

            def __len__(self):
                return self._n

            def __getitem__(self, key):
                if isinstance(key, slice):
                    start = 0 if key.start is None else key.start
                    stop = self._n if key.stop is None else key.stop
                    start = max(0, start)
                    stop = max(start, min(stop, self._n))
                    return [None] * (stop - start)
                return None

        paginator = Paginator(_LenOnly(total), per_page, allow_empty_first_page=True)
        try:
            page_number = max(1, int(request.GET.get('p') or 1))
        except (TypeError, ValueError):
            page_number = 1
        try:
            page = paginator.page(min(page_number, max(paginator.num_pages, 1)))
        except (EmptyPage, PageNotAnInteger):
            page = paginator.page(1)

        offset = (page.number - 1) * per_page
        rows = (
            load_unified_admin_bookings(
                request.user,
                filters,
                limit=per_page,
                offset=max(0, offset),
            )
            if total
            else []
        )

        query = request.GET.copy()
        query.pop('p', None)

        def page_url(num):
            q = query.copy()
            if num > 1:
                q['p'] = str(num)
            qs = q.urlencode()
            return f'{request.path}?{qs}' if qs else request.path

        extra_context.update({
            'use_unified_booking_list': True,
            'unified_booking_rows': rows,
            'unified_result_count': total,
            'unified_page': page,
            'unified_paginator': paginator,
            'unified_prev_url': page_url(page.previous_page_number()) if page.has_previous() else None,
            'unified_next_url': page_url(page.next_page_number()) if page.has_next() else None,
        })
        # Django's ChangeList paginates the new-site queryset only; drop `p` so a
        # deep legacy page does not 404 when there are few new bookings.
        request.GET = request.GET.copy()
        request.GET.pop('p', None)
        return super().changelist_view(request, extra_context=extra_context)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return list(self.add_readonly_fields)
        readonly = list(self.change_readonly_fields)
        if user_has_full_region_access(request.user):
            return readonly
        # Franchisees: only student contact/details fields above stay editable.
        editable = set(self.student_editable_fields)
        locked = [
            f.name for f in self.model._meta.fields if f.name not in editable
        ] + [f.name for f in self.model._meta.many_to_many]
        return list(dict.fromkeys(locked + readonly))

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = ManualBookingAdminForm
            form_class = super().get_form(request, obj, **kwargs)
            workshop_base_qs = filter_workshops_for_user(
                Workshop.objects.select_related('course', 'venue'),
                request.user,
            )

            class BoundManualBookingForm(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs.setdefault('workshop_base_queryset', workshop_base_qs)
                    super().__init__(*args, **form_kwargs)

            BoundManualBookingForm.__name__ = form_class.__name__
            BoundManualBookingForm.__qualname__ = form_class.__qualname__
            return BoundManualBookingForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        if change:
            return super().save_model(request, obj, form, change)

        booking = create_manual_booking(
            workshop=form.cleaned_data['workshop'],
            student_first_name=form.cleaned_data['student_first_name'],
            student_last_name=form.cleaned_data['student_last_name'],
            student_email=form.cleaned_data['student_email'],
            student_phone=form.cleaned_data.get('student_phone') or '',
            special_requirements=form.cleaned_data.get('special_requirements') or '',
            loan_camera=bool(form.cleaned_data.get('loan_camera')),
            list_price=form.cleaned_data.get('list_price'),
            price_paid=form.cleaned_data.get('price_paid'),
            send_confirmation_email=bool(
                form.cleaned_data.get('send_confirmation_email', True)
            ),
            created_by=request.user,
        )
        obj.pk = booking.pk
        obj.booking_reference = booking.booking_reference
        obj.status = booking.status
        obj.payment_id = booking.payment_id
        obj.customer_id = booking.customer_id
        messages.success(
            request,
            f'Manual booking {booking.booking_reference} created (paid to tutor).',
        )

    def response_add(self, request, obj, post_url_continue=None):
        return super().response_add(request, obj, post_url_continue)

    @admin.display(description='Course', ordering='workshop__course__course_name')
    def course_name(self, obj):
        if not obj.workshop or not obj.workshop.course:
            return '—'
        return obj.workshop.course.course_name

    @admin.display(description='Workshop date', ordering='workshop__date')
    def workshop_date(self, obj):
        if not obj.workshop or not obj.workshop.date:
            return '—'
        return obj.workshop.date.strftime('%d %b %Y')

    @admin.display(description='Payment', ordering='payment__status')
    def payment_status(self, obj):
        if not obj.payment:
            return '—'
        if obj.payment.intent_type == 'manual_tutor':
            return 'Paid to tutor'
        return obj.payment.get_status_display() if hasattr(obj.payment, 'get_status_display') else obj.payment.status

    @admin.display(description='Voucher record')
    def voucher_admin_link(self, obj):
        if obj.discount_code_id:
            url = reverse('admin:bookings_discountcode_change', args=[obj.discount_code_id])
            label = obj.voucher_code or f'Discount #{obj.discount_code_id}'
            return format_html('<a href="{}">{}</a>', url, label)
        if not obj.voucher_id:
            return '—'
        url = reverse('admin:bookings_voucher_change', args=[obj.voucher_id])
        label = obj.voucher_code or f'Voucher #{obj.voucher_id}'
        return format_html('<a href="{}">{}</a>', url, label)

    @admin.display(description='Workshop')
    def workshop_summary(self, obj):
        workshop = obj.workshop
        if not workshop:
            return '—'
        parts = []
        if workshop.course:
            parts.append(format_html('Course: <strong>{}</strong>', workshop.course.course_name))
        if workshop.venue:
            parts.append(format_html('Venue: {}', workshop.venue.venue_name))
        if workshop.date:
            parts.append(format_html('Date: {}', workshop.date.strftime('%d %B %Y')))
        if obj.payment_id and obj.payment and obj.payment.intent_type == 'manual_tutor':
            parts.append('Payment: paid to tutor')
        return format_html('<br>'.join(parts)) if parts else '—'


@admin.register(BookingTermsAcceptance)
class BookingTermsAcceptanceAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    list_display = [
        'id',
        'accepted_at',
        'customer',
        'basket_id',
        'booking_count',
        'terms_updated_at',
        'ip_address',
    ]
    list_filter = ['accepted_at']
    search_fields = ['customer__email', 'customer__firstname', 'customer__lastname', 'ip_address']
    readonly_fields = [
        'customer',
        'basket_id',
        'booking_ids',
        'accepted_at',
        'ip_address',
        'user_agent',
        'terms_updated_at',
    ]

    @admin.display(description='Bookings')
    def booking_count(self, obj):
        return len(obj.booking_ids or [])

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WorkshopFeedback)
class WorkshopFeedbackAdmin(admin.ModelAdmin):
    """
    Student ratings and comments from day-after follow-up emails.
    Superusers see all; franchisees see feedback for workshops they created/own.
    """

    list_display = [
        'rated_at',
        'rating_stars',
        'workshop_label',
        'student_name',
        'comment_preview',
        'booking_ref',
    ]
    list_filter = ['rating', 'rated_at']
    search_fields = [
        'comment',
        'booking__booking_reference',
        'booking__student_first_name',
        'booking__student_last_name',
        'booking__student_email',
        'workshop__course__title',
    ]
    readonly_fields = [
        'booking',
        'workshop',
        'rating',
        'comment',
        'rated_at',
        'comment_submitted_at',
        'updated_at',
    ]
    ordering = ['-rated_at']
    date_hierarchy = 'rated_at'

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            'booking',
            'workshop',
            'workshop__course',
            'workshop__venue',
        )
        if user_has_full_region_access(request.user):
            return qs
        owned_workshop_ids = filter_workshops_for_user(
            Workshop.objects.all(),
            request.user,
        ).values_list('pk', flat=True)
        return qs.filter(workshop_id__in=owned_workshop_ids)

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and request.user.is_staff)

    def has_view_permission(self, request, obj=None):
        if not (request.user and request.user.is_active and request.user.is_staff):
            return False
        if obj is None or user_has_full_region_access(request.user):
            return True
        return filter_workshops_for_user(
            Workshop.objects.filter(pk=obj.workshop_id),
            request.user,
        ).exists()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    @admin.display(description='Rating', ordering='rating')
    def rating_stars(self, obj):
        return f'{obj.rating} ★'

    @admin.display(description='Workshop')
    def workshop_label(self, obj):
        workshop = obj.workshop
        if not workshop:
            return '—'
        title = workshop.course.title if workshop.course else 'Workshop'
        date = workshop.start_date.strftime('%d %b %Y') if workshop.start_date else ''
        return f'{title} ({date})' if date else title

    @admin.display(description='Student')
    def student_name(self, obj):
        booking = obj.booking
        if not booking:
            return '—'
        return f'{booking.student_first_name} {booking.student_last_name}'.strip() or booking.student_email

    @admin.display(description='Comment')
    def comment_preview(self, obj):
        text = (obj.comment or '').strip()
        if not text:
            return '—'
        if len(text) > 80:
            return f'{text[:77]}…'
        return text

    @admin.display(description='Booking')
    def booking_ref(self, obj):
        return obj.booking.booking_reference if obj.booking_id else '—'
