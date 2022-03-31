# Generated by Django 2.2 on 2022-03-31 13:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0071_auto_20220330_1319'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesimdriver',
            name='dk_op',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='racesimdriver',
            name='fd_op',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='racesimlineup',
            name='dup_projection',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
    ]
