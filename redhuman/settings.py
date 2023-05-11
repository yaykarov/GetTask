﻿"""
Django settings for redhuman project.

Generated by 'django-admin startproject' using Django 1.10.1.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import datetime
import os
import os.path as op
import sys
import environ
from pathlib import Path

env = environ.Env()
environ.Env.read_env()

SITE_ID = 1

COMPANY_NAME = 'ГЕТТАСК'

BASE_DIR = op.abspath(op.join(op.dirname(__file__), '..'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
DEBUG_TOOLBAR = DEBUG

REST_HANDLE_500 = True

ALLOWED_HOSTS = ['127.0.0.1']

DATA_UPLOAD_MAX_NUMBER_FIELDS = 4096

# Application definition

log_dir = Path(__file__).resolve().parent / 'logs'
log_dir.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'action': {
            'format': '%(levelname)1.1s :: %(asctime)s :: %(message)s',
            'class': 'utils.date_time.UTCFormatter',
        }
    },
    'handlers': {
        'console_db': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'action',
        },
        'action': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'action',
            'filename': log_dir / 'action.log',
            'delay': True,
            'when': 'midnight',
            'utc': True,
            'backupCount': 14,
            'encoding': 'utf-8',
        }
    },
    'loggers': {
#        'django.db.backends': {
#            'handlers': [
#                'console_db',
#            ],
#            'filters': ['require_debug_true'],
#            'propagate': False,
#            'level': 'DEBUG'
#        },
        'the_redhuman_is.services.delivery.actions': {
            'handlers': [
                'action',
            ],
            'level': 'INFO',
        },
    }
}

INSTALLED_APPS = [
    'adminsortable2',
    'bootstrap_daterangepicker',
    'bootstrap_datepicker_plus',
    'constance',
    'corsheaders',
    'crispy_forms',
    'dal',
    'dal_select2',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'django_telegrambot',
    'huey.contrib.djhuey',
    'import_export',
    'massadmin',
    'mathfilters',
    'rangefilter',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'telegram_bot',

    # Our apps
    'applicants',
    'async_utils',
    'doc_templates',
    'finance',
    'import1c',
    'redhuman',
    'redis_sessions', # Todo: find out, wtf is this
    'the_redhuman_is',
    'utils',

    # The following block order is important, it is for wiki module
    'django.contrib.sites.apps.SitesConfig',
    'django.contrib.humanize.apps.HumanizeConfig',
    'django_nyt.apps.DjangoNytConfig',
    'mptt',
#    'sekizai',
    'sorl.thumbnail',
#    'wiki.apps.WikiConfig',
#    'wiki.plugins.attachments.apps.AttachmentsConfig',
#    'wiki.plugins.notifications.apps.NotificationsConfig',
#    'wiki.plugins.images.apps.ImagesConfig',
#    'wiki.plugins.macros.apps.MacrosConfig',
]

MIDDLEWARE = [
    # should be placed as high as possible
    'corsheaders.middleware.CorsMiddleware',

    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'redhuman.middleware.RestrictAccess',
]

ROOT_URLCONF = 'redhuman.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            op.join(op.dirname(__file__), 'templates'),
            op.join(BASE_DIR, 'frontend/internal/build'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'constance.context_processors.config',
#                'sekizai.context_processors.sekizai',
            ],
        },
    },
]

WSGI_APPLICATION = 'redhuman.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'redhuman',
        'USER': 'redhuman',
        'PASSWORD': 'pswpswpsw',
        'HOST': 'localhost',
        'PORT': '',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'ru-RU'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_L10N = True

USE_TZ = True

SHORT_DATE_FORMAT = 'd.m.Y'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = op.join(BASE_DIR, 'public', 'static')

STATICFILES_DIRS = [
    op.join(BASE_DIR, 'applicants', 'static'),
    op.join(BASE_DIR, 'redhuman', 'static'),
    op.join(BASE_DIR, 'the_redhuman_is', 'static'),

    op.join(BASE_DIR, 'frontend/internal/build/static'),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = op.join(BASE_DIR, 'public', 'media')

THUMBNAIL_DEBUG = True

LOGIN_REDIRECT_URL = '/'

FILE_UPLOAD_HANDLERS = (
    "django_excel.ExcelMemoryFileUploadHandler",
    "django_excel.TemporaryExcelFileUploadHandler",
)
FILE_UPLOAD_PERMISSIONS = 0o644

SESSION_ENGINE = 'redis_sessions.session'
SESSION_REDIS_URL = 'redis://127.0.0.1:6379/0'
SESSION_REDIS_PREFIX = 'redhuman_session'
SESSION_SERIALIZER = 'redis_sessions.serializers.UjsonSerializer'
SESSION_REDIS_JSON_ENCODING = 'utf8'

CONSTANCE_REDIS_CONNECTION = SESSION_REDIS_URL
CONSTANCE_REDIS_PREFIX = 'redhuman_constance:'

CONSTANCE_BACKEND = 'constance.backends.redisd.RedisBackend'
CONSTANCE_CONFIG = {
    'CONTRACT_EDGE_DAYS': (
        4, 'Количество дней до окончания договора, когда изменять статус', int
    ),
    'MIN_TURNOUTS': (
        3, 'Минимальное количество выходов на работу для создания УОЗ', int
    ),
    'MIN_TURNOUTS_WITHIN_DAYS': (
        7, 'Промежуток из количества дней, в котором считать минимальное '
           'число выходов на работу', int
    ),
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# how many days to store notices zip files
NOTICE_ZIP_STORE_DAYS = 1

CRISPY_TEMPLATE_PACK = 'bootstrap4'

WIKI_ATTACHMENTS_EXTENSIONS = [
    'pdf', 'doc', 'odt', 'docx', 'txt',
    'xls', 'xlsx', 'csv', 'sh', 'py'
]

# djangorestframework

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated'
    ],
    'EXCEPTION_HANDLER': 'the_redhuman_is.views.utils.rest_exception_handler',
}

# djangorestframework_simplejwt

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': datetime.timedelta(days=61),
    'REFRESH_TOKEN_LIFETIME': datetime.timedelta(days=90),
}

# HUEY

HUEY = {
    'immediate': False
}

# django-cors-headers

CORS_EXPOSE_HEADERS = [
    'Content-Disposition',
]
CORS_ORIGIN_ALLOW_ALL = False
CORS_ORIGIN_WHITELIST = [
    'https://gettask.ru',
    'https://lk.gettask.ru',
    'http://lk.ozbs.ru',
    'http://localhost:3000',
    'http://localhost:3001',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:3001',
]

'''
!!!Настройки телеграмма тестовые.!!!
'''

# Todo: move to some more suitable location
SITE_NAME = 'work.redhuman.ru'

TELEGRAM_WEBHOOK_URL = 'https://'

OFFICE_TELEGRAMBOT_TOKEN = None
CHAT_TELEGRAMBOT_TOKEN = None
ALERTS_TELEGRAMBOT_TOKEN = None


'''

##########################################################
!!!         все настройки писать выше этих строк       !!!
##########################################################
!!! локальные настройки писать в файл settings_local.py!!!
##########################################################

'''
try:
    from .settings_local import *
except ImportError:
    pass

if DEBUG_TOOLBAR:
    try:
        import debug_toolbar
    except ImportError:
        pass
    else:

        def show_toolbar(request):
            return not request.is_ajax()

        INSTALLED_APPS.append('debug_toolbar')
        INTERNAL_IPS = ['127.0.0.1', ]
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        DEBUG_TOOLBAR_CONFIG = {
           'SHOW_TOOLBAR_CALLBACK': 'redhuman.settings.show_toolbar',
        }

DJANGO_TELEGRAMBOT = { 'WEBHOOK_PREFIX': 'telegram_bot' }

_BOTS = [
    {'TOKEN': T}
    for T in [
        OFFICE_TELEGRAMBOT_TOKEN,
        CHAT_TELEGRAMBOT_TOKEN,
        ALERTS_TELEGRAMBOT_TOKEN
    ] if T
]

if len(_BOTS) > 0:
    DJANGO_TELEGRAMBOT = {
        'MODE': 'WEBHOOK',
        'WEBHOOK_SITE': TELEGRAM_WEBHOOK_URL,
        'WEBHOOK_PREFIX': 'telegram_bot',
        'BOTS': _BOTS
    }
