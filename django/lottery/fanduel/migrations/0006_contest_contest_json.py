# Generated by Django 2.2 on 2021-11-16 14:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fanduel', '0005_auto_20211109_1528'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='contest_json',
            field=models.TextField(blank=True, null=True),
        ),
    ]
