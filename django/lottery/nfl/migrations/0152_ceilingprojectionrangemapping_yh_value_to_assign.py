# Generated by Django 2.2 on 2021-12-03 10:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0151_auto_20211202_0727'),
    ]

    operations = [
        migrations.AddField(
            model_name='ceilingprojectionrangemapping',
            name='yh_value_to_assign',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=4),
            preserve_default=False,
        ),
    ]
