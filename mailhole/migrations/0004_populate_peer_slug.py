# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-17 23:08
from __future__ import unicode_literals

from django.db import migrations


def populate_peer_slug(apps, schema_editor):
    Peer = apps.get_model('mailhole', 'Peer')
    for o in Peer.objects.all():
        if o.slug != '':
            continue
        if o.key.startswith('tk'):
            o.slug = 'tkammer'
            o.save()
        elif o.key.startswith('mf'):
            o.slug = 'mftutor'
            o.save()


class Migration(migrations.Migration):

    dependencies = [
        ('mailhole', '0003_peer_slug'),
    ]

    operations = [
        migrations.RunPython(populate_peer_slug),
    ]