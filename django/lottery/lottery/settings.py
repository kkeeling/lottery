# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

DEBUG = (os.environ.get('DEBUG', 'False') == 'true')

ALLOWED_HOSTS = [os.environ.get('HOSTNAME')]
HOSTNAME = os.environ.get('HOSTNAME')
SHORT_URL = os.environ.get('SHORT_URL')
SITE_ID = 1
APPEND_SLASH = True

DEFAULT_HOST = 'great-lotto.com'

CORS_ORIGIN_ALLOW_ALL = True

# SECURE_SSL_REDIRECT = True
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100000

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'lottery',
        'USER': 'lottery',
        'PASSWORD': 'lottery',
        'HOST': 'db',
        'AUTOCOMMIT': True
    }
}

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

WSGI_APPLICATION = 'lottery.wsgi.application'

ADMINS = (
    ('Keenan Keeling', 'keenan@gmail.com'),
    ('Mike Chyril', 'mike.chyril@gmail.com'),
)

STATIC_ROOT = "/opt/static/"
MEDIA_ROOT = "/opt/media/"

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'mcaic5mccxc4kel7l4iv%tb*&t9d=_j6i&hbhc8hrje@)z2)jy)zb='

# Application definition

INSTALLED_APPS = (
    'django.contrib.contenttypes',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'corsheaders',
    'django_celery_beat',
    'grappelli',
    'rest_framework',
    'django_admin_listfilter_dropdown',
    'rangefilter',
    'django_extensions',
    'configuration',
    'nfl',
    'fanduel',
    'yahoo',
    'nfl_sims',
)

MIDDLEWARE = (
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates'),],
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

ROOT_URLCONF = 'lottery.urls'

WSGI_APPLICATION = 'lottery.wsgi.application'

SITE_ID = 1

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_L10N = True

USE_TZ = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/
STATIC_URL = '/static/'
MEDIA_URL = '/media/'

LOGIN_URL = '/admin/login'

# Django Rest Framework ####
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '10/hour',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_BACKEND = 'redis://redis:6379/0'
CELERY_RESULT_EXPIRES = 60
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERYD_TASK_TIME_LIMIT = 30 #sec
CELERYD_TASK_SOFT_TIME_LIMIT = 30 #sec
USE_CELERY = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': "%(asctime)s.%(msecs).03d %(levelname)s [%(module)s:%(lineno)s] %(message)s",
            'datefmt': "%Y-%m-%d %H:%M:%S"
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
    },
    'root': {
        'handlers': ['console'],
        'propagate': True,
        'level': 'INFO',
    },
}

TEAM_COLORS = {
    'ARI': '#97233F',
    'ATL': '#A71930',
    'BAL': '#241773',
    'BUF': '#00338D',
    'CAR': '#0085CA',
    'CHI': '#0B162A',
    'CIN': '#FB4F14',
    'CLE': '#FB4F14',
    'DAL': '#B0B7BC',
    'DEN': '#002244',
    'DET': '#005A8B',
    'GB': '#203731',
    'HOU': '#03202F',
    'IND': '#002C5F',
    'JAC': '#006778',
    'KC': '#E31837',
    'LAC': '#0073CF',
    'LAR': '#002244',
    'LV': '#A5ACAF',
    'MIA': '#008E97',
    'MIN': '#4F2683',
    'NE': '#C60C30',
    'NO': '#9F8958',
    'NYG': '#0B2265',
    'NYJ': '#203731',
    'OAK': '#A5ACAF',
    'PHI': '#004953',
    'PIT': '#FFB612',
    'SF': '#AA0000',
    'SEA': '#69BE28',
    'TB': '#D50A0A',
    'TEN': '#4B92DB',
    'WAS': '#773141',
    
}

# Simulations
SIMULATION_SIZE = 10000