# Generated by Django 2.2 on 2022-03-18 10:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formula_1', '0008_racesimdriver_dk_scores'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesimdriver',
            name='avg_dk_score',
            field=models.FloatField(default=0.0),
        ),
    ]