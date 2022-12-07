import os

import environ
from celery.schedules import crontab

BASE_DIR = environ.Path(__file__) - 2

env = environ.Env()

env_file = str(BASE_DIR.path('.env'))
if os.path.exists(env_file):
    env.read_env(env_file)

SECRET_KEY = 'dq%c%l^&=+p_s$fd8=q+_7s$q(^xs0c45*vj_)&y48nrx*tpsd'
DEBUG = env.bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=[])
REDIS_URL = env.str('REDIS_URL', 'redis://localhost:6379/1')

INSTALLED_APPS = [
    'admin_views',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'computedfields',
    'django_extensions',
    'dynamic_preferences',
    'adminsortable2',
    'bootstrap4',

    'app',
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

ROOT_URLCONF = 'evosbot.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [str(BASE_DIR.path('templates'))],
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

WSGI_APPLICATION = 'evosbot.wsgi.application'

DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///db.sqlite3'),
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATICFILES_DIRS = [
    str(BASE_DIR.path('static')),
]

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

PUBLIC_ROOT = BASE_DIR.path('public')
STATIC_URL = '/static/'
STATIC_ROOT = str(PUBLIC_ROOT.path('static'))

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
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
        },
        'console_debug_false': {
            'level': 'WARNING',
            'filters': ['require_debug_false'],
            'class': 'logging.StreamHandler',
        },
        'tx': {
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR.path('logs', 'tx.log')),
            'formatter': 'csv',
        },
        'rank': {
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR.path('logs', 'rank.log')),
            'formatter': 'csv',
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'csv': {
            'format': '{asctime},{message}',
            'style': '{',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'console_debug_false'],
            'level': 'WARNING',
        },
        'django': {
            'handlers': ['console', 'console_debug_false'],
            'level': 'INFO',
        },
        'tx': {
            'handlers': ['tx', 'console', 'console_debug_false'],
            'level': 'INFO',
        },
        'rank': {
            'handlers': ['rank', 'console', 'console_debug_false'],
            'level': 'INFO',
        },
        'discord': {
            'handlers': ['console', 'console_debug_false'],
            'level': 'INFO',
        },
    },
}

CELERY_IMPORTS = 'app.tasks'
CELERY_BROKER_URL = REDIS_URL
CELERY_WORKER_CONCURRENCY = 4
CELERY_BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 60*60*24}
CELERY_BEAT_SCHEDULE = {
    'airdrop_plan': {
        'task': 'app.tasks.airdrop_plan',
        'schedule': crontab(minute='0', hour='0'),
    },
    'check_deposits': {
        'task': 'app.tasks.check_deposits',
        'schedule': crontab(),
    },
    'check_staking_pool_rewards': {
        'task': 'app.tasks.check_staking_pool_rewards',
        'schedule': crontab(),
    },
    'process_unstaking': {
        'task': 'app.tasks.process_unstaking',
        'schedule': crontab(),
    },
    'update_pos_settings': {
        'task': 'app.tasks.update_pos_settings',
        'schedule': crontab(minute='0', hour='*/12'),
    },
    'check_masternode_rewards': {
        'task': 'app.tasks.check_masternode_rewards',
        'schedule': crontab(),
    },
    'process_mn_withdraws': {
        'task': 'app.tasks.process_mn_withdraws',
        'schedule': crontab(minute='*/2'),
    },
    'masternode_create': {
        'task': 'app.tasks.masternode_create',
        'schedule': crontab(minute='*/5'),
    },
    'update_activity': {
        'task': 'app.tasks.update_activity',
        'schedule': crontab(),
    },
    'update_ranks': {
        'task': 'app.tasks.update_ranks',
        'schedule': crontab(),
    },
    'lottery': {
        'task': 'app.tasks.lottery',
        'schedule': crontab(),
    },
    'usernode_create': {
        'task': 'app.tasks.usernode_create',
        'schedule': crontab(minute='0', hour='*'),
    },
    'usernode_rewards': {
        'task': 'app.tasks.usernode_rewards',
        'schedule': crontab(minute='*/15'),
    },
    'load_markets_data': {
        'task': 'app.tasks.load_markets_data',
        'schedule': crontab(minute='*/5'),
    },
    'check_tracked_mns': {
        'task': 'app.tasks.check_tracked_mns',
        'schedule': crontab(minute='*/5'),
    },
}
CELERY_ONCE = {
    'backend': 'celery_once.backends.Redis',
    'settings': {
        'url': REDIS_URL,
        'default_timeout': 60 * 60,
    }
}
