import csv
import datetime
import requests
import traceback

from django.core.management.base import BaseCommand

from tennis.models import PinnacleMatch, PinnacleMatchOdds


class Command(BaseCommand):
    help = 'Update pinnacle odds'

    def handle(self, *args, **options):
        matchup_url = 'https://guest.api.arcadia.pinnacle.com/0.1/sports/33/matchups'
        odds_url = 'https://guest.api.arcadia.pinnacle.com/0.1/sports/33/markets/straight?primaryOnly=false'
        response = requests.get(matchup_url, headers={'x-api-key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'})
        
        matchups = response.json()
        for matchup in matchups:
            if matchup.get('parent') == None and 'special' not in matchup:
                try:
                    match = PinnacleMatch.objects.get(id=matchup.get('id'))
                except PinnacleMatch.DoesNotExist:
                    match = PinnacleMatch.objects.create(
                        id=matchup.get('id'),
                        event=matchup.get('league').get('name'),
                        home_participant=matchup.get('participants')[0].get('name'),
                        away_participant=matchup.get('participants')[1].get('name'),
                        start_time=datetime.datetime.strptime(matchup.get('startTime'), '%Y-%m-%dT%H:%M:%SZ')
                    )

                print(match)            

        response = requests.get(odds_url, headers={'x-api-key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'})
        odds_list = response.json()
        for odds in odds_list:
            if odds.get('type') == 'moneyline' and odds.get('period') == 0:
                try:
                    match = PinnacleMatch.objects.get(id=odds.get('matchupId'))
                    pinnacle_odds = PinnacleMatchOdds.objects.create(
                        match=match,
                        home_price=odds.get('prices')[0].get('price'),
                        away_price=odds.get('prices')[1].get('price')
                    )
                    print(pinnacle_odds)
                except PinnacleMatch.DoesNotExist:
                    pass
        