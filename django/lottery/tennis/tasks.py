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
        headers = {
            'authority': 'guest.api.arcadia.pinnacle.com',
            'pragma': 'no-cache',
            'cache-control': 'no-cache',
            'accept': 'application/json',
            'x-device-uuid': '00f06d96-7d7dd505-45d4f32f-23672660',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36',
            'x-api-key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R',
            'content-type': 'application/json',
            'sec-gpc': '1',
            'origin': 'https://www.pinnacle.com',
            'sec-fetch-site': 'same-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://www.pinnacle.com/',
            'accept-language': 'en-US,en;q=0.9',
        }        
        response = requests.get(matchup_url, headers=headers)
        
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

        response = requests.get(odds_url, headers=headers)
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
        favorite, odds = slate_match.match.favorite
        if odds > 0:
            fav_implied_win_pct = 100/(100+odds)
        else:
            fav_implied_win_pct = -odds/(-odds+100)

        fav_prob_lookup = models.WinRateLookup.objects.get(implied_odds=round(fav_implied_win_pct, 2))
        dog_prob_lookup = models.WinRateLookup.objects.get(implied_odds=round(1.0 - fav_implied_win_pct, 2))

        if slate_match.tour == 'wta':
            fav_prob = fav_prob_lookup.wta_odds
        else:
            if slate_match.best_of == 3:
                fav_prob = fav_prob_lookup.atp3_odds
            else:
                fav_prob = fav_prob_lookup.atp5_odds

        w_vals = numpy.random(1, size=(1000))

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


@shared_task
def calculate_target_scores(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        all_scores = numpy.array(
            [
                p.sim_scores for p in models.SlatePlayerProjection.objects.filter(
                    slate_player__slate=slate
                )
            ]
        )

        n = 8
        df_scores = pandas.DataFrame(all_scores, dtype=float)
        top_scores = df_scores.max(axis = 0)
        target_scores = [df_scores[c].nlargest(n).values[n-1] for c in df_scores.columns]

        slate.top_score = numpy.mean(top_scores.to_list())
        slate.target_score = numpy.mean(target_scores)
        slate.save()
        
        task.status = 'success'
        task.content = f'Target scores calculated'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating target scores: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def calculate_slate_structure(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        chord(
            [find_optimal_for_sim.s(slate.id, i) for i in range(0, 10000)],
            complile_sim_optimals.s(slate_id, task_id)
        )()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating slate structure: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def find_optimal_for_sim(slate_id, sim_iteration):
    slate = models.Slate.objects.get(id=slate_id)
    optimal = optimize.find_optimal_from_sims(
        slate.site,
        models.SlatePlayerProjection.objects.filter(slate_player__slate=slate),
        sim_iteration=sim_iteration
    )[0]
    return [p.id for p in optimal.players]


@shared_task
def complile_sim_optimals(results, slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        df_opt = pandas.DataFrame(results)
        
        # s_0 = df_opt[0].value_counts()
        # s_1 = df_opt[1].value_counts()
        # s_2 = df_opt[2].value_counts()
        # s_3 = df_opt[3].value_counts()
        # s_4 = df_opt[4].value_counts()
        # s_5 = df_opt[5].value_counts()
        
        # print(s_0)
        # print(s_1)
        # print(s_2)
        # print(s_3)
        # print(s_4)
        # print(s_5)

        for projection in models.SlatePlayerProjection.objects.filter(slate_player__slate=slate):
            count = 0
            try:
                count += df_opt[0].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[1].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[2].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[3].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[4].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[5].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            print(f'{projection.slate_player}: {count}')
            projection.optimal_exposure = count / 10000
            projection.save()
                
        task.status = 'success'
        task.content = f'Slate structure calculated'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating slate structure: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def build_lineups(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)
        lineups = optimize.optimize(build.slate.site, models.SlatePlayerProjection.objects.filter(slate_player__slate=build.slate), build.configuration, build.total_lineups * build.configuration.lineup_multiplier)

        for lineup in lineups:
            if build.slate.site == 'draftkings':
                lineup = models.SlateBuildLineup.objects.create(
                    build=build,
                    player_1=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[0].id, slate_player__slate=build.slate),
                    player_2=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[1].id, slate_player__slate=build.slate),
                    player_3=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[2].id, slate_player__slate=build.slate),
                    player_4=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[3].id, slate_player__slate=build.slate),
                    player_5=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[4].id, slate_player__slate=build.slate),
                    player_6=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[5].id, slate_player__slate=build.slate),
                    total_salary=lineup.salary_costs
                )
                # lineup = models.SlateBuildLineup.objects.create(
                #     build=build,
                #     player_1=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[0].name, slate_player__slate=build.slate),
                #     player_2=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[1].name, slate_player__slate=build.slate),
                #     player_3=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[2].name, slate_player__slate=build.slate),
                #     player_4=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[3].name, slate_player__slate=build.slate),
                #     player_5=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[4].name, slate_player__slate=build.slate),
                #     player_6=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[5].name, slate_player__slate=build.slate),
                #     total_salary=lineup.spent()
                # )
                lineup.implied_win_pct = lineup.player_1.implied_win_pct * lineup.player_2.implied_win_pct * lineup.player_3.implied_win_pct * lineup.player_4.implied_win_pct * lineup.player_5.implied_win_pct * lineup.player_6.implied_win_pct
                lineup.save()

                lineup.simulate()
            else:
                raise Exception(f'{build.slate.site} is not available for building yet.')
        
        task.status = 'success'
        task.content = f'{build.lineups.all().count()} lineups created.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem building lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def clean_lineups(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)

        ordered_lineups = build.lineups.all().order_by(f'-{build.configuration.clean_lineups_by}')
        ordered_lineups.filter(id__in=ordered_lineups.values_list('pk', flat=True)[int(build.total_lineups):]).delete()
        
        task.status = 'success'
        task.content = 'Lineups cleaned.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem cleaning lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def calculate_exposures(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)
        players = models.SlatePlayerProjection.objects.filter(
            slate_player__slate=build.slate
        )

        for player in players:
            exposure, _ = models.SlateBuildPlayerExposure.objects.get_or_create(
                build=build,
                player=player
            )
            exposure.exposure = build.lineups.filter(
                Q(
                    Q(player_1=player) | 
                    Q(player_2=player) | 
                    Q(player_3=player) | 
                    Q(player_4=player) | 
                    Q(player_5=player) | 
                    Q(player_6=player)
                )
            ).count() / build.lineups.all().count()
            exposure.save()
        
        task.status = 'success'
        task.content = 'Exposures calculated.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating exposures: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def export_build_for_upload(build_id, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        build = models.SlateBuild.objects.get(pk=build_id)

        with open(result_path, 'w') as temp_csv:
            build_writer = csv.writer(temp_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            build_writer.writerow(['P', 'P', 'P', 'P', 'P', 'P'])

            lineups = build.lineups.all()

            for lineup in lineups:
                if build.slate.site == 'draftkings':
                    row = [
                        f'{lineup.player_1.name} ({lineup.player_1.slate_player.slate_player_id})',
                        f'{lineup.player_2.name} ({lineup.player_2.slate_player.slate_player_id})',
                        f'{lineup.player_3.name} ({lineup.player_3.slate_player.slate_player_id})',
                        f'{lineup.player_4.name} ({lineup.player_4.slate_player.slate_player_id})',
                        f'{lineup.player_5.name} ({lineup.player_5.slate_player.slate_player_id})',
                        f'{lineup.player_6.name} ({lineup.player_6.slate_player.slate_player_id})'
                    ]
                else:
                    raise Exception('{} is not a supported dfs site.'.format(build.slate.site)) 

                build_writer.writerow(row)

        task.status = 'download'
        task.content = result_url
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem generating your export {e}'
            task.save()
        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))

