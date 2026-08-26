from django.apps import AppConfig


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'courses'

    def ready(self):
        from django.contrib import admin

        from courses.admin_index import patch_admin_index
        from courses.admin_training_views import get_training_admin_urls

        admin.site.index_template = 'admin/dashboard.html'
        patch_admin_index()

        original_get_urls = admin.site.get_urls

        def get_urls():
            return get_training_admin_urls() + original_get_urls()

        admin.site.get_urls = get_urls
