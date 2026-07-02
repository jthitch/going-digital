"""
Django settings for photocourses project.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Some tools (e.g. Cursor) set SSLKEYLOGFILE to a virtual path Python cannot write.
# That makes every HTTPS call fail with PermissionError, including Stripe API requests.
_ssl_keylog = os.environ.get('SSLKEYLOGFILE', '')
if _ssl_keylog.startswith('\\\\?\\Volume'):
    os.environ.pop('SSLKEYLOGFILE', None)

# Try to use django-environ if available, otherwise use environment variables or defaults
try:
    import environ
    env = environ.Env(
        DEBUG=(bool, False)
    )
    environ.Env.read_env(os.path.join(BASE_DIR, '.env'))
    
    SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production')
    DEBUG = env('DEBUG', default=True)
    ALLOWED_HOSTS = env.list(
        'ALLOWED_HOSTS',
        default=[
            'localhost',
            '127.0.0.1',
            'goingdigital.co.uk',
            'www.goingdigital.co.uk',
            'staging.goingdigital.co.uk',
        ],
    )
    # Passcode gate for non-public environments (see website.middleware /dev-access/).
    DEV_SITE_PASSWORD = env('DEV_SITE_PASSWORD', default='')
    DEV_SITE_ACCESS_ENABLED = env.bool('DEV_SITE_ACCESS_ENABLED', default=DEBUG)
except ImportError:
    # Fallback if django-environ is not installed
    SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me-in-production')
    DEBUG = os.environ.get('DEBUG', 'True') == 'True'
    ALLOWED_HOSTS = os.environ.get(
        'ALLOWED_HOSTS',
        'localhost,127.0.0.1,goingdigital.co.uk,www.goingdigital.co.uk,staging.goingdigital.co.uk',
    ).split(',')
    DEV_SITE_PASSWORD = os.environ.get('DEV_SITE_PASSWORD', '')
    DEV_SITE_ACCESS_ENABLED = os.environ.get(
        'DEV_SITE_ACCESS_ENABLED',
        'True' if DEBUG else 'False',
    ).lower() in ('1', 'true', 'yes')

# Application definition
INSTALLED_APPS = [
    'jazzmin',  # Modern admin theme - must be before django.contrib.admin
    'ckeditor',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    
    # Third party
    'rest_framework',
    'django_recaptcha',

    # Local apps
    'core',
    'courses',
    'website',
    'bookings',
    'franchises',
    'payments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'website.middleware.DevSiteAccessMiddleware',
    'django.middleware.common.CommonMiddleware',
    'website.middleware.RedirectMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.CustomerAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'photocourses.urls'

_template_context_processors = [
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'bookings.context_processors.basket_context',
    'website.context_processors.google_reviews',
    'website.context_processors.newsletter_modal',
]
if DEBUG:
    _template_context_processors.insert(0, 'django.template.context_processors.debug')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': _template_context_processors,
        },
    },
]

WSGI_APPLICATION = 'photocourses.wsgi.application'


def _mysql_database_config():
    """Single MySQL/MariaDB config (django-environ or plain os.environ)."""
    try:
        return {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': env('DB_NAME', default='photocourses'),
            'USER': env('DB_USER', default='root'),
            'PASSWORD': env('DB_PASSWORD', default=''),
            'HOST': env('DB_HOST', default='localhost'),
            'PORT': env('DB_PORT', default='3306'),
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    except NameError:
        return {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'photocourses'),
            'USER': os.environ.get('DB_USER', 'root'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {'charset': 'utf8mb4'},
        }


DATABASES = {'default': _mysql_database_config()}

# Custom User Model (maps to gd_user table)
AUTH_USER_MODEL = 'core.User'

# Auth backend: login by email
AUTHENTICATION_BACKENDS = ['core.backends.EmailBackend']
LOGIN_URL = 'account:login'
LOGIN_REDIRECT_URL = 'account:my_bookings'

# Password hashers: PBKDF2 for new passwords (createsuperuser, set_password),
# bcrypt for verifying legacy gd_user passwords
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'core.hashers.BcryptPasswordHasher',
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# reCAPTCHA (get keys at https://www.google.com/recaptcha/admin)
try:
    RECAPTCHA_PUBLIC_KEY = env('RECAPTCHA_PUBLIC_KEY', default='')
    RECAPTCHA_PRIVATE_KEY = env('RECAPTCHA_PRIVATE_KEY', default='')
except NameError:
    RECAPTCHA_PUBLIC_KEY = os.environ.get('RECAPTCHA_PUBLIC_KEY', '')
    RECAPTCHA_PRIVATE_KEY = os.environ.get('RECAPTCHA_PRIVATE_KEY', '')

# Silence reCAPTCHA test-key warning when using Google's test keys for local development
SILENCED_SYSTEM_CHECKS = ['django_recaptcha.recaptcha_test_key_error']

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CKEditor - rich text for admin content fields (bold, font size, etc. without writing HTML)
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': [
            ['Styles', 'Format', 'Font', 'FontSize'],
            ['Bold', 'Italic', 'Underline', 'Strike'],
            ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent'],
            ['Link', 'Unlink'],
            ['RemoveFormat'],
        ],
        'height': 300,
        'width': '100%',
    },
    'legal': {
        'toolbar': [
            ['Styles', 'Format'],
            ['Bold', 'Italic', 'Underline'],
            ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent'],
            ['Link', 'Unlink', 'Anchor'],
            ['RemoveFormat', 'Source'],
        ],
        'height': 500,
        'width': '100%',
    },
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20
}

# Stripe Configuration
try:
    STRIPE_PUBLIC_KEY = env('STRIPE_PUBLIC_KEY', default='')
    STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
    STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')
except NameError:
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Google Places API (optional — live homepage review rating sync)
try:
    GOOGLE_PLACES_API_KEY = env('GOOGLE_PLACES_API_KEY', default='').strip()
    GOOGLE_PLACE_ID = env('GOOGLE_PLACE_ID', default='').strip()
except NameError:
    GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY', '').strip()
    GOOGLE_PLACE_ID = os.environ.get('GOOGLE_PLACE_ID', '').strip()

# Email Configuration
try:
    EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
    EMAIL_HOST = env('EMAIL_HOST', default='')
    EMAIL_PORT = env.int('EMAIL_PORT', default=587)
    EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@photocourses.com')
    SERVER_EMAIL = env('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)
    CONTACT_EMAIL = env('CONTACT_EMAIL', default='info@goingdigital.co.uk')
    SITE_URL = env('SITE_URL', default='http://127.0.0.1:8000')
    GOING_DIGITAL_FACEBOOK_GROUP_URL = env('GOING_DIGITAL_FACEBOOK_GROUP_URL', default='')
    GETADDRESS_API_KEY = env('GETADDRESS_API_KEY', default='')
    EMAIL_SUPPRESS_RECIPIENTS = [
        addr.strip().lower()
        for addr in env('EMAIL_SUPPRESS_RECIPIENTS', default='').split(',')
        if addr.strip()
    ]
    EMAIL_FRANCHISEE_BCC_ENABLED = env.bool('EMAIL_FRANCHISEE_BCC_ENABLED', default=True)
except NameError:
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
    EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@photocourses.com')
    SERVER_EMAIL = os.environ.get('SERVER_EMAIL', DEFAULT_FROM_EMAIL)
    CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'info@goingdigital.co.uk')
    SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000')
    GOING_DIGITAL_FACEBOOK_GROUP_URL = os.environ.get('GOING_DIGITAL_FACEBOOK_GROUP_URL', '')
    GETADDRESS_API_KEY = os.environ.get('GETADDRESS_API_KEY', '')
    EMAIL_SUPPRESS_RECIPIENTS = [
        addr.strip().lower()
        for addr in os.environ.get('EMAIL_SUPPRESS_RECIPIENTS', '').split(',')
        if addr.strip()
    ]
    EMAIL_FRANCHISEE_BCC_ENABLED = os.environ.get('EMAIL_FRANCHISEE_BCC_ENABLED', 'True').lower() in (
        '1', 'true', 'yes', 'on',
    )

# Jazzmin Admin Theme Configuration
JAZZMIN_SETTINGS = {
    # Title on the login screen
    "site_title": "Going Digital Admin",
    
    # Title on the brand (19 chars max)
    "site_header": "Going Digital",
    
    # Title on the brand when screen is <1200px (19 chars max)
    "site_brand": "Going Digital",
    
    # Logo to use for your site, must be present in static files
    "site_logo": "img/logo/logo-dark.png",
    
    # Logo to use for login form
    "login_logo": "img/logo/logo-dark.png",
    
    # Logo to use for login form in dark themes
    "login_logo_dark": "img/logo/logo-dark.png",
    
    # img-fluid lets wide logos scale properly; img-circle can distort non-square logos
    "site_logo_classes": "img-fluid",
    
    # Favicon for browser tab (ideally 32x32px)
    "site_icon": "img/favicon/favicon.png",
    
    # Welcome text on the login screen
    "welcome_sign": "Welcome to Going Digital Admin",
    
    # Copyright on the footer
    "copyright": "Going Digital",
    
    # The model admin to search from the search bar
    "search_model": ["core.User", "courses.Course"],
    
    # Field name on user model that contains avatar ImageField/URLField
    "user_avatar": None,
    
    ############
    # Top Menu #
    ############
    
    # Links to put along the top menu
    "topmenu_links": [
        # Url that gets reversed (Permissions can be added)
        {"name": "Home", "url": "admin:index", "permissions": ["core.view_user"]},
        
        # External url that opens in a new window (Permissions can be added)
        {"name": "View Site", "url": "/", "new_window": True},
        
        # model admin to link to (Permissions checked against model)
        {"model": "core.User"},
        
        # App with dropdown menu to all its models pages (Permissions checked against models)
        {"app": "courses"},
    ],
    
    #############
    # User Menu #
    #############
    
    # Additional links to include in the user menu on the top right
    "usermenu_links": [
        {"name": "View Site", "url": "/", "new_window": True},
        {"model": "core.user"}
    ],
    
    #############
    # Side Menu #
    #############
    
    # Whether to display the side menu
    "show_sidebar": True,
    
    # Whether to aut expand the menu
    "navigation_expanded": True,
    
    # Hide these apps when generating side menu
    "hide_apps": [],
    
    # Hide these models when generating side menu (Content editable under Courses)
    "hide_models": ["courses.Content"],
    
    # List of apps (and/or models) to base side menu ordering off of
    # Course first, then Category & Skill Level grouped under Courses for cleaner dashboard
    "order_with_respect_to": [
        "courses",
        "courses.Course",
        "courses.CourseCategory",
        "courses.CourseSkillLevel",
        "courses.Workshop",
        "courses.Instructor",
        "courses.Image",
        "website",
        "website.HeroImage",
        "website.GiftVoucherPageImage",
        "website.GiftCardDesign",
        "website.NewsletterModalSettings",
        "website.GoogleReviewsSettings",
        "website.LegalPage",
        "bookings",
        "franchises",
        "payments",
    ],
    
    "custom_links": {
        "bookings": [
            {
                "name": "Reports",
                "url": "admin:bookings_reports",
                "icon": "fas fa-chart-bar",
            },
        ],
    },
    
    # Custom icons for side menu apps/models
    "icons": {
        "core": "fas fa-users-cog",
        "core.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "courses.Course": "fas fa-book",
        "courses.Workshop": "fas fa-calendar-alt",
        "courses.Instructor": "fas fa-chalkboard-teacher",
        "website": "fas fa-globe",
        "website.HeroImage": "fas fa-image",
        "website.GiftVoucherPageImage": "fas fa-gift",
        "website.GiftCardDesign": "fas fa-id-card",
        "website.NewsletterModalSettings": "fas fa-envelope-open-text",
        "website.GoogleReviewsSettings": "fab fa-google",
        "website.LegalPage": "fas fa-file-contract",
        "website.Testimonial": "fas fa-quote-left",
        "website.BeforeAfterImage": "fas fa-images",
        "website.FAQ": "fas fa-question-circle",
        "bookings": "fas fa-ticket-alt",
        "bookings.Booking": "fas fa-ticket-alt",
        "bookings.Voucher": "fas fa-gift",
        "franchises.Franchise": "fas fa-building",
        "franchises.Location": "fas fa-map-marker-alt",
        "payments.Payment": "fas fa-credit-card",
    },
    
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    
    #################
    # Related Modal #
    #################
    # Use modals instead of popups
    # Disabled due to connection issues - using traditional popups instead
    "related_modal_active": False,
    
    #############
    # UI Tweaks #
    #############
    # Relative paths to custom CSS/JS scripts (must be present in static files)
    "custom_css": "admin/css/jazzmin-admin.css",
    "custom_js": "admin/js/jazzmin-admin.js",
    
    # Whether to link font from fonts.googleapis.com
    "use_google_fonts_cdn": True,
    
    # Whether to show the UI customizer on the sidebar
    "show_ui_builder": False,
    
    ###############
    # Change view #
    ###############
    # Render out the change view as a single form, or in tabs, current options are
    # - single
    # - horizontal_tabs (default)
    # - vertical_tabs
    # - collapsible
    # - carousel
    "changeform_format": "horizontal_tabs",
    
    # override change forms on a per modeladmin basis
    "changeform_format_overrides": {
        "core.user": "collapsible",
        "auth.group": "vertical_tabs"
    },
    
    # Add a language dropdown into the admin
    "language_chooser": False,
}

# Jazzmin UI Tweaks
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": False,
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-light-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    # Follow OS light/dark preference via data-bs-theme (Jazzmin 3.0.4+)
    "default_theme_mode": "auto",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

# Production: HTTPS, secure cookies, HSTS (only when DEBUG is False)
if not DEBUG:
    try:
        SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
        SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)
        SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
        SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)
        CSRF_TRUSTED_ORIGINS = env.list(
            'CSRF_TRUSTED_ORIGINS',
            default=[
                'https://goingdigital.co.uk',
                'https://www.goingdigital.co.uk',
                'https://staging.goingdigital.co.uk',
            ],
        )
        USE_PROXY_SSL = env.bool('USE_PROXY_SSL', default=False)
    except NameError:
        SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('1', 'true', 'yes')
        SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
        SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get(
            'SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True'
        ).lower() in ('1', 'true', 'yes')
        SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'False').lower() in ('1', 'true', 'yes')
        _csrf = os.environ.get(
            'CSRF_TRUSTED_ORIGINS',
            'https://goingdigital.co.uk,https://www.goingdigital.co.uk,https://staging.goingdigital.co.uk',
        )
        CSRF_TRUSTED_ORIGINS = [x.strip() for x in _csrf.split(',') if x.strip()]
        USE_PROXY_SSL = os.environ.get('USE_PROXY_SSL', 'False').lower() in ('1', 'true', 'yes')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    if USE_PROXY_SSL:
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_SSL_REDIRECT = False

_INSECURE_SECRET_KEYS = frozenset({
    'django-insecure-change-me-in-production',
    'change-me-in-production',
})
if not DEBUG and SECRET_KEY in _INSECURE_SECRET_KEYS:
    raise ImproperlyConfigured(
        'Set a unique SECRET_KEY environment variable before running with DEBUG=False.'
    )

# In-process cache (redirect lookups, safe for single-server; use Redis/Memcached in multi-worker prod)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'goingdigital',
    }
}
