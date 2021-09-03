# Generated by Django 2.2 on 2021-09-02 21:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0058_slatebuildlineup_rating'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateplayerprojection',
            name='adjusted_opportunity_percentile',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='slateplayerprojection',
            name='ownership_projection_percentile',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='slateplayerprojection',
            name='projection_percentile',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='slateplayerprojection',
            name='rating',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='slateplayerprojection',
            name='value',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=5),
        ),
        migrations.AddField(
            model_name='slateplayerprojection',
            name='value_projection_percentile',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
    ]
