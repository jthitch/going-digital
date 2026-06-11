"""
Utility functions for courses app.
"""
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

UK_TZ = ZoneInfo('Europe/London')


def get_easter_sunday(year):
    """
    Calculate Easter Sunday for a given year using the Anonymous Gregorian algorithm.
    Returns a date object.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_uk_mothers_day(year):
    """
    UK Mother's Day = 4th Sunday of Lent = 3 weeks before Easter Sunday.
    """
    easter = get_easter_sunday(year)
    return easter - timedelta(days=21)


def get_uk_fathers_day(year):
    """
    UK Father's Day = 3rd Sunday in June.
    """
    june_first = date(year, 6, 1)
    # weekday(): Mon=0 ... Sun=6. Days until first Sunday.
    days_to_first_sunday = (6 - june_first.weekday() + 7) % 7
    first_sunday = june_first + timedelta(days=days_to_first_sunday)
    return first_sunday + timedelta(days=14)  # 3rd Sunday


def get_promoted_occasions():
    """
    Return a list of gift occasions to promote on the gift vouchers page.
    - Birthdays: always
    - Mother's Day (UK): ~4 weeks before to 1 week after
    - Father's Day (UK): ~4 weeks before to 1 week after
    - Christmas: from 1 November
    """
    today = date.today()
    year = today.year
    occasions = []

    # Always promote birthdays and anniversaries
    occasions.append({
        'slug': 'birthday',
        'name': "Birthday",
        'date': None,
        'promo': "Perfect birthday present",
    })
    occasions.append({
        'slug': 'anniversary',
        'name': "Anniversary",
        'date': None,
        'promo': "Perfect anniversary gift",
    })

    # Mother's Day (UK) - promote from 4 weeks before up to the day itself (not after)
    mothers_day = get_uk_mothers_day(year)
    window_start = mothers_day - timedelta(days=28)
    if window_start <= today <= mothers_day:
        occasions.append({
            'slug': 'mothers-day',
            'name': "Mother's Day",
            'date': mothers_day,
            'promo': f"The perfect Mother's Day experience — {mothers_day.strftime('%d %B %Y')}",
        })

    # Father's Day (UK) - promote from 4 weeks before up to the day itself (not after)
    fathers_day = get_uk_fathers_day(year)
    window_start = fathers_day - timedelta(days=28)
    if window_start <= today <= fathers_day:
        occasions.append({
            'slug': 'fathers-day',
            'name': "Father's Day",
            'date': fathers_day,
            'promo': f"The perfect Father's Day experience — {fathers_day.strftime('%d %B %Y')}",
        })

    # Christmas - from 1 November
    if today.month >= 11:
        occasions.append({
            'slug': 'christmas',
            'name': "Christmas",
            'date': date(year, 12, 25),
            'promo': "Give the gift of photography this Christmas",
        })

    return occasions


def workshop_calendar_date(dt):
    """
    UK wall-clock calendar date (YYYY-MM-DD) for a workshop datetime.

    Legacy gd_workshop rows are often naive local UK times; aware values are
    converted to Europe/London before taking the date.
    """
    if not dt:
        return ''
    if timezone.is_aware(dt):
        local = timezone.localtime(dt, UK_TZ)
    else:
        local = dt.replace(tzinfo=UK_TZ)
    return local.strftime('%Y-%m-%d')
