"""Constants shared by legacy report sync and admin report queries."""

# New-site bookings live in the `bookings` table; legacy rows used gd_booking ids.
# Offset avoids overwriting historical report rows that share low numeric ids.
LEGACY_REPORT_BOOKING_ID_OFFSET = 10_000_000
