# Generated by Django 2.2 on 2022-03-30 12:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0067_auto_20220329_1521'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='racesimdriver',
            name='best_possible_speed',
        ),
        migrations.RemoveField(
            model_name='racesimdriver',
            name='worst_possible_speed',
        ),
    ]