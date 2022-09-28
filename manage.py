#!/usr/bin/env python
import json
import os
import sys

if __name__ == "__main__":
    if 'DJANGO_SETTINGS_MODULE' not in os.environ:
        with open('env.json') as fp:
            os.environ.update(json.load(fp))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mailhole.settings")
    try:
        with open(os.path.dirname(__file__) + '/../automysql.py') as fp:
            exec(fp.read(), {})
    except FileNotFoundError:
        pass
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise
    execute_from_command_line(sys.argv)
