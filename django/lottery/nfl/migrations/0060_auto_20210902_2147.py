# Generated by Django 2.2 on 2021-09-02 21:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0059_auto_20210902_2146'),
    ]

    operations = [
        migrations.AddField(
            model_name='buildplayerprojection',
            name='adjusted_opportunity_percentile',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='buildplayerprojection',
            name='ownership_projection_percentile',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='buildplayerprojection',
            name='projection_percentile',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='buildplayerprojection',
            name='rating',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='buildplayerprojection',
            name='value',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='buildplayerprojection',
            name='value_projection_percentile',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
    ]