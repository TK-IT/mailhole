"""
WSGI config for mailhole project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    with open(os.path.join(BASE_DIR, 'env.json')) as fp:
        os.environ.update(json.load(fp))

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mailhole.settings")

application = get_wsgi_application()
