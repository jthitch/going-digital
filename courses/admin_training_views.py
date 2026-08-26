"""Admin views for internal training guides."""
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.urls import path
from django.utils.decorators import method_decorator
from django.views import View

from courses.admin_training import (
    GUIDE_CATALOG,
    get_guide,
    render_guide_html,
    training_url_context,
)


@method_decorator(staff_member_required, name='dispatch')
class TrainingIndexView(View):
    template_name = 'admin/training/index.html'

    def get(self, request):
        context = {
            **admin.site.each_context(request),
            'title': 'Training guides',
            'guides': GUIDE_CATALOG,
            'urls': training_url_context(request),
        }
        return render(request, self.template_name, context)


@method_decorator(staff_member_required, name='dispatch')
class TrainingGuideView(View):
    template_name = 'admin/training/guide.html'

    def get(self, request, slug):
        guide = get_guide(slug)
        if guide is None:
            raise Http404('Training guide not found.')
        context = {
            **admin.site.each_context(request),
            'title': guide.title,
            'guide': guide,
            'guide_html': render_guide_html(guide, request),
            'guides': GUIDE_CATALOG,
            'urls': training_url_context(request),
        }
        return render(request, self.template_name, context)


def get_training_admin_urls():
    return [
        path(
            'training/',
            admin.site.admin_view(TrainingIndexView.as_view()),
            name='admin_training_index',
        ),
        path(
            'training/<slug:slug>/',
            admin.site.admin_view(TrainingGuideView.as_view()),
            name='admin_training_guide',
        ),
    ]
