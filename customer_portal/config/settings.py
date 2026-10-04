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
    "api_client",
    "licenses",
    "installations",
    "support",
    "insights",
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
    "accounts.middleware.InactiveCustomerMiddleware",
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

AUTH_USER_MODEL = "accounts.CustomerUser"

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite3")

if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "sentinel_customer_portal"),
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
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
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
SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SECURE_COOKIES", "False") == "True"
CSRF_COOKIE_SECURE = os.environ.get("DJANGO_SECURE_COOKIES", "False") == "True"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Namespaced so this project's cookies never collide with the Vendor Portal's -
# see the matching comment in the Vendor Portal's settings.py for why this matters.
SESSION_COOKIE_NAME = "customer_sessionid"
CSRF_COOKIE_NAME = "customer_csrftoken"

# Session expires after 30 minutes idle, and on browser close — a reasonable
# default for an account/billing portal. Tune to taste.
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", str(60 * 30)))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

if os.environ.get("DJANGO_SECURE_COOKIES", "False") == "True":
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@sentinel.example.com")

# Sentinel Cloud API (hosted by the Vendor Portal) that this portal talks to.
# This portal never touches the Vendor Portal's database directly — every piece
# of license/subscription/installation data shown here comes from this API.
SENTINEL_CLOUD_URL = os.environ.get("SENTINEL_CLOUD_URL", "http://localhost:8001")
SENTINEL_CLOUD_TIMEOUT_SECONDS = float(os.environ.get("SENTINEL_CLOUD_TIMEOUT_SECONDS", "5"))
SENTINEL_CLOUD_MAX_RETRIES = int(os.environ.get("SENTINEL_CLOUD_MAX_RETRIES", "2"))

# Shared secret the Vendor Portal uses to call this project's /internal/provision/
# endpoint. Must match VENDOR_PROVISIONING_KEY in the Vendor Portal's .env.
# This is a server-to-server credential only - it authenticates "a request from
# our own Vendor Portal", never a customer, and is never exposed in any
# customer-facing view or template.
VENDOR_PROVISIONING_KEY = os.environ.get("VENDOR_PROVISIONING_KEY", "")

LICENSE_EXPIRING_SOON_DAYS = int(os.environ.get("LICENSE_EXPIRING_SOON_DAYS", "7"))

# Business Insights: a plain Python/statistics feature, independent of the
# Sentinel Cloud API above and of any LLM. Connects directly to a database
# server (its own "orders" table) and computes summary stats, trend, and
# simple z-score anomalies. Defaults to a bundled SQLite file so the demo
# works with zero setup; point it at a real Postgres server for production.
INSIGHTS_DB_ENGINE = os.environ.get("INSIGHTS_DB_ENGINE", "sqlite3")
INSIGHTS_DB_PATH = os.environ.get("INSIGHTS_DB_PATH", str(BASE_DIR / "insights_demo.sqlite3"))
INSIGHTS_DB_HOST = os.environ.get("INSIGHTS_DB_HOST", "localhost")
INSIGHTS_DB_PORT = os.environ.get("INSIGHTS_DB_PORT", "5432")
INSIGHTS_DB_NAME = os.environ.get("INSIGHTS_DB_NAME", "insights_demo")
INSIGHTS_DB_USER = os.environ.get("INSIGHTS_DB_USER", "postgres")
INSIGHTS_DB_PASSWORD = os.environ.get("INSIGHTS_DB_PASSWORD", "")
INSIGHTS_WINDOW_DAYS = int(os.environ.get("INSIGHTS_WINDOW_DAYS", "90"))
LOGIN_RATE_LIMIT_PER_MINUTE = int(os.environ.get("LOGIN_RATE_LIMIT_PER_MINUTE", "10"))

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
