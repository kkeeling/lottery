# Generated by Django 2.2 on 2023-01-17 21:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0041_match_final_odds'),
    ]

    operations = [
        migrations.RenameField(
            model_name='match',
            old_name='final_odds',
            new_name='loser_odds',
        ),
        migrations.AddField(
            model_name='match',
            name='winner_odds',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
