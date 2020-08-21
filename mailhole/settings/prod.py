from .common import *

ADMINS = (
    ('Mathias Rav', 'rav@cs.au.dk'),
)

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = False

STATIC_ROOT = os.path.join(BASE_DIR, 'prodekanus/static')
MEDIA_ROOT = os.path.join(BASE_DIR, 'prodekanus/uploads')

ALLOWED_HOSTS = ['mail.tket.dk']

# Update database configuration with $DATABASE_URL.
import dj_database_url
db_from_env = dj_database_url.config(conn_max_age=500)
DATABASES['default'].update(db_from_env)
if DATABASES['default']['ENGINE'] == 'django.db.backends.mysql':
    DATABASES['default'].setdefault('OPTIONS', {})['init_command'] = (
        "SET sql_mode='STRICT_TRANS_TABLES'")

EMAIL_HOST = 'localhost'
DEFAULT_FROM_EMAIL = SERVER_EMAIL = 'admin@TAAGEKAMMERET.dk'.lower()

# EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
# EMAIL_FILE_PATH = os.path.join(BASE_DIR, 'django-email')

# EMAIL_HOST = 'smtp-clients.au.dk'
# EMAIL_HOST_USER = 'au306325@uni.au.dk'
# from base64 import b64decode as _b64decode
# EMAIL_HOST_PASSWORD = _b64decode(...)
# EMAIL_PORT = 587
# EMAIL_USE_TLS = False
# EMAIL_USE_SSL = False
# EMAIL_TIMEOUT = 5

_logfile = os.path.join(BASE_DIR, 'prodekanus',
                        'django-%s.log' % pwd.getpwuid(os.geteuid()).pw_name)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': ('[%(asctime)s %(name)s %(levelname)s] ' +
                       '%(message)s'),
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': _logfile,
            'formatter': 'simple',
            'encoding': 'utf-8',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'mail_admins'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'WARNING'),
        },
        'mailhole': {
            'handlers': ['file', 'mail_admins'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'DEBUG'),
        },
    },
}

NO_OUTGOING_EMAIL = True
REQUIRE_FROM_REWRITING = True
