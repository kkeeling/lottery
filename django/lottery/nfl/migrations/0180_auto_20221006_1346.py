# Generated by Django 2.2 on 2022-10-06 13:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0179_slateprojectionimport'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateprojectionimport',
            name='has_ownership_projections',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='slateprojectionimport',
            name='has_scoring_projections',
            field=models.BooleanField(default=True),
        ),
    ]
