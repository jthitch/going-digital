from django import template

from courses.venue_approval import (
    pending_content_change_count,
    pending_content_change_venues_queryset,
    pending_content_changes_changelist_url,
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
    content_pending = list(pending_content_change_venues_queryset()[:limit])
    venue_count = pending_venue_count()
    content_count = pending_content_change_count()
    return {
        'show': bool(pending or content_pending),
        'count': venue_count,
        'pending': pending,
        'review_url': pending_venues_changelist_url(),
        'content_count': content_count,
        'content_pending': content_pending,
        'content_review_url': pending_content_changes_changelist_url(),
    }
