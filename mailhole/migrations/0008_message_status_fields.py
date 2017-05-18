# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-18 00:10
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mailhole', '0007_remove_message_message_bytes'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='status_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='message',
            name='status_on',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
