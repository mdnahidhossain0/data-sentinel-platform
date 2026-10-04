import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-change-me-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# Origins allowed to POST here even when the browser's Origin/Referer differs
# from ALLOWED_HOSTS - required whenever this is reached through a proxy or
# tunnel that presents HTTPS to the browser (ngrok, a cloud IDE's forwarded
# port, a CDN, etc). Comma-separated, each entry needs a scheme, e.g.
# "https://myapp.example.com,https://myapp-preview.example.com".
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# Set only if a reverse proxy terminates TLS in front of this app and sets
# X-Forwarded-Proto - lets Django correctly see the request as HTTPS so
# secure cookies and CSRF work instead of silently failing.
if os.environ.get("DJANGO_BEHIND_HTTPS_PROXY", "False") == "True":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "customers",
    "plans",
    "licenses",
    "installations",
    "audit",
    "cloudapi",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.StaffUser"

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite3")

if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "sentinel_vendor"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SECURE_COOKIES", "False") == "True"
CSRF_COOKIE_SECURE = os.environ.get("DJANGO_SECURE_COOKIES", "False") == "True"

# Namespaced so this project's cookies never collide with the Customer Portal's.
# Browsers scope cookies by domain only, not port (RFC 6265) - two Django
# projects both running on "localhost" on different ports otherwise share one
# cookie jar, so logging into one can silently invalidate a login form already
# open on the other (a stale CSRF token -> 403 on submit).
SESSION_COOKIE_NAME = "vendor_sessionid"
CSRF_COOKIE_NAME = "vendor_csrftoken"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# HSTS and SSL redirect are off by default so local/dev HTTP still works.
# Set DJANGO_SECURE_COOKIES=True (behind HTTPS) in production to enable all of this.
if os.environ.get("DJANGO_SECURE_COOKIES", "False") == "True":
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "structured"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

LICENSE_SIGNING_PRIVATE_KEY_B64 = os.environ.get("LICENSE_SIGNING_PRIVATE_KEY_B64", "")
LICENSE_PUBLIC_KEY_B64 = "sDeNfpuuBjSPWNNrR+sHSR/oOhrTfAqGpjfEHRzDF4s="

# The Customer Portal that this Vendor Portal provisions customer accounts onto.
# The Vendor Portal is the sole source of truth for customer identity: creating,
# suspending, or reactivating a customer here pushes that state to the Customer
# Portal via a small internal, server-to-server endpoint — never the other way
# around, and never through anything the customer can trigger themselves.
CUSTOMER_PORTAL_URL = os.environ.get("CUSTOMER_PORTAL_URL", "http://localhost:8000")
VENDOR_PROVISIONING_KEY = os.environ.get("VENDOR_PROVISIONING_KEY", "")

INSTALLATION_OFFLINE_AFTER_MINUTES = int(os.environ.get("INSTALLATION_OFFLINE_AFTER_MINUTES", "180"))
CHECK_IN_INTERVAL_SECONDS = int(os.environ.get("CHECK_IN_INTERVAL_SECONDS", "3600"))

RATE_LIMIT_CHECKIN_PER_MINUTE = int(os.environ.get("RATE_LIMIT_CHECKIN_PER_MINUTE", "30"))
