# Generated by Django 2.2 on 2022-03-02 13:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0048_auto_20220301_1432'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesimlapsledprofile',
            name='cum_laps_led_max',
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name='racesimlapsledprofile',
            name='cum_laps_led_min',
            field=models.FloatField(default=0.0),
        ),
    ]