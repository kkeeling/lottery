# Generated by Django 2.2 on 2021-09-10 20:19

from django.db import migrations
from django.db.models.query_utils import Q


class Migration(migrations.Migration):
    
    def assign_games(apps, schema_editor):
        # We can't import the Person model directly as it may be a newer
        # version than this migration expects. We use the historical version.
        SlatePlayer = apps.get_model('nfl', 'SlatePlayer')
        for player in SlatePlayer.objects.all():
            games = player.slate.games.filter(
                Q(Q(game__home_team=player.team) | Q(game__away_team=player.team))
            )

            if games.count() > 0:
                player.slate_game = games[0]
            else:
                player.slate_game = None

            player.save()

    dependencies = [
        ('nfl', '0081_slateplayer_slate_game'),
    ]

    operations = [
        migrations.RunPython(assign_games),
    ]
