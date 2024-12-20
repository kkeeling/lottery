# Generated by Django 2.2 on 2021-12-03 11:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0152_ceilingprojectionrangemapping_yh_value_to_assign'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ceilingprojectionrangemapping',
            name='max_projection',
            field=models.DecimalField(decimal_places=3, max_digits=5),
        ),
        migrations.AlterField(
            model_name='ceilingprojectionrangemapping',
            name='min_projection',
            field=models.DecimalField(decimal_places=3, max_digits=5),
        ),
        migrations.AlterField(
            model_name='ceilingprojectionrangemapping',
            name='value_to_assign',
            field=models.DecimalField(decimal_places=3, max_digits=5),
        ),
        migrations.AlterField(
            model_name='ceilingprojectionrangemapping',
            name='yh_value_to_assign',
            field=models.DecimalField(decimal_places=3, max_digits=5),
        ),
    ]
