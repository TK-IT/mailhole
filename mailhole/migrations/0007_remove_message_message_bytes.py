# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-17 23:29
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mailhole', '0006_populate_message_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='message',
            name='message_bytes',
        ),
    ]
