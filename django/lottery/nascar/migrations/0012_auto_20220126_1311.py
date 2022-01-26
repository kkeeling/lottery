# Generated by Django 2.2 on 2022-01-26 13:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0011_raceinfraction'),
    ]

    operations = [
        migrations.AddField(
            model_name='race',
            name='num_cars',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='race',
            name='num_caution_laps',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='race',
            name='num_cautions',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='race',
            name='num_lead_changes',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='race',
            name='num_leaders',
            field=models.IntegerField(default=0),
        ),
    ]
