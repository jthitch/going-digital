"""Editable copy for the day-before workshop reminder email."""
from website.models import (
    DEFAULT_REMINDER_EMAIL_CLOSING,
    DEFAULT_REMINDER_EMAIL_INTRO,
    WorkshopReminderEmailSettings,
)


def reminder_email_copy():
    """Return intro and closing paragraphs for reminder emails."""
    settings_row = WorkshopReminderEmailSettings.get_singleton()
    if settings_row:
        return {
            'intro': settings_row.intro_text(),
            'closing': settings_row.closing_text(),
        }
    return {
        'intro': DEFAULT_REMINDER_EMAIL_INTRO,
        'closing': DEFAULT_REMINDER_EMAIL_CLOSING,
    }
