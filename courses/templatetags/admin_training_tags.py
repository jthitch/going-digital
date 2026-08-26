from django import template
from django.urls import NoReverseMatch, reverse

from courses.admin_training import guides_for_context

register = template.Library()


@register.inclusion_tag('admin/includes/training_help.html', takes_context=True)
def training_help(context, context_key):
    """Contextual training banner for venue / course / workshop admin screens."""
    guides = guides_for_context(context_key)
    items = []
    for guide in guides:
        try:
            url = reverse('admin:admin_training_guide', kwargs={'slug': guide.slug})
        except NoReverseMatch:
            url = '#'
        items.append({'title': guide.title, 'url': url, 'summary': guide.summary})
    try:
        hub_url = reverse('admin:admin_training_index')
    except NoReverseMatch:
        hub_url = '#'
    return {
        'show': bool(items),
        'guides': items,
        'hub_url': hub_url,
        'context_key': context_key,
    }
