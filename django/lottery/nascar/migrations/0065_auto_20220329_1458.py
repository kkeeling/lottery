# Generated by Django 2.2 on 2022-03-29 14:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0064_auto_20220329_1350'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesimdriver',
            name='avg_dk_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='racesimdriver',
            name='avg_fd_score',
            field=models.FloatField(default=0.0),
        ),
    ]
