from pathlib import Path
import os
from dotenv import load_dotenv, find_dotenv
from django.contrib.messages import constants as messages

load_dotenv(find_dotenv())

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

BUILD_ENV = os.getenv("BUILD_ENV", default="local")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", default="127.0.0.1").split()

if os.getenv("CSRF_TRUSTED_ORIGINS"):
    CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS").split()

# Application definition

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth_suap",
    "tinymce",
    "crispy_forms",
    "crispy_bootstrap5",
    "django_htmx",
    "simple_menu",
    "django_tables2",
    "django_filters",
    "taggit",
]

LOCAL_APPS = [
    "users",
    "core",
    "presente.apps.PresenteConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
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


# Database
if BUILD_ENV == "local":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME"),
            "HOST": os.getenv("DB_HOST"),
            "PORT": os.getenv("DB_PORT"),
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
        }
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

if BUILD_ENV == "production":
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_POST = os.getenv("EMAIL_POST")
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by email
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Internationalization

LANGUAGE_CODE = "pt-BR"

TIME_ZONE = "America/Recife"

USE_I18N = True

USE_TZ = True

# Datetime input formats for forms
DATETIME_INPUT_FORMATS = [
    "%Y-%m-%dT%H:%M",  # HTML5 datetime-local format
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
]


# Static files (CSS, JavaScript, Images)

# URL para arquivos estáticos
STATIC_URL = "static/"
MEDIA_URL = "media/"

# Diretórios adicionais para arquivos estáticos
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Diretório onde os arquivos estáticos coletados serão armazenados
if BUILD_ENV == "local":
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"
else:
    STATIC_ROOT = os.getenv("STATIC_ROOT")
    MEDIA_ROOT = os.getenv("MEDIA_ROOT")


# Default primary key field type

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
X_FRAME_OPTIONS = "SAMEORIGIN"

SITE_ID = 1

# config users
AUTH_USER_MODEL = "users.User"
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "presente:index"
LOGOUT_REDIRECT_URL = "presente:index"

ACCOUNT_ADAPTER = "users.adapters.CustomAccountAdapter"
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_CHANGE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
OPEN_FOR_SIGNUP = True

ACCOUNT_FORMS = {
    "login": "users.forms.UserLoginForm",
    "reset_password": "users.forms.UserResetPasswordForm",
    "reset_password_from_key": "users.forms.UserResetPasswordKeyForm",
}

SOCIALACCOUNT_ADAPTER = "users.adapters.SuapSocialAccountAdapter"
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_PROVIDERS = {
    "suap": {
        "VERIFIED_EMAIL": True,
        "EMAIL_AUTHENTICATION": True,
        "SUAP_URL": "https://suap.ifrn.edu.br",
        "SCOPE": ["identificacao", "email"],
        "APP": {
            "client_id": os.getenv("SUAP_CLIENT_ID"),
            "secret": os.getenv("SUAP_CLIENT_SECRET"),
        },
    }
}


X_FRAME_OPTIONS = "SAMEORIGIN"

MESSAGE_TAGS = {
    messages.ERROR: "danger",
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MENU_SELECT_PARENTS = True

DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap5.html"
DJANGO_TABLES2_TABLE_ATTRS = {
    "class": "table table-striped",
}
