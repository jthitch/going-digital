from django import template

from courses.venue_approval import (
    pending_venue_count,
    pending_venues_changelist_url,
    pending_venues_queryset,
    user_sees_pending_venue_alerts,
)

register = template.Library()


@register.inclusion_tag('admin/includes/pending_venue_alerts.html', takes_context=True)
def pending_venue_alerts(context, limit=8):
    request = context.get('request')
    user = getattr(request, 'user', None)
    if not user or not user_sees_pending_venue_alerts(user):
        return {'show': False}

    pending = list(pending_venues_queryset()[:limit])
    return {
        'show': bool(pending),
        'count': pending_venue_count(),
        'pending': pending,
        'review_url': pending_venues_changelist_url(),
    }
