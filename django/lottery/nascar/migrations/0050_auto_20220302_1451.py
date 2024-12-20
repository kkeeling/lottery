# Generated by Django 2.2 on 2022-03-02 14:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0049_auto_20220302_1312'),
    ]

    operations = [
        migrations.RenameField(
            model_name='racesimfastestlapsprofile',
            old_name='pct_laps_led_max',
            new_name='cum_fastest_laps_max',
        ),
        migrations.RenameField(
            model_name='racesimfastestlapsprofile',
            old_name='pct_laps_led_min',
            new_name='cum_fastest_laps_min',
        ),
        migrations.AddField(
            model_name='racesimfastestlapsprofile',
            name='pct_fastest_laps_max',
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name='racesimfastestlapsprofile',
            name='pct_fastest_laps_min',
            field=models.FloatField(default=0.0),
        ),
    ]
