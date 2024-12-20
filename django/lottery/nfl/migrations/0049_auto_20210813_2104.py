# Generated by Django 2.2 on 2021-08-13 21:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0048_auto_20210806_2129'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuild',
            name='target_score',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='target'),
        ),
        migrations.AlterField(
            model_name='slatebuild',
            name='total_optimals',
            field=models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
    ]
