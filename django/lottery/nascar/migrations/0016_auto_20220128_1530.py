# Generated by Django 2.2 on 2022-01-28 15:30

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0015_auto_20220127_1300'),
    ]

    operations = [
        migrations.RenameField(
            model_name='racesimdriver',
            old_name='best_fp',
            new_name='best_speed_rank',
        ),
        migrations.RenameField(
            model_name='racesimdriver',
            old_name='worst_fp',
            new_name='worst_speed_rank',
        ),
    ]