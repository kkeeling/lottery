# Generated by Django 2.2 on 2021-11-23 15:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fanduel', '0007_contest_last_page_processed'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='slate_week',
            field=models.PositiveIntegerField(default=0, verbose_name='Week #'),
        ),
        migrations.AddField(
            model_name='contest',
            name='slate_year',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
