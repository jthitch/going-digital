"""Region-based admin scoping for franchisees (gd_region_user)."""
from django.db.models import Q


def user_has_full_region_access(user):
    """Super users and administrators see all regions."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.user_type_id == 2


def get_user_region_ids(user):
    """
    Return list of region ids for a franchisee, or None if unrestricted.
    Empty list means no regions assigned.
    """
    if user_has_full_region_access(user):
        return None
    if getattr(user, 'is_region_scoped', False):
        return user.get_region_ids()
    return None


def _filter_courses_by_region(queryset, user):
    """Global courses (no region) plus courses in the user's regions."""
    region_ids = get_user_region_ids(user)
    if region_ids is None:
        return queryset
    if not region_ids:
        return queryset.none()
    return queryset.filter(Q(region_id__isnull=True) | Q(region_id__in=region_ids))


def filter_courses_for_user(queryset, user):
    """
    Courses visible to a franchisee in admin: region-eligible, minus workshop blocks.

    Blocked courses are hidden from the course list and course autocomplete
    (including the workshop form course picker).
    """
    queryset = _filter_courses_by_region(queryset, user)
    region_ids = get_user_region_ids(user)
    if region_ids is None:
        return queryset
    blocked_ids = course_workshop_block_ids(user)
    if not blocked_ids:
        return queryset
    return queryset.exclude(pk__in=blocked_ids)


def course_workshop_block_ids(user):
    """Course PKs this franchisee may not select when creating/changing workshops."""
    if not getattr(user, 'pk', None):
        return frozenset()
    if user_has_full_region_access(user):
        return frozenset()
    from courses.models import CourseWorkshopBlock

    return frozenset(
        CourseWorkshopBlock.objects.filter(user_id=user.pk).values_list('course_id', flat=True)
    )


def franchisee_course_blocked(user, course):
    if not course or not getattr(user, 'pk', None):
        return False
    return course.pk in course_workshop_block_ids(user)


def filter_courses_for_workshop_picker(queryset, user, *, include_course_ids=None):
    """
    Courses a franchisee may pick for a workshop: region-eligible, minus deny-list blocks.

    include_course_ids re-includes the current workshop's course(s) so existing
    workshops on a blocked course remain editable without switching course.
    """
    queryset = filter_courses_for_user(queryset, user)
    keep = {pk for pk in (include_course_ids or ()) if pk}
    if not keep:
        return queryset
    # Re-add kept courses that still pass region scope (even if blocked).
    kept = _filter_courses_by_region(
        queryset.model.objects.filter(pk__in=keep),
        user,
    )
    return (queryset | kept).distinct()


def franchisee_owns_workshop(user, workshop):
    if not workshop:
        return False
    return workshop.user_id == user.pk or workshop.createdby_id == user.pk


def franchisee_owns_venue(user, venue):
    if not venue:
        return False
    if venue.user_id == user.pk:
        return True
    return venue.user_id is None and venue.createdby_id == user.pk


def venue_workshop_access_venue_ids(user):
    """Venue PKs where this franchisee may create workshops via superuser grant."""
    from courses.models import VenueWorkshopAccess

    return frozenset(
        VenueWorkshopAccess.objects.filter(user_id=user.pk).values_list('venue_id', flat=True)
    )


def franchisee_has_venue_workshop_grant(user, venue):
    if not venue or not getattr(user, 'pk', None):
        return False
    return venue.pk in venue_workshop_access_venue_ids(user)


def _franchisee_owned_venues_q(user):
    return Q(user_id=user.pk) | Q(user_id__isnull=True, createdby_id=user.pk)


def filter_workshops_for_user(queryset, user):
    """Franchisees: only workshops they created or own, within assigned regions."""
    region_ids = get_user_region_ids(user)
    if region_ids is None:
        return queryset
    if not region_ids:
        return queryset.none()
    return queryset.filter(region_id__in=region_ids).filter(
        Q(user_id=user.pk) | Q(createdby_id=user.pk)
    )


def filter_venues_for_user(queryset, user):
    """Franchisees: own venues, plus any with explicit workshop-access grants."""
    region_ids = get_user_region_ids(user)
    if region_ids is None:
        return queryset
    if not region_ids:
        return queryset.none()
    granted_ids = venue_workshop_access_venue_ids(user)
    owned = queryset.filter(region_id__in=region_ids).filter(_franchisee_owned_venues_q(user))
    if not granted_ids:
        return owned
    granted = queryset.filter(pk__in=granted_ids)
    return (owned | granted).distinct()


def filter_venues_for_workshop_picker(queryset, user):
    """Venues the franchisee owns *or* has been granted workshop-creation access to."""
    region_ids = get_user_region_ids(user)
    if region_ids is None:
        return queryset
    if not region_ids:
        return queryset.none()
    granted_ids = venue_workshop_access_venue_ids(user)
    owned = queryset.filter(region_id__in=region_ids).filter(_franchisee_owned_venues_q(user))
    if not granted_ids:
        return owned
    granted = queryset.filter(pk__in=granted_ids)
    return (owned | granted).distinct()


def venue_is_approved(venue):
    return bool(venue and venue.approved == 1)


def user_can_access_venue(user, venue):
    if user_has_full_region_access(user):
        return True
    if not venue:
        return False
    if franchisee_has_venue_workshop_grant(user, venue):
        return True
    if not venue.region_id:
        return False
    if not user_can_access_region(user, venue.region_id):
        return False
    return franchisee_owns_venue(user, venue)


def user_can_change_venue(user, venue):
    """Franchisees may edit their own venues (content always; details only until approved)."""
    if user_has_full_region_access(user):
        return True
    if not user_can_access_venue(user, venue):
        return False
    return franchisee_owns_venue(user, venue)


def user_can_edit_venue_details(user, venue):
    """Franchisees may change address/contact details only before the venue is approved."""
    if user_has_full_region_access(user):
        return True
    if not user_can_change_venue(user, venue):
        return False
    return venue.approved != 1


def user_can_add_venue(user):
    if user_has_full_region_access(user):
        return True
    return bool(get_user_region_ids(user))


def filter_regions_for_user(queryset, user):
    region_ids = get_user_region_ids(user)
    if region_ids is None:
        return queryset
    if not region_ids:
        return queryset.none()
    return queryset.filter(pk__in=region_ids)


def user_can_access_region(user, region_id):
    if not region_id:
        return False
    region_ids = get_user_region_ids(user)
    if region_ids is None:
        return True
    return region_id in region_ids


def user_can_view_course(user, course):
    if user_has_full_region_access(user):
        return True
    if franchisee_course_blocked(user, course):
        return False
    region_ids = get_user_region_ids(user) or []
    if not region_ids:
        return False
    if not course.region_id:
        return True
    return course.region_id in region_ids


def user_can_access_workshop(user, workshop):
    if user_has_full_region_access(user):
        return True
    if not workshop or not workshop.region_id:
        return False
    if not user_can_access_region(user, workshop.region_id):
        return False
    return franchisee_owns_workshop(user, workshop)
