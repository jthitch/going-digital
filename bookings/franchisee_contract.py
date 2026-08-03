"""Franchisee contract wording for booking confirmations."""
from core.models import User


def resolve_workshop_franchisee(workshop):
    """Workshop owner (user_id), then creator (createdby_id)."""
    if not workshop:
        return None
    for uid in (getattr(workshop, 'user_id', None), getattr(workshop, 'createdby_id', None)):
        if not uid:
            continue
        user = User.objects.filter(pk=uid, active=1).first()
        if user:
            return user
    return None


def franchisee_contract_details(workshop):
    """Return {'name', 'address'} for the workshop franchisee, or None."""
    user = resolve_workshop_franchisee(workshop)
    if not user:
        return None
    name = (user.get_full_name() or '').strip()
    if not name:
        return None
    return {
        'name': name,
        'address': user.get_display_address(),
    }


def franchisee_contract_notice_from_details(details):
    """Build the contract sentence from franchisee_contract_details() output."""
    if not details or not details.get('name'):
        return ''
    name = details['name']
    address = (details.get('address') or '').strip()
    if address:
        return (
            'You have entered into a contract with a Going Digital franchise, '
            f'owned and operated under licence by {name}, {address}'
        )
    return (
        'You have entered into a contract with a Going Digital franchise, '
        f'owned and operated under licence by {name}'
    )


def franchisee_contract_notice(workshop):
    """Full contract sentence for emails and confirmation pages, or ''."""
    return franchisee_contract_notice_from_details(franchisee_contract_details(workshop))
