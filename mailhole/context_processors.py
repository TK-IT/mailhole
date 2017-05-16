from django.conf import settings


def vars(request):
    return {
        'SITE_NAME': settings.SITE_NAME,
        'MANAGER_NAME': settings.MANAGER_NAME,
        'BLANK_SUBJECT': '(intet emne)',
    }
