from django.apps import AppConfig


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'courses'

    def ready(self):
        from django.contrib import admin

        from courses.admin_index import patch_admin_index

        admin.site.index_template = 'admin/dashboard.html'
        patch_admin_index()
