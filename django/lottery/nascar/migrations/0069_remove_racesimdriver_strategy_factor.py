# Generated by Django 2.2 on 2022-03-30 12:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0068_auto_20220330_1239'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='racesimdriver',
            name='strategy_factor',
        ),
    ]
