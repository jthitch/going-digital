"""Editable copy for the day-after workshop follow-up email."""
from website.models import (
    DEFAULT_FOLLOW_UP_EMAIL_CLOSING,
    DEFAULT_FOLLOW_UP_EMAIL_INTRO,
    DEFAULT_FOLLOW_UP_FEEDBACK_PROMPT,
    WorkshopFollowUpEmailSettings,
)


def follow_up_email_copy():
    """Return intro, closing, and feedback-form prompt for follow-up emails."""
    settings_row = WorkshopFollowUpEmailSettings.get_singleton()
    if settings_row:
        return {
            'intro': settings_row.intro_text(),
            'closing': settings_row.closing_text(),
            'feedback_prompt': settings_row.feedback_prompt_text(),
        }
    return {
        'intro': DEFAULT_FOLLOW_UP_EMAIL_INTRO,
        'closing': DEFAULT_FOLLOW_UP_EMAIL_CLOSING,
        'feedback_prompt': DEFAULT_FOLLOW_UP_FEEDBACK_PROMPT,
    }
