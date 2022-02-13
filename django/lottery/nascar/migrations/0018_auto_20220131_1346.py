# Generated by Django 2.2 on 2022-01-31 13:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0017_racesimdriver_starting_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='race',
            name='stage_1_laps',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='race',
            name='stage_2_laps',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='race',
            name='stage_3_laps',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='race',
            name='stage_4_laps',
            field=models.IntegerField(default=0),
        ),
    ]