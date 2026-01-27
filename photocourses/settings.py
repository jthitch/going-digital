"""
Django settings for photocourses project.
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Try to use django-environ if available, otherwise use environment variables or defaults
try:
    import environ
    env = environ.Env(
        DEBUG=(bool, False)
    )
    environ.Env.read_env(os.path.join(BASE_DIR, '.env'))
    
    SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production')
    DEBUG = env('DEBUG', default=True)
    ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])
except ImportError:
    # Fallback if django-environ is not installed
    SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me-in-production')
    DEBUG = os.environ.get('DEBUG', 'True') == 'True'
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'jazzmin',  # Modern admin theme - must be before django.contrib.admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    
    # Third party (make optional)
    'rest_framework',
    # 'corsheaders',  # Optional - uncomment if installed
    
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
    # 'corsheaders.middleware.CorsMiddleware',  # Optional - uncomment if corsheaders installed
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'photocourses.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'photocourses.wsgi.application'

# Database
# Use SQLite for development, PostgreSQL for production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Uncomment for PostgreSQL in production:
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': env('DB_NAME', default='photocourses'),
#         'USER': env('DB_USER', default='postgres'),
#         'PASSWORD': env('DB_PASSWORD', default=''),
#         'HOST': env('DB_HOST', default='localhost'),
#         'PORT': env('DB_PORT', default='5432'),
#     }
# }

# Custom User Model
AUTH_USER_MODEL = 'core.User'

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

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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

# Email Configuration
try:
    EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
    EMAIL_HOST = env('EMAIL_HOST', default='')
    EMAIL_PORT = env('EMAIL_PORT', default=587)
    EMAIL_USE_TLS = env('EMAIL_USE_TLS', default=True)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@photocourses.com')
except NameError:
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
    EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@photocourses.com')

# CORS settings (for React components)
try:
    CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000'])
except NameError:
    cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000')
    CORS_ALLOWED_ORIGINS = cors_origins.split(',') if cors_origins else ['http://localhost:3000']
CORS_ALLOW_CREDENTIALS = True

# Jazzmin Admin Theme Configuration
JAZZMIN_SETTINGS = {
    # Title on the login screen
    "site_title": "Going Digital Admin",
    
    # Title on the brand (19 chars max)
    "site_header": "Going Digital",
    
    # Title on the brand when screen is <1200px (19 chars max)
    "site_brand": "Going Digital",
    
    # Logo to use for your site, must be present in static files
    "site_logo": None,  # You can add a logo later
    
    # Logo to use for login form
    "login_logo": None,
    
    # Logo to use for login form in dark themes
    "login_logo_dark": None,
    
    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle",
    
    # Relative path to a favicon for your site
    "site_icon": None,
    
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
    
    # Hide these models when generating side menu
    "hide_models": [],
    
    # List of apps (and/or models) to base side menu ordering off of
    "order_with_respect_to": ["courses", "website", "bookings", "franchises", "payments"],
    
    # Custom links to append to app groups, keyed on app name
    "custom_links": {
        "courses": [{
            "name": "View Courses",
            "url": "/courses/",
            "icon": "fas fa-camera",
            "new_window": True,
        }]
    },
    
    # Custom icons for side menu apps/models
    "icons": {
        "core": "fas fa-users-cog",
        "core.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "courses.Course": "fas fa-book",
        "courses.CourseInstance": "fas fa-calendar-alt",
        "courses.Instructor": "fas fa-chalkboard-teacher",
        "website": "fas fa-globe",
        "website.HeroImage": "fas fa-image",
        "website.Testimonial": "fas fa-quote-left",
        "website.BeforeAfterImage": "fas fa-images",
        "website.FAQ": "fas fa-question-circle",
        "bookings.Booking": "fas fa-ticket-alt",
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
    "custom_css": None,
    "custom_js": None,
    
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
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}
