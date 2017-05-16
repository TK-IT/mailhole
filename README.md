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

En postmaster (f.eks. en fra TKs admingruppe) kan logge ind
og markere hver som "spam" eller "videresend":

    | ⦻ | → | Fra            | Til           | Emne               |
    |[ ]|[ ]| ....           | ....          | ....               |
    |[ ]|[ ]| ....           | ....          | ....               |
    ...
    [Udfør]


TODO
----

* Mulighed for white-listing af afsender
* Mulighed for white-listing på subject
* Når en mail kommer ind på API'et skal den sendes videre med det samme hvis den matcher whitelist
* HTTPS-API til batch-håndtering i editor
* Touch+small screen-venlig


Overvejelser
------------

Det nytter ikke noget at give BEST og tutorbest adgang til endnu et system
de skal logge ind på og huske at tjekke. Det er bedre at sætte Rav og FUHI
til det, for så har de et incitament til at finde en langtidsholdbar løsning!

Desuden er det mere effektivt at sætte nogle få personer til at gøre det
og udvikle et ekspert-system til det (f.eks. terminal-baseret, men det behøver
det ikke), end at sætte mange brugere til at bruge et mere brugervenligt system.

Endelig gør det at BEST og tutorbest ikke har endnu en ting at skulle sættes
ind i som en del af bestyrelsesarbejdet.

Branding: "TK-admingruppen og Tutorweb har indgået samarbejde med PostNord.
Samme services som før, men nu med et døgns forsinkelse ved levering til Hotmail!"


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
