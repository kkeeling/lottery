import csv
import datetime
import logging
import json
import math
import numpy
import os
import pandas
import pandasql
import requests
import scipy
import sys
import time
import traceback
import uuid

from random import random

from celery import shared_task, chord, group, chain
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages.api import success
from django.db.models.aggregates import Count, Sum
from django.db.models import Q, F
from django.db import transaction

from configuration.models import BackgroundTask

from fanduel import models as fanduel_models
from yahoo import models as yahoo_models

from . import models
from . import optimize

from lottery.celery import app

logger = logging.getLogger(__name__)

ATP_MATCH_FILES = [
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1968.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1969.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1970.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1971.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1972.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1973.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1974.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1975.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1976.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1977.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1978.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1979.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1980.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1981.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1982.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1983.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1984.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1985.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1986.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1987.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1988.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1989.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1990.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1991.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1992.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1993.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1994.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1995.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1996.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1997.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1998.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1999.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2000.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2001.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2002.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2003.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2004.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2005.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2006.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2007.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2008.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2009.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2010.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2011.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2012.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2013.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2014.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2015.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2016.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2017.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2018.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2019.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2020.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2021.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2022.csv'
]

WTA_MATCH_FILES = [
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1968.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1969.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1970.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1971.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1972.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1973.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1974.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1975.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1976.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1977.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1978.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1979.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1980.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1981.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1982.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1983.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1984.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1985.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1986.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1987.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1988.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1989.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1990.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1991.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1992.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1993.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1994.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1995.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1996.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1997.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1998.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1999.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2000.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2001.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2002.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2003.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2004.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2005.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2006.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2007.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2008.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2009.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2010.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2011.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2012.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2013.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2014.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2015.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2016.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2017.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2018.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2019.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2020.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2021.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2022.csv'
]


# ensures that tasks only run once at most!
@contextmanager
def lock_task(key, timeout=None):
    has_lock = False
    client = app.broker_connection().channel().client
    lock = client.lock(key, timeout=timeout)
    try:
        has_lock = lock.acquire(blocking=False)
        yield has_lock
    finally:
        if has_lock:
            lock.release()


@shared_task
def update_player_list_from_ta(tour):
    try:
        if tour == 'atp':
            url = 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_players.csv'
        else:
            url = 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_players.csv'

        # ATP Players
        with requests.Session() as s:
            download = s.get(url)
            decoded_content = download.content.decode('latin-1')

            cr = csv.DictReader(decoded_content.splitlines())
            # cr = csv.reader(decoded_content.splitlines(), delimiter=',')
            rows = list(cr)
            for row in rows:
                try:
                    dob = datetime.datetime.strptime(row['dob'], '%Y%m%d').date()
                except:
                    dob = None
                
                try:
                    player = models.Player.objects.get(player_id=row['player_id'], tour=tour)
                    print('Found {}'.format(str(player)))
                except models.Player.DoesNotExist:
                    player = models.Player.objects.create(
                        player_id=row['player_id'],
                        first_name=row['name_first'],
                        last_name=row['name_last'],
                        tour=tour,
                        hand=row['hand'].lower(),
                        dob=dob,
                        country=row['ioc']
                    )
                    print('Added {}'.format(str(player)))        
    except Exception as e:
        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def update_matches_from_ta(tour, year):
    if tour == 'atp':
        urls = ATP_MATCH_FILES
    else:
        urls = WTA_MATCH_FILES

    current_year = datetime.date.today().year
    file_index = len(urls) - (current_year - year) - 1

    print(f'Updating {tour} matches from {year} (index = {file_index})')

    url = urls[file_index]

    with requests.Session() as s:
        download = s.get(url)
        decoded_content = download.content.decode('latin-1')

        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        rows = list(cr)
        for index, row in enumerate(rows):
            if index == 0:
                continue

            try:
                tourney_date = datetime.datetime.strptime(row[5], '%Y%m%d').date()
            except:
                continue
            
            try:
                match = models.Match.objects.get(
                    tourney_id=row[0],
                    winner=models.Player.objects.get(
                        player_id=row[7],
                        tour=tour
                    ),
                    loser=models.Player.objects.get(
                        player_id=row[15],
                        tour=tour
                    ),
                )
            except models.Match.DoesNotExist:
                match = models.Match.objects.create(
                    tourney_id=row[0],
                    winner=models.Player.objects.get(
                        player_id=row[7],
                        tour=tour
                    ),
                    loser=models.Player.objects.get(
                        player_id=row[15],
                        tour=tour
                    ),
                )
            except models.Player.DoesNotExist:
                continue

            match.tourney_name = row[1]
            match.surface = row[2]
            match.draw_size = None if row[3] is None or row[3] == '' else int(row[3])
            match.tourney_level = row[4]
            match.tourney_date = tourney_date
            match.match_num = None if row[6] is None or row[6] == '' else int(row[6])
            try:
                match.winner_seed = None if row[8] is None or row[8] == '' else int(row[8])
            except:
                pass
            match.winner_entry = row[9]
            match.winner_name = row[10]
            match.winner_hand = row[11]
            # match.winner_ht = None if row[12] is None or row[12] == '' else int(row[12])
            match.winner_ioc = row[13]
            match.winner_age = None if row[14] is None or row[14] == '' else float(row[14])
            try:
                match.loser_seed = None if row[16] is None or row[16] == '' else int(row[16])
            except:
                pass
            match.loser_entry = row[17]
            match.loser_name = row[18]
            match.loser_hand = row[19]
            # match.loser_ht = None if row[20] is None or row[20] == '' else int(row[20])
            match.loser_ioc = row[21]
            match.loser_age = None if row[22] is None or row[22] == '' else float(row[22])
            match.score = row[23]
            match.best_of = None if row[24] is None or row[24] == '' else int(row[24])
            match.round = row[25]
            match.minutes = None if row[26] is None or row[26] == '' else int(row[26])
            match.w_ace = None if row[27] is None or row[27] == '' else int(row[27])
            match.w_df = None if row[28] is None or row[28] == '' else int(row[28])
            match.w_svpt = None if row[29] is None or row[29] == '' else int(row[29])
            match.w_1stIn = None if row[30] is None or row[30] == '' else int(row[30])
            match.w_1stWon = None if row[31] is None or row[31] == '' else int(row[31])
            match.w_2ndWon = None if row[32] is None or row[32] == '' else int(row[32])
            match.w_SvGms = None if row[33] is None or row[33] == '' else int(row[33])
            match.w_bpSaved = None if row[34] is None or row[34] == '' else int(row[34])
            match.w_bpFaced = None if row[35] is None or row[35] == '' else int(row[35])
            match.l_ace = None if row[36] is None or row[36] == '' else int(row[36])
            match.l_df = None if row[37] is None or row[37] == '' else int(row[37])
            match.l_svpt = None if row[38] is None or row[38] == '' else int(row[38])
            match.l_1stIn = None if row[39] is None or row[39] == '' else int(row[39])
            match.l_1stWon = None if row[40] is None or row[40] == '' else int(row[40])
            match.l_2ndWon = None if row[41] is None or row[41] == '' else int(row[41])
            match.l_SvGms = None if row[42] is None or row[42] == '' else int(row[42])
            match.l_bpSaved = None if row[43] is None or row[43] == '' else int(row[43])
            match.l_bpFaced = None if row[44] is None or row[44] == '' else int(row[44])
            match.winner_rank = None if row[45] is None or row[45] == '' else int(row[45])
            match.winner_rank_points = None if row[46] is None or row[46] == '' else int(row[46])
            match.loser_rank = None if row[47] is None or row[47] == '' else int(row[47])
            match.loser_rank_points = None if row[48] is None or row[48] == '' else int(row[48])
            match.save()
                
            print(match)


@shared_task
def get_pinn_odds(task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        update_time = datetime.datetime.now()
        matchup_url = 'https://guest.api.arcadia.pinnacle.com/0.1/sports/33/matchups'
        odds_url = 'https://guest.api.arcadia.pinnacle.com/0.1/sports/33/markets/straight?primaryOnly=false'
        response = requests.get(matchup_url, headers={'x-api-key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'})
        
        matchups = response.json()
        for matchup in matchups:
            if matchup.get('parent') == None and 'special' not in matchup:
                try:
                    match = models.PinnacleMatch.objects.get(id=matchup.get('id'))
                except models.PinnacleMatch.DoesNotExist:
                    match = models.PinnacleMatch.objects.create(
                        id=matchup.get('id'),
                        event=matchup.get('league').get('name'),
                        home_participant=matchup.get('participants')[0].get('name'),
                        away_participant=matchup.get('participants')[1].get('name'),
                        start_time=datetime.datetime.strptime(matchup.get('startTime'), '%Y-%m-%dT%H:%M:%SZ')
                    )

        response = requests.get(odds_url, headers={'x-api-key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'})
        odds_list = response.json()
        for odds in odds_list:
            if odds.get('type') == 'moneyline' and odds.get('period') == 0:
                try:
                    match = models.PinnacleMatch.objects.get(id=odds.get('matchupId'))
                    (pinnacle_odds, _) = models.PinnacleMatchOdds.objects.get_or_create(
                        match=match,
                        create_at=update_time
                    )
                    pinnacle_odds.home_price=odds.get('prices')[0].get('price')
                    pinnacle_odds.away_price=odds.get('prices')[1].get('price')
                    pinnacle_odds.save()
                except models.PinnacleMatch.DoesNotExist:
                    pass
            elif odds.get('type') == 'spread' and odds.get('period') == 0:
                try:
                    match = models.PinnacleMatch.objects.get(id=odds.get('matchupId'))
                    (pinnacle_odds, _) = models.PinnacleMatchOdds.objects.get_or_create(
                        match=match,
                        create_at=update_time
                    )
                    if pinnacle_odds.home_spread == 0.0:
                        pinnacle_odds.home_spread=odds.get('prices')[0].get('points')
                        pinnacle_odds.away_spread=odds.get('prices')[1].get('points')
                        pinnacle_odds.save()
                except models.PinnacleMatch.DoesNotExist:
                    pass

        task.status = 'success'
        task.content = 'Pinnacle odds updated.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem finding matches for slate: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def find_slate_matches(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        slate.find_matches()

        task.status = 'success'
        task.content = f'{slate.matches.all().count()} matches found'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem finding matches for slate: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_slate_players(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        
        with open(slate.salaries.path, mode='r') as salaries_file:
            csv_reader = csv.DictReader(salaries_file)

            success_count = 0
            missing_players = []

            for row in csv_reader:
                if slate.site == 'draftkings':
                    player_id = row['ID']
                    player_name = row['Name']
                    player_salary = int(row['Salary'])
                else:
                    raise Exception(f'{slate.site} is not supported yet.')

                alias = models.Alias.find_alias(player_name, slate.site)
                
                if alias is not None:
                    try:
                        slate_player = models.SlatePlayer.objects.get(
                            slate=slate,
                            slate_player_id=player_id
                        )
                    except models.SlatePlayer.DoesNotExist:
                        slate_player = models.SlatePlayer(
                            slate=slate,
                            slate_player_id=player_id
                        )

                    slate_player.name = alias.get_alias(slate.site)
                    slate_player.salary = player_salary
                    slate_player.player = alias.player
                    slate_player.save()

                    success_count += 1
                else:
                    missing_players.append(player_name)

        task.status = 'success'
        task.content = '{} players have been successfully added to {}.'.format(success_count, str(slate)) if len(missing_players) == 0 else '{} players have been successfully added to {}. {} players could not be identified.'.format(success_count, str(slate), len(missing_players))
        task.link = '/admin/tennis/missingalias/' if len(missing_players) > 0 else None
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing slate players: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def simulate_match(match_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        slate_match = models.SlateMatch.objects.get(id=match_id)

        def getBigPointProb(server):
            if server==p1:
                return p1_big_point
            elif server==p2:
                return p2_big_point
            else:
                print("Error")
                
        def isBigPoint(server_points, returner_points, tiebreak):
            #server_next_point = server_points+1
            server_next_point = server_points
            #print(server_next_point)
            if tiebreak==False:
                if server_next_point >= 3 and (server_next_point - returner_points) >= 1:
                    # print("game point")
                    return True
            else:
                if server_next_point >= 6 and abs(server_next_point - returner_points) >= 1:
                    # print("set point")
                    return True

        def getScore(pointsServer, pointsReturner, server_games, returner_games, completed_sets, tiebreaker):
            in_game = ['15', '30', '40']
            extra = ['D', 'A']
            
            display_server='0'
            display_returner='0'
            
            if tiebreaker==False:
                if pointsServer==0:
                    display_server='0'
                elif pointsServer>0 and pointsServer<4:
                    display_server=in_game[pointsServer-1]
                elif pointsServer>=4:
                    #clean_pointsServer = pointsServer-4
                    display_server = 'D'

                if pointsReturner==0:
                    display_returner='0'
                elif pointsReturner>0 and pointsReturner<4:
                    display_returner=in_game[pointsReturner-1]
                elif pointsReturner>=4:
                    #clean_pointsReturner = pointsReturner-4
                    display_returner = 'D'
                
                if (pointsServer>=4 and pointsReturner<4) or (pointsServer<4 and pointsReturner>=4):
                    display_server='D'
                    display_returner='D'

                if display_server=='D' and display_server=='D':
                    if pointsServer>pointsReturner:
                        display_server='A'
                    elif pointsReturner>pointsServer:
                        display_returner='A'

                if (display_server=='A' and display_returner=='A') or (display_server=='40' and display_returner=='40'):
                    display_server = 'D'
                    display_returner = 'D'
                if (display_server=='A' and display_returner=='40'):
                    display_server = 'A'
                    display_returner = 'D'
                if (display_server=='40' and display_returner=='A'):
                    display_server = 'D'
                    display_returner = 'A'
            else:
                display_server = str(pointsServer)
                display_returner = str(pointsReturner)
            
            if len(completed_sets)==0:
                pass
                # print(display_server+"-"+display_returner+"|"+"["+str(server_games)+"-"+str(returner_games)+"]")
            else:
                completed = ""
                for sets in completed_sets:
                    completed = completed+" "+str(sets[0])+":"+str(sets[1])
                # print(display_server+"-"+display_returner+"|"+str(completed)+"["+str(server_games)+":"+str(returner_games)+"]")

        def player_serve(server, returner, server_prob, returner_prob, gamesMatch, S, server_points_match, returner_points_match, server_games, returner_games, server_pointsGame, returner_pointsGame, completed_sets):
            if isBigPoint(server_pointsGame, returner_pointsGame, False):
                server_prob = getBigPointProb(server)
            if random() < server_prob:
                # print(server+" ", end = "")
                getScore(server_pointsGame, returner_pointsGame, server_games, returner_games, completed_sets, False)
                server_pointsGame += 1
                server_points_match += 1

                # if server == p1 and random() < p1_ace:
                #     print(f'{p1} ACES!!!')
                # elif server == p2 and random() < p2_ace:
                #     print(f'{p2} ACES!!!')
            else:
                # print(server+" ", end = "")
                getScore(server_pointsGame, returner_pointsGame, server_games, returner_games, completed_sets, False)
                returner_pointsGame += 1
                returner_points_match += 1
            if max(server_pointsGame, returner_pointsGame) >= 4 and abs(server_pointsGame - returner_pointsGame) > 1:
                # print("\t", server + ":", str(server_pointsGame) + ",", returner + ":", returner_pointsGame, end = "")
                if server_pointsGame > returner_pointsGame:
                    server_games += 1
                    # print()
                else:
                    returner_games += 1
                    # print(" -- " + returner, "broke")
                gamesMatch += 1
                return server_games, returner_games, gamesMatch, S, server_points_match, returner_points_match, server_pointsGame, returner_pointsGame

            return server_games, returner_games, gamesMatch, S, server_points_match, returner_points_match, server_pointsGame, returner_pointsGame

        def simulateSet(a, b, gamesMatch, S, pointsMatch1, pointsMatch2, completed_sets):
            S += 1
            gamesSet1 = 0
            gamesSet2 = 0
            while (max(gamesSet1, gamesSet2) < 6 or abs(gamesSet1 - gamesSet2) < 2) and gamesSet1 + gamesSet2 < 12: #Conditions to play another Game in this Set
                pointsGame1 = 0
                pointsGame2 = 0
                #player 1 serves
                while gamesMatch % 2 == 0:
                    gamesSet1, gamesSet2, gamesMatch, S, pointsMatch1, pointsMatch2, pointsGame1, pointsGame2 = player_serve(p1, p2, a, b, gamesMatch, S, pointsMatch1, pointsMatch2, gamesSet1, gamesSet2, pointsGame1, pointsGame2, completed_sets)
                pointsGame1 = 0
                pointsGame2 = 0
                #player 2 serves, but we also incorporate in logic to end the set
                while gamesMatch % 2 == 1 and (max(gamesSet1, gamesSet2) < 6 or abs(gamesSet1 - gamesSet2) < 2) and gamesSet1 + gamesSet2 < 12:
                    gamesSet2, gamesSet1, gamesMatch, S, pointsMatch2, pointsMatch1, pointsGame2, pointsGame1 = player_serve(p2, p1, b, a, gamesMatch, S, pointsMatch2, pointsMatch1, gamesSet2, gamesSet1, pointsGame2, pointsGame1, completed_sets)
            #at 6 games all we go to a tie breaker
            # if gamesSet1 == 6 and gamesSet2 == 6:
            #     print("Set", S, "is 6-6 and going to a Tiebreaker.")
            
            return gamesSet1, gamesSet2, gamesMatch, S, pointsMatch1, pointsMatch2

        def simulateTiebreaker(player1, player2, a, b, gamesMatch, pointsMatch1, pointsMatch2, completed_sets):
            pointsTie1, pointsTie2 = 0, 0           
            while max(pointsTie1, pointsTie2) < 7 or abs(pointsTie1 - pointsTie2) < 2:
                #player 1 will server first
                if gamesMatch % 2 == 0:
                    while (pointsTie1 + pointsTie2) % 4 == 0 or (pointsTie1 + pointsTie2) % 4 == 3:
                        server_prob = a
                        if isBigPoint(pointsTie1, pointsTie2, True):
                            server_prob=getBigPointProb(player1)
                        if random() < server_prob:
                            # print(player1+" ", end = "")
                            getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                            pointsTie1 += 1
                            pointsMatch1 += 1

                            # if random() < p1_ace:
                            #     print(f'{p1} ACES!!!')
                        else:
                            getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                            pointsTie2 += 1
                            pointsMatch2 += 1
                        if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
                            # print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
                            gamesMatch += 1
                            break 
                    while (max(pointsTie1, pointsTie2) < 7 or abs(pointsTie1 - pointsTie2) < 2) and ((pointsTie1 + pointsTie2) % 4 == 1 or (pointsTie1 + pointsTie2) % 4 == 2): # Conditions to continue Tiebreaker (race to 7, win by 2) and Player 2 serves (points 4N+1 and 4N+2)
                        server_prob = b
                        if isBigPoint(pointsTie2, pointsTie1, True):
                            server_prob=getBigPointProb(player2)
                        if random() < server_prob:
                            #print(player2+" ", end = "")
                            getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                            pointsTie2 += 1
                            pointsMatch2 += 1

                            # if random() < p2_ace:
                            #     print(f'{p2} ACES!!!')
                        else:
                            getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                            pointsTie1 += 1
                            pointsMatch1 += 1
                        if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
                            # print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
                            break
                
                #player 2 will server first
                if gamesMatch % 2 == 1:
                    while (pointsTie1 + pointsTie2) % 4 == 1 or (pointsTie1 + pointsTie2) % 4 == 2:
                        server_prob =  a
                        if isBigPoint(pointsTie1, pointsTie2, True):
                            server_prob=getBigPointProb(player1)
                        if random() < server_prob:
                            #print(player1+" ", end = "")
                            getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                            pointsTie1 += 1
                            pointsMatch1 += 1
                        else:
                            getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                            pointsTie2 += 1
                            pointsMatch2 += 1
                        # if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
                        #     print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
                        #     break 
                    while (max(pointsTie2, pointsTie1) < 7 or abs(pointsTie1 - pointsTie2) < 2) and ((pointsTie1 + pointsTie2) % 4 == 0 or (pointsTie1 + pointsTie2) % 4 == 3): # Conditions to continue Tiebreaker (race to 7, win by 2) and Player 2 serves (points 4N and 4N+3)
                        server_prob =  b
                        if isBigPoint(pointsTie2, pointsTie1, True):
                            server_prob=getBigPointProb(player2)
                        if random() < server_prob:
                            #print(player2+" ", end = "")
                            getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                            pointsTie2 += 1
                            pointsMatch2 += 1
                        else:
                            getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                            pointsTie1 += 1
                            pointsMatch1 += 1
                        # if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
                        #     print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
                        #     break                             
            gamesMatch += 1
            return pointsTie1, pointsTie2, gamesMatch, pointsMatch1, pointsMatch2

        def printSetMatchSummary(p1, p2, gamesSet1, gamesSet2, S, pointsTie1, pointsTie2, setsMatch1, setsMatch2):
            if gamesSet1 > gamesSet2:
                setsMatch1 += 1
                # print(p1.upper(), "wins Set", str(S) + ":", gamesSet1, "games to", str(gamesSet2) + ".")
            elif gamesSet2 > gamesSet1:
                setsMatch2 += 1
                # print(p2.upper(), "wins Set", str(S) + ":", gamesSet2, "games to", str(gamesSet1) + ".")
            elif gamesSet1 == gamesSet2:
                if pointsTie1 > pointsTie2:
                    setsMatch1 += 1
                    # print(p1.upper(), "wins Set", str(S) + ": 7 games to 6 (" + str(pointsTie1) + "-" + str(pointsTie2) + ").")
                else:
                    setsMatch2 += 1
                    # print(p2.upper(), "wins Set", str(S) + ": 7 games to 6 (" + str(pointsTie2) + "-" + str(pointsTie1) + ").")
            # print("After", S, "Sets:", p1, str(setsMatch1) + ",", p2, str(setsMatch2) + ".\n")   
            return setsMatch1, setsMatch2

        def pointsMatchSummary(p1, p2, setsMatch1, setsMatch2, pointsMatch1, pointsMatch2):
            if setsMatch1 == sets_to_win:
                # print(p1.upper(), "(" + str(a) + ")", "beat", p2, "(" + str(b) + ") by", setsMatch1, "Sets to", str(setsMatch2) + ".")
                return p1
            else:
                # print(p2.upper(), "(" + str(b) + ")", "beat", p1, "(" + str(a) + ") by", setsMatch2, "Sets to", str(setsMatch1) + ".")
                return p2

        last_52_weeks = models.Match.objects.filter(
            winner__tour='atp',
            surface='Hard',
            tourney_date__gte=datetime.date.today() - datetime.timedelta(weeks=52),
            tourney_date__lte=datetime.date.today()
        )
        w_serve_points_data = last_52_weeks.exclude(
            Q(Q(w_svpt=None) | Q(w_1stWon=None) | Q(w_2ndWon=None))
        ).aggregate(
            num_points=Sum('w_svpt'),
            num_1stWon=Sum('w_1stWon'),
            num_2ndWon=Sum('w_2ndWon')
        )
        l_serve_points_data = last_52_weeks.exclude(
            Q(Q(l_svpt=None) | Q(l_1stWon=None) | Q(l_2ndWon=None))
        ).aggregate(
            num_points=Sum('l_svpt'),
            num_1stWon=Sum('l_1stWon'),
            num_2ndWon=Sum('l_2ndWon')
        )
        avg_serve_point_rate = round((w_serve_points_data.get('num_1stWon') + w_serve_points_data.get('num_2ndWon') + l_serve_points_data.get('num_1stWon') + l_serve_points_data.get('num_2ndWon')) / (w_serve_points_data.get('num_points') + l_serve_points_data.get('num_points')), 4)
        avg_return_point_rate = 1 - avg_serve_point_rate

        #initialize player one and two
        #a is ps1 and b is ps2
        #p1_big_point and p2_big_point are the probability
        #of p1 and p2 winning on a big point, respectively
        try:
            alias1 = models.Alias.objects.get(pinn_name=slate_match.match.home_participant)
        except models.Alias.DoesNotExist:
            print(f'{slate_match.home_participant} does not have an alias.')
            return
        try:
            alias2 = models.Alias.objects.get(pinn_name=slate_match.match.away_participant)
        except models.Alias.DoesNotExist:
            print(f'{slate_match.away_participant} does not have an alias.')
            return

        player_1 = alias1.player
        player_2 = alias2.player
        p1 = player_1.full_name
        p2 = player_2.full_name

        p1_1st_pct = player_1.get_first_in_rate()
        p2_1st_pct = player_2.get_first_in_rate()
        p1_1st_won = player_1.get_first_won_rate()
        p2_1st_won = player_2.get_first_won_rate()
        p1_2nd_won = player_1.get_second_won_rate()
        p2_2nd_won = player_2.get_second_won_rate()
        p1_break_pct = player_1.get_break_rate()
        p2_break_pct = player_2.get_break_rate()
        
        p1_other = numpy.linalg.norm([
            p1_1st_pct,
            p1_1st_won,
            p1_2nd_won,
            p1_break_pct
        ])
        
        p2_other = numpy.linalg.norm([
            p2_1st_pct,
            p2_1st_won,
            p2_2nd_won,
            p2_break_pct
        ])

        a_prime = player_1.get_return_points_rate()
        b_prime = player_2.get_return_points_rate()
        a_diff = ((a_prime/avg_return_point_rate) - 1) * .75
        b_diff = ((b_prime/avg_return_point_rate) - 1) * .75

        # a = player_1.get_serve_points_rate() * (1 + (b_diff * -1))
        # b = player_2.get_serve_points_rate() * (1 + (a_diff * -1))
        a = (player_1.get_serve_points_rate()/p1_other)# * (1 + (b_diff * -1))
        b = (player_2.get_serve_points_rate()/p2_other)# * (1 + (a_diff * -1))

        p1_big_point = a
        p2_big_point = b
        p1_ace = player_1.get_ace_pct()
        p2_ace = player_2.get_ace_pct()
        p1_df = player_1.get_df_pct()
        p2_df = player_2.get_df_pct()
        p1_break = player_1.get_return_points_rate()
        p2_break = player_2.get_return_points_rate()


        best_of = 3
        sets_to_win = math.ceil(best_of/2)
        p1_wins = 0
        p2_wins = 0

        # print(f'{p1} {a}')
        # print(f'{p2} {b}')

        for _ in range(0, 10000):
            completed_sets = []
            S = 0
            gamesMatch = 0

            #in all subscripted variables
            #the subscript refers to the player
            #for example, setsMatch1 is sets won by player1 and
            #setsMatch2 is sets won by player2
            pointsMatch1, pointsMatch2 = 0, 0
            setsMatch1, setsMatch2 = 0, 0
            pointsTie1, pointsTie2 = 0, 0
            pointsGame1, pointsGame2 = 0, 0
            breaks1, breaks2 = 0, 0
            aces1, aces2 = 0, 0
            doubles1, doubles2 = 0, 0

            while S < best_of and max(setsMatch1, setsMatch2) < sets_to_win:
                gamesSet1, gamesSet2, gamesMatch, S, pointsMatch1, pointsMatch2 = simulateSet(a, b, gamesMatch, S, 
                                                                                            pointsMatch1, pointsMatch2, 
                                                                                            completed_sets)
                # print()
                if gamesSet1 == 6 and gamesSet2 == 6:
                    pointsTie1, pointsTie2, gamesMatch, pointsMatch1, pointsMatch2 = simulateTiebreaker(p1, p2, a, b, 
                                                                                                        gamesMatch, pointsMatch1, 
                                                                                                        pointsMatch2, 
                                                                                                        completed_sets)
                
                setsMatch1, setsMatch2 = printSetMatchSummary(p1, p2, gamesSet1, gamesSet2, 
                                                            S, pointsTie1, pointsTie2, 
                                                            setsMatch1, setsMatch2)
                
                if gamesSet1 == 6 and gamesSet2 == 6:
                    if pointsTie1 > pointsTie2:
                        completed_sets.append([gamesSet1+1, gamesSet2])
                    else:
                        completed_sets.append([gamesSet1, gamesSet2+1])
                else:
                    completed_sets.append([gamesSet1, gamesSet2])

            winner = pointsMatchSummary(p1, p2, setsMatch1, setsMatch2, pointsMatch1, pointsMatch2)
            if winner == p1:
                p1_wins += 1
            else:
                p2_wins += 1

        print(f'{p1} wins {p1_wins/100}%')

        task.status = 'success'
        task.content = f'Simulation of {slate_match} complete.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem simulating {slate_match}: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))
