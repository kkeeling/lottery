# Generated by Django 2.2 on 2023-01-20 14:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0049_auto_20230120_1442'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='loser_dk',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='match',
            name='winner_dk',
            field=models.FloatField(blank=True, null=True),
        ),
    ]