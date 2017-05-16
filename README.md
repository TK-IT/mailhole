Purgatory for hot mails
=======================

Hotmail har blokeret pulerau.

prodekanus kan sende mails til Hotmail via AU ITs mailservere.
Vi har ikke lyst til blindt at videresende via AU ITs mailservere,
da vi under ingen omstændigheder må sende spam ud fra disse.

Når pulerau modtager en mail til en TK-adresse eller tutor-adresse,
og denne mail skal viderestilles til en Hotmail-adresse,
sendes den i stedet til

    POST https://mailhole.tket.dk/api/submit/
    key=mailserver-private-api-token
    mail_from=nude.celebs@for.free
    rcpt_to=mathiasrav@hotmail.dk
    message_bytes=RFC2822 message data...

En bruger kan logge ind og se mails til sine designerede mailbokse
og markere hver som "spam" eller "videresend":

    | ⦻ | → | Fra            | Til           | Emne               |
    |[ ]|[ ]| ....           | ....          | ....               |
    |[ ]|[ ]| ....           | ....          | ....               |
    ...
    [Udfør]


Installation
============

Create `mailhole/settings/__init__.py` as follows:

```
from .common import *  # noqa

SECRET_KEY = r'''generate with pwgen -sy 50 1'''

DEBUG = True

DATABASES['default'] = {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': '...',
    'USER': '...',
    'PASSWORD': '...',
    'OPTIONS': {
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    },
}
```

**Make sure that you create your MySQL database with `CHARACTER SET utf8`.**
Character set utf8mb4 will not work since we have a unique `EmailField`,
and MySQL InnoDB old format with utf8mb4 can only handle indexes of fields
of 191 characters or less.

Install the requirements and mysqlclient with pip:

```
pyvenv mailhole-venv
. mailhole-venv/bin/activate
pip install 'django==1.11.1' 'django-macros==0.4.0' html2text mysqlclient
```

Run migrate, createsuperuser and runserver:

```
./manage.py migrate
./manage.py createsuperuser
./manage.py runserver
```
