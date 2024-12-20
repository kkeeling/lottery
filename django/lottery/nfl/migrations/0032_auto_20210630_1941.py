# Generated by Django 2.2 on 2021-06-30 19:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0031_auto_20210622_2049'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuild',
            name='optimals_pct_complete',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=3),
        ),
        migrations.AddField(
            model_name='slatebuild',
            name='total_optimals',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
