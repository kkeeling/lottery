# Generated by Django 2.2 on 2022-02-16 13:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0029_auto_20220216_1259'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesimdriver',
            name='strategy_factor',
            field=models.FloatField(default=0.0),
        ),
    ]
