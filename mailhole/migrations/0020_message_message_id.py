# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-01-25 16:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mailhole', '0019_mailbox_default_action'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='message_id',
            field=models.CharField(blank=True, db_index=True, max_length=190, null=True),
        ),
    ]
