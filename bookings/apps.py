from django.apps import AppConfig


class BookingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bookings'

    def ready(self):
        from django.contrib import admin
        from django.urls import path

        from bookings.admin_reports import reports_admin_view

        original_get_urls = admin.site.get_urls

        def get_urls():
            custom_urls = [
                path(
                    'reports/',
                    admin.site.admin_view(reports_admin_view),
                    name='bookings_reports',
                ),
            ]
            return custom_urls + original_get_urls()

        admin.site.get_urls = get_urls
