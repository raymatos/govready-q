# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-06-17 16:15
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('guidedmodules', '0007_auto_20160616_1912'),
    ]

    operations = [
        migrations.RenameField(
            model_name='taskanswerhistory',
            old_name='value',
            new_name='stored_value',
        ),
    ]