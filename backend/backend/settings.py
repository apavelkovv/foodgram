import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / '.env')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set SECRET_KEY or enable DEBUG locally.')
    SECRET_KEY = 'development-only-foodgram-key-do-not-use-in-production'
ALLOWED_HOSTS = os.getenv(
    'ALLOWED_HOSTS', 'localhost,127.0.0.1,food-gram.sytes.net'
).split(',')
CSRF_TRUSTED_ORIGINS = list(
    filter(None, os.getenv('CSRF_TRUSTED_ORIGINS', '').split(','))
)
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'djoser',
    'users.apps.UsersConfig',
    'recipes.apps.RecipesConfig',
    'api.apps.ApiConfig',
    'django_cleanup.apps.CleanupConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'backend.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ]
        },
    }
]
WSGI_APPLICATION = 'backend.wsgi.application'
if os.getenv('USE_SQLITE', 'True').lower() == 'true':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.getenv('SQLITE_NAME', str(BASE_DIR / 'db.sqlite3')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['POSTGRES_DB'],
            'USER': os.environ['POSTGRES_USER'],
            'PASSWORD': os.environ['POSTGRES_PASSWORD'],
            'HOST': os.getenv('DB_HOST', 'db'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
AUTH_USER_MODEL = 'users.User'
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        )
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'MinimumLengthValidator'
        )
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        )
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        )
    },
]
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'collected_static'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DATA_DIR = Path(os.getenv('DATA_DIR', str(BASE_DIR.parent / 'data')))
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication'
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly'
    ],
    'DEFAULT_PAGINATION_CLASS': 'api.pagination.LimitPagePagination',
    'PAGE_SIZE': 6,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend'
    ],
}
DJOSER = {
    'HIDE_USERS': False,
    'SERIALIZERS': {
        'user_create': 'api.serializers.UserCreateSerializer',
        'user': 'api.serializers.UserSerializer',
        'current_user': 'api.serializers.UserSerializer',
    },
    'PERMISSIONS': {
        'user': ['rest_framework.permissions.AllowAny'],
        'user_list': ['rest_framework.permissions.AllowAny'],
    },
}
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = os.getenv('HTTPS_ENABLED', 'False').lower() == 'true'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT = SESSION_COOKIE_SECURE
if os.getenv('TRUST_PROXY', 'False').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECURE_REDIRECT_EXEMPT = [r'^health/$']
