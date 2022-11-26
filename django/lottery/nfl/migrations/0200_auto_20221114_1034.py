# Generated by Django 2.2 on 2022-11-14 10:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0199_marketprojections_week'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='slateprojectionimport',
            name='content_type',
        ),
        migrations.RemoveField(
            model_name='slateprojectionimport',
            name='has_ownership_projections',
        ),
        migrations.RemoveField(
            model_name='slateprojectionimport',
            name='has_scoring_projections',
        ),
        migrations.RemoveField(
            model_name='slateprojectionimport',
            name='headers',
        ),
        migrations.RemoveField(
            model_name='slateprojectionimport',
            name='projection_sheet',
        ),
        migrations.RemoveField(
            model_name='slateprojectionimport',
            name='url',
        ),
        migrations.AlterField(
            model_name='slateprojectionimport',
            name='field_lineup_count',
            field=models.IntegerField(default=100, verbose_name='# Field Lineups'),
        ),
    ]
