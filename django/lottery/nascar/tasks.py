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


# Updating Nascar Data

@shared_task
def update_driver_list():
    try:
        url = 'https://www.nascar.com/json/drivers/?limit=1000'
        response = requests.get(url)

        if response.status_code >= 300:
            raise Exception(f'Error updating driver list: HTTP {response.status_code}')
        
        data = response.json().get('response')
        for d in data:
            driver, _ = models.Driver.objects.get_or_create(
                nascar_driver_id=d.get('Nascar_Driver_ID')
            )

            driver.driver_id = d.get('Driver_ID')
            driver.first_name = d.get('First_Name')
            driver.last_name = d.get('Last_Name')
            driver.full_name = d.get('Full_Name')
            driver.badge = d.get('Badge')
            driver.badge_image = d.get('Badge_Image')
            driver.manufacturer_image = d.get('Manufacturer')
            driver.team = d.get('Team') if d.get('Team') != d.get('Badge') else None
            driver.driver_image = d.get('Image')
            driver.save()

            alias, _ = models.Alias.objects.get_or_create(
                nascar_name=driver.full_name
            )
            alias.dk_name = driver.full_name if alias.dk_name is None else alias.dk_name
            alias.fd_name = driver.full_name if alias.fd_name is None else alias.fd_name
            alias.ma_name = driver.full_name if alias.ma_name is None else alias.ma_name
            alias.save()

    except Exception as e:
        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def update_race_list(race_year=2022):
    try:
        url = f'https://cf.nascar.com/cacher/{race_year}/race_list_basic.json'
        response = requests.get(url)

        if response.status_code >= 300:
            raise Exception(f'Error updating race list: HTTP {response.status_code}')
        
        data = response.json()

        for series in data:
            races = data[series]
            for r in races:
                # get basic race data
                print(r.get('race_name'))

                race, _ = models.Race.objects.get_or_create(
                    race_id=r.get('race_id')
                )
                race.series = r.get('series_id')
                race.race_season = r.get('race_season')
                race.race_name = r.get('race_name')
                race.race_type = r.get('race_type_id')
                race.restrictor_plate = r.get('restrictor_plate')

                track, _ = models.Track.objects.get_or_create(
                    track_id=r.get('track_id')
                )

                track.track_name = r.get('track_name')
                track.save()

                race.track = track
                race.race_date = datetime.datetime.strptime(r.get('race_date'), '%Y-%m-%dT%H:%M:%S')
                race.qualifying_date = datetime.datetime.strptime(r.get('qualifying_date'), '%Y-%m-%dT%H:%M:%S')
                race.scheduled_distance = r.get('scheduled_distance')
                race.scheduled_laps = r.get('scheduled_laps')
                race.save()
        
        race_result_tasks = [
            update_race_results.si(race.race_id, race_year) for race in models.Race.objects.filter(race_season=race_year)
        ]
        lap_data_tasks = [
            update_lap_data_for_race.si(race.race_id, race_year) for race in models.Race.objects.filter(race_season=race_year)
        ]
        group(race_result_tasks + lap_data_tasks)()

    except Exception as e:
        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def update_race_results(race_id, race_year=2022):
    race = models.Race.objects.get(race_id=race_id)

    # get race results
    race.results.all().delete()
    race.cautions.all().delete()
    race.infractions.all().delete()
    weekend_url = f'https://cf.nascar.com/cacher/{race_year}/{race.series}/{race.race_id}/weekend-feed.json'

    results_response = requests.get(weekend_url)
    if results_response.status_code >= 300:
        print(f'Cannot retrieve results for {race.race_name}: HTTP {results_response.status_code}')
        return
    
    results_data = results_response.json()
    weekend_race = results_data.get('weekend_race')

    for wr in weekend_race:
        race.num_cars = wr.get('number_of_cars_in_field')
        race.num_lead_changes = wr.get('number_of_lead_changes')
        race.num_leaders = wr.get('number_of_leaders')
        race.num_cautions = wr.get('number_of_cautions')
        race.num_caution_laps = wr.get('number_of_caution_laps')
        race.save()

        results = wr.get('results')
        for result in results:
            try:
                models.RaceResult.objects.create(
                    race=race,
                    driver=models.Driver.objects.get(nascar_driver_id=result.get('driver_id')),
                    finishing_position=result.get('finishing_position'),
                    starting_position=result.get('starting_position'),
                    laps_led=result.get('laps_led'),
                    times_led=result.get('times_led'),
                    laps_completed=result.get('laps_completed'),
                    finishing_status=result.get('finishing_status'),
                    disqualified=result.get('disqualified')
                )
            except:
                pass

        caution_segments = wr.get('caution_segments')
        for caution in caution_segments:
            try:
                models.RaceCautionSegment.objects.create(
                    race=race,
                    start_lap=caution.get('start_lap'),
                    end_lap=caution.get('end_lap'),
                    reason=caution.get('reason'),
                    comment=caution.get('comment')
                )
            except:
                pass

        infractions = wr.get('infractions')
        for infraction in infractions:
            try:
                models.RaceInfraction.objects.create(
                    race=race,
                    driver=models.Driver.objects.get(nascar_driver_id=infraction.get('driver_id')),
                    lap=infraction.get('lap'),
                    lap_assessed=infraction.get('lap_assessed'),
                    infraction=infraction.get('infraction'),
                    penalty=infraction.get('penalty'),
                    notes=infraction.get('notes')
                )
            except:
                pass


@shared_task
def update_lap_data_for_race(race_id, race_year=2022):
    race = models.Race.objects.get(race_id=race_id)

    # get lap data
    race.driver_laps.all().delete()
    lap_times_url = f'https://cf.nascar.com/cacher/{race_year}/{race.series}/{race.race_id}/lap-times.json'

    laps_response = requests.get(lap_times_url)
    if laps_response.status_code >= 300:
        print(f'Cannot retrieve results for {race.race_name}: HTTP {laps_response.status_code}')
        return

    laps_data = laps_response.json().get('laps')
    for ld in laps_data:
        driver = models.Driver.objects.get(nascar_driver_id=ld.get('NASCARDriverID'))
        for l in ld.get('Laps'):
            try:
                models.RaceDriverLap.objects.create(
                    race=race,
                    driver=driver,
                    lap=l.get('Lap'),
                    lap_time=l.get('LapTime'),
                    lap_speed=l.get('LapSpeed'),
                    running_pos=l.get('RunningPos')
                )
            except:
                pass


# Exports

@shared_task
def export_tracks(track_ids, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        tracks = models.Track.objects.filter(track_id__in=track_ids)
        df_tracks = pandas.DataFrame.from_records(tracks.values())
        df_tracks.to_csv(result_path)

        task.status = 'download'
        task.content = result_url
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a exporting track data: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))

# @shared_task
# def update_matches_from_ta(tour, year):
#     if tour == 'atp':
#         urls = ATP_MATCH_FILES
#     else:
#         urls = WTA_MATCH_FILES

#     current_year = datetime.date.today().year
#     file_index = len(urls) - (current_year - year) - 1

#     print(f'Updating {tour} matches from {year} (index = {file_index})')

#     url = urls[file_index]

#     with requests.Session() as s:
#         download = s.get(url)
#         decoded_content = download.content.decode('latin-1')

#         cr = csv.reader(decoded_content.splitlines(), delimiter=',')
#         rows = list(cr)
#         for index, row in enumerate(rows):
#             if index == 0:
#                 continue

#             try:
#                 tourney_date = datetime.datetime.strptime(row[5], '%Y%m%d').date()
#             except:
#                 continue
            
#             try:
#                 match = models.Match.objects.get(
#                     tourney_id=row[0],
#                     winner=models.Player.objects.get(
#                         player_id=row[7],
#                         tour=tour
#                     ),
#                     loser=models.Player.objects.get(
#                         player_id=row[15],
#                         tour=tour
#                     ),
#                 )
#             except models.Match.DoesNotExist:
#                 match = models.Match.objects.create(
#                     tourney_id=row[0],
#                     winner=models.Player.objects.get(
#                         player_id=row[7],
#                         tour=tour
#                     ),
#                     loser=models.Player.objects.get(
#                         player_id=row[15],
#                         tour=tour
#                     ),
#                 )
#             except models.Player.DoesNotExist:
#                 continue

#             match.tourney_name = row[1]
#             match.surface = row[2]
#             match.draw_size = None if row[3] is None or row[3] == '' else int(row[3])
#             match.tourney_level = row[4]
#             match.tourney_date = tourney_date
#             match.match_num = None if row[6] is None or row[6] == '' else int(row[6])
#             try:
#                 match.winner_seed = None if row[8] is None or row[8] == '' else int(row[8])
#             except:
#                 pass
#             match.winner_entry = row[9]
#             match.winner_name = row[10]
#             match.winner_hand = row[11]
#             # match.winner_ht = None if row[12] is None or row[12] == '' else int(row[12])
#             match.winner_ioc = row[13]
#             match.winner_age = None if row[14] is None or row[14] == '' else float(row[14])
#             try:
#                 match.loser_seed = None if row[16] is None or row[16] == '' else int(row[16])
#             except:
#                 pass
#             match.loser_entry = row[17]
#             match.loser_name = row[18]
#             match.loser_hand = row[19]
#             # match.loser_ht = None if row[20] is None or row[20] == '' else int(row[20])
#             match.loser_ioc = row[21]
#             match.loser_age = None if row[22] is None or row[22] == '' else float(row[22])
#             match.score = row[23]
#             match.best_of = None if row[24] is None or row[24] == '' else int(row[24])
#             match.round = row[25]
#             match.minutes = None if row[26] is None or row[26] == '' else int(row[26])
#             match.w_ace = None if row[27] is None or row[27] == '' else int(row[27])
#             match.w_df = None if row[28] is None or row[28] == '' else int(row[28])
#             match.w_svpt = None if row[29] is None or row[29] == '' else int(row[29])
#             match.w_1stIn = None if row[30] is None or row[30] == '' else int(row[30])
#             match.w_1stWon = None if row[31] is None or row[31] == '' else int(row[31])
#             match.w_2ndWon = None if row[32] is None or row[32] == '' else int(row[32])
#             match.w_SvGms = None if row[33] is None or row[33] == '' else int(row[33])
#             match.w_bpSaved = None if row[34] is None or row[34] == '' else int(row[34])
#             match.w_bpFaced = None if row[35] is None or row[35] == '' else int(row[35])
#             match.l_ace = None if row[36] is None or row[36] == '' else int(row[36])
#             match.l_df = None if row[37] is None or row[37] == '' else int(row[37])
#             match.l_svpt = None if row[38] is None or row[38] == '' else int(row[38])
#             match.l_1stIn = None if row[39] is None or row[39] == '' else int(row[39])
#             match.l_1stWon = None if row[40] is None or row[40] == '' else int(row[40])
#             match.l_2ndWon = None if row[41] is None or row[41] == '' else int(row[41])
#             match.l_SvGms = None if row[42] is None or row[42] == '' else int(row[42])
#             match.l_bpSaved = None if row[43] is None or row[43] == '' else int(row[43])
#             match.l_bpFaced = None if row[44] is None or row[44] == '' else int(row[44])
#             match.winner_rank = None if row[45] is None or row[45] == '' else int(row[45])
#             match.winner_rank_points = None if row[46] is None or row[46] == '' else int(row[46])
#             match.loser_rank = None if row[47] is None or row[47] == '' else int(row[47])
#             match.loser_rank_points = None if row[48] is None or row[48] == '' else int(row[48])
#             match.save()
                
#             print(match)


# @shared_task
# def get_pinn_odds(task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)
#         update_time = datetime.datetime.now()
#         matchup_url = 'https://guest.api.arcadia.pinnacle.com/0.1/sports/33/matchups'
#         odds_url = 'https://guest.api.arcadia.pinnacle.com/0.1/sports/33/markets/straight?primaryOnly=false'
#         response = requests.get(matchup_url, headers={'x-api-key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'})
        
#         matchups = response.json()
#         for matchup in matchups:
#             if matchup.get('parent') == None and 'special' not in matchup:
#                 try:
#                     match = models.PinnacleMatch.objects.get(id=matchup.get('id'))
#                 except models.PinnacleMatch.DoesNotExist:
#                     match = models.PinnacleMatch.objects.create(
#                         id=matchup.get('id'),
#                         event=matchup.get('league').get('name'),
#                         home_participant=matchup.get('participants')[0].get('name'),
#                         away_participant=matchup.get('participants')[1].get('name'),
#                         start_time=datetime.datetime.strptime(matchup.get('startTime'), '%Y-%m-%dT%H:%M:%SZ')
#                     )

#         response = requests.get(odds_url, headers={'x-api-key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'})
#         odds_list = response.json()
#         for odds in odds_list:
#             if odds.get('type') == 'moneyline' and odds.get('period') == 0:
#                 try:
#                     match = models.PinnacleMatch.objects.get(id=odds.get('matchupId'))
#                     (pinnacle_odds, _) = models.PinnacleMatchOdds.objects.get_or_create(
#                         match=match,
#                         create_at=update_time
#                     )
#                     pinnacle_odds.home_price=odds.get('prices')[0].get('price')
#                     pinnacle_odds.away_price=odds.get('prices')[1].get('price')
#                     pinnacle_odds.save()
#                 except models.PinnacleMatch.DoesNotExist:
#                     pass
#             elif odds.get('type') == 'spread' and odds.get('period') == 0:
#                 try:
#                     match = models.PinnacleMatch.objects.get(id=odds.get('matchupId'))
#                     (pinnacle_odds, _) = models.PinnacleMatchOdds.objects.get_or_create(
#                         match=match,
#                         create_at=update_time
#                     )
#                     if pinnacle_odds.home_spread == 0.0:
#                         pinnacle_odds.home_spread=odds.get('prices')[0].get('points')
#                         pinnacle_odds.away_spread=odds.get('prices')[1].get('points')
#                         pinnacle_odds.save()
#                 except models.PinnacleMatch.DoesNotExist:
#                     pass

#         task.status = 'success'
#         task.content = 'Pinnacle odds updated.'
#         task.save()
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem finding matches for slate: {e}'
#             task.save()

#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def find_slate_matches(slate_id, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)

#         # Task implementation goes here
#         slate = models.Slate.objects.get(id=slate_id)
#         slate.find_matches()

#         task.status = 'success'
#         task.content = f'{slate.matches.all().count()} matches found'
#         task.save()
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem finding matches for slate: {e}'
#             task.save()

#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def process_slate_players(slate_id, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)

#         # Task implementation goes here
#         slate = models.Slate.objects.get(id=slate_id)
        
#         with open(slate.salaries.path, mode='r') as salaries_file:
#             csv_reader = csv.DictReader(salaries_file)

#             success_count = 0
#             missing_players = []

#             for row in csv_reader:
#                 if slate.site == 'draftkings':
#                     player_id = row['ID']
#                     player_name = row['Name']
#                     player_salary = int(row['Salary'])
#                 else:
#                     raise Exception(f'{slate.site} is not supported yet.')

#                 alias = models.Alias.find_alias(player_name, slate.site)
                
#                 if alias is not None:
#                     try:
#                         slate_player = models.SlatePlayer.objects.get(
#                             slate=slate,
#                             slate_player_id=player_id
#                         )
#                     except models.SlatePlayer.DoesNotExist:
#                         slate_player = models.SlatePlayer(
#                             slate=slate,
#                             slate_player_id=player_id
#                         )

#                     slate_player.name = alias.get_alias(slate.site)
#                     slate_player.salary = player_salary
#                     slate_player.player = alias.player
#                     slate_player.save()

#                     success_count += 1
#                 else:
#                     missing_players.append(player_name)

#         task.status = 'success'
#         task.content = '{} players have been successfully added to {}.'.format(success_count, str(slate)) if len(missing_players) == 0 else '{} players have been successfully added to {}. {} players could not be identified.'.format(success_count, str(slate), len(missing_players))
#         task.link = '/admin/tennis/missingalias/' if len(missing_players) > 0 else None
#         task.save()
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem processing slate players: {e}'
#             task.save()

#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def simulate_match(match_id, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)

#         slate_match = models.SlateMatch.objects.get(id=match_id)
#         common_opponents = models.Player.objects.filter(
#             id__in=slate_match.common_opponents(slate_match.surface)
#         )

#         def getBigPointProb(server):
#             if server==p1:
#                 return p1_big_point
#             elif server==p2:
#                 return p2_big_point
#             else:
#                 print("Error")
                
#         def isBigPoint(server_points, returner_points, tiebreak):
#             #server_next_point = server_points+1
#             server_next_point = server_points
#             #print(server_next_point)
#             if tiebreak==False:
#                 if server_next_point >= 3 and (server_next_point - returner_points) >= 1:
#                     # print("game point")
#                     return True
#             else:
#                 if server_next_point >= 6 and abs(server_next_point - returner_points) >= 1:
#                     # print("set point")
#                     return True

#         def getScore(pointsServer, pointsReturner, server_games, returner_games, completed_sets, tiebreaker):
#             in_game = ['15', '30', '40']
#             extra = ['D', 'A']
            
#             display_server='0'
#             display_returner='0'
            
#             if tiebreaker==False:
#                 if pointsServer==0:
#                     display_server='0'
#                 elif pointsServer>0 and pointsServer<4:
#                     display_server=in_game[pointsServer-1]
#                 elif pointsServer>=4:
#                     #clean_pointsServer = pointsServer-4
#                     display_server = 'D'

#                 if pointsReturner==0:
#                     display_returner='0'
#                 elif pointsReturner>0 and pointsReturner<4:
#                     display_returner=in_game[pointsReturner-1]
#                 elif pointsReturner>=4:
#                     #clean_pointsReturner = pointsReturner-4
#                     display_returner = 'D'
                
#                 if (pointsServer>=4 and pointsReturner<4) or (pointsServer<4 and pointsReturner>=4):
#                     display_server='D'
#                     display_returner='D'

#                 if display_server=='D' and display_server=='D':
#                     if pointsServer>pointsReturner:
#                         display_server='A'
#                     elif pointsReturner>pointsServer:
#                         display_returner='A'

#                 if (display_server=='A' and display_returner=='A') or (display_server=='40' and display_returner=='40'):
#                     display_server = 'D'
#                     display_returner = 'D'
#                 if (display_server=='A' and display_returner=='40'):
#                     display_server = 'A'
#                     display_returner = 'D'
#                 if (display_server=='40' and display_returner=='A'):
#                     display_server = 'D'
#                     display_returner = 'A'
#             else:
#                 display_server = str(pointsServer)
#                 display_returner = str(pointsReturner)
            
#             if len(completed_sets)==0:
#                 pass
#                 # print(display_server+"-"+display_returner+"|"+"["+str(server_games)+"-"+str(returner_games)+"]")
#             else:
#                 completed = ""
#                 for sets in completed_sets:
#                     completed = completed+" "+str(sets[0])+":"+str(sets[1])
#                 # print(display_server+"-"+display_returner+"|"+str(completed)+"["+str(server_games)+":"+str(returner_games)+"]")

#         def player_serve(server, returner, server_prob, returner_prob, gamesMatch, S, server_points_match, returner_points_match, server_games, returner_games, server_pointsGame, returner_pointsGame, completed_sets):
#             ace = False
#             double_fault = False
#             broken = False

#             if isBigPoint(server_pointsGame, returner_pointsGame, False):
#                 server_prob = getBigPointProb(server)
#             if random() < server_prob:
#                 # print(server+" ", end = "")
#                 getScore(server_pointsGame, returner_pointsGame, server_games, returner_games, completed_sets, False)
#                 server_pointsGame += 1
#                 server_points_match += 1

#                 if (server == p1 and random() < p1_ace) or (server == p2 and random() < p2_ace):
#                     ace = True
#             else:
#                 # print(server+" ", end = "")
#                 getScore(server_pointsGame, returner_pointsGame, server_games, returner_games, completed_sets, False)
#                 returner_pointsGame += 1
#                 returner_points_match += 1

#                 if (server == p1 and random() < p1_df) or (server == p2 and random() < p2_df):
#                     double_fault = True
            
#             # If this point ended a game, calculate game values
#             if max(server_pointsGame, returner_pointsGame) >= 4 and abs(server_pointsGame - returner_pointsGame) > 1:
#                 # print("\t", server + ":", str(server_pointsGame) + ",", returner + ":", returner_pointsGame, end = "")
#                 if server_pointsGame > returner_pointsGame:
#                     server_games += 1
#                     # print()
#                 else:
#                     returner_games += 1
#                     broken = True
#                 gamesMatch += 1
#                 return server_games, returner_games, gamesMatch, S, server_points_match, returner_points_match, server_pointsGame, returner_pointsGame, ace, double_fault, broken

#             return server_games, returner_games, gamesMatch, S, server_points_match, returner_points_match, server_pointsGame, returner_pointsGame, ace, double_fault, broken

#         def simulateSet(a, b, gamesMatch, S, pointsMatch1, pointsMatch2, completed_sets):
#             S += 1
#             gamesSet1 = 0
#             gamesSet2 = 0
#             breaks1, breaks2 = 0, 0
#             aces1, aces2 = 0, 0
#             doubles1, doubles2 = 0, 0
#             while (max(gamesSet1, gamesSet2) < 6 or abs(gamesSet1 - gamesSet2) < 2) and gamesSet1 + gamesSet2 < 12: #Conditions to play another Game in this Set
#                 pointsGame1 = 0
#                 pointsGame2 = 0
#                 #player 1 serves
#                 while gamesMatch % 2 == 0:
#                     gamesSet1, gamesSet2, gamesMatch, S, pointsMatch1, pointsMatch2, pointsGame1, pointsGame2, ace, double_fault, broken = player_serve(p1, p2, a, b, gamesMatch, S, pointsMatch1, pointsMatch2, gamesSet1, gamesSet2, pointsGame1, pointsGame2, completed_sets)
#                     if ace:
#                         aces1 += 1
#                     if double_fault:
#                         doubles1 += 1
#                     if broken:
#                         breaks2 += 1
                    
#                 pointsGame1 = 0
#                 pointsGame2 = 0
#                 #player 2 serves, but we also incorporate in logic to end the set
#                 while gamesMatch % 2 == 1 and (max(gamesSet1, gamesSet2) < 6 or abs(gamesSet1 - gamesSet2) < 2) and gamesSet1 + gamesSet2 < 12:
#                     gamesSet2, gamesSet1, gamesMatch, S, pointsMatch2, pointsMatch1, pointsGame2, pointsGame1, ace, double_fault, broken = player_serve(p2, p1, b, a, gamesMatch, S, pointsMatch2, pointsMatch1, gamesSet2, gamesSet1, pointsGame2, pointsGame1, completed_sets)
#                     if ace:
#                         aces2 += 1
#                     if double_fault:
#                         doubles2 += 1
#                     if broken:
#                         breaks1 += 1
#             #at 6 games all we go to a tie breaker
#             # if gamesSet1 == 6 and gamesSet2 == 6:
#             #     print("Set", S, "is 6-6 and going to a Tiebreaker.")
            
#             return gamesSet1, gamesSet2, gamesMatch, S, pointsMatch1, pointsMatch2, aces1, aces2, doubles1, doubles2, breaks1, breaks2

#         def simulateTiebreaker(player1, player2, a, b, gamesMatch, pointsMatch1, pointsMatch2, completed_sets):
#             pointsTie1, pointsTie2 = 0, 0
#             aces1, aces2 = 0, 0
#             doubles1, doubles2 = 0, 0

#             while max(pointsTie1, pointsTie2) < 7 or abs(pointsTie1 - pointsTie2) < 2:
#                 #player 1 will server first
#                 if gamesMatch % 2 == 0:
#                     while (pointsTie1 + pointsTie2) % 4 == 0 or (pointsTie1 + pointsTie2) % 4 == 3:
#                         server_prob = a
#                         if isBigPoint(pointsTie1, pointsTie2, True):
#                             server_prob=getBigPointProb(player1)
#                         if random() < server_prob:
#                             # print(player1+" ", end = "")
#                             getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
#                             pointsTie1 += 1
#                             pointsMatch1 += 1

#                             if random() < p1_ace:
#                                 aces1 += 1
#                         else:
#                             getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
#                             pointsTie2 += 1
#                             pointsMatch2 += 1

#                             if random() < p1_df:
#                                 doubles1 += 1
#                         if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
#                             # print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
#                             gamesMatch += 1
#                             break 
#                     while (max(pointsTie1, pointsTie2) < 7 or abs(pointsTie1 - pointsTie2) < 2) and ((pointsTie1 + pointsTie2) % 4 == 1 or (pointsTie1 + pointsTie2) % 4 == 2): # Conditions to continue Tiebreaker (race to 7, win by 2) and Player 2 serves (points 4N+1 and 4N+2)
#                         server_prob = b
#                         if isBigPoint(pointsTie2, pointsTie1, True):
#                             server_prob=getBigPointProb(player2)
#                         if random() < server_prob:
#                             #print(player2+" ", end = "")
#                             getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
#                             pointsTie2 += 1
#                             pointsMatch2 += 1

#                             if random() < p2_ace:
#                                 aces2 += 1
#                         else:
#                             getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
#                             pointsTie1 += 1
#                             pointsMatch1 += 1

#                             if random() < p2_df:
#                                 doubles2 += 1
#                         if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
#                             # print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
#                             break
                
#                 #player 2 will server first
#                 if gamesMatch % 2 == 1:
#                     while (pointsTie1 + pointsTie2) % 4 == 1 or (pointsTie1 + pointsTie2) % 4 == 2:
#                         server_prob =  a
#                         if isBigPoint(pointsTie1, pointsTie2, True):
#                             server_prob=getBigPointProb(player1)
#                         if random() < server_prob:
#                             #print(player1+" ", end = "")
#                             getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
#                             pointsTie1 += 1
#                             pointsMatch1 += 1

#                             if random() < p1_ace:
#                                 aces1 += 1
#                         else:
#                             getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
#                             pointsTie2 += 1
#                             pointsMatch2 += 1

#                             if random() < p1_df:
#                                 doubles1 += 1
#                         # if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
#                         #     print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
#                         #     break 
#                     while (max(pointsTie2, pointsTie1) < 7 or abs(pointsTie1 - pointsTie2) < 2) and ((pointsTie1 + pointsTie2) % 4 == 0 or (pointsTie1 + pointsTie2) % 4 == 3): # Conditions to continue Tiebreaker (race to 7, win by 2) and Player 2 serves (points 4N and 4N+3)
#                         server_prob =  b
#                         if isBigPoint(pointsTie2, pointsTie1, True):
#                             server_prob=getBigPointProb(player2)
#                         if random() < server_prob:
#                             #print(player2+" ", end = "")
#                             getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
#                             pointsTie2 += 1
#                             pointsMatch2 += 1

#                             if random() < p2_ace:
#                                 aces2 += 1
#                         else:
#                             getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
#                             pointsTie1 += 1
#                             pointsMatch1 += 1

#                             if random() < p2_df:
#                                 doubles2 += 1
#                         # if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
#                         #     print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
#                         #     break                             
#             gamesMatch += 1
#             return pointsTie1, pointsTie2, gamesMatch, pointsMatch1, pointsMatch2, aces1, aces2, doubles1, doubles2

#         def printSetMatchSummary(p1, p2, gamesSet1, gamesSet2, S, pointsTie1, pointsTie2, setsMatch1, setsMatch2):
#             if gamesSet1 > gamesSet2:
#                 setsMatch1 += 1
#                 # print(p1.upper(), "wins Set", str(S) + ":", gamesSet1, "games to", str(gamesSet2) + ".")
#             elif gamesSet2 > gamesSet1:
#                 setsMatch2 += 1
#                 # print(p2.upper(), "wins Set", str(S) + ":", gamesSet2, "games to", str(gamesSet1) + ".")
#             elif gamesSet1 == gamesSet2:
#                 if pointsTie1 > pointsTie2:
#                     setsMatch1 += 1
#                     # print(p1.upper(), "wins Set", str(S) + ": 7 games to 6 (" + str(pointsTie1) + "-" + str(pointsTie2) + ").")
#                 else:
#                     setsMatch2 += 1
#                     # print(p2.upper(), "wins Set", str(S) + ": 7 games to 6 (" + str(pointsTie2) + "-" + str(pointsTie1) + ").")
#             # print("After", S, "Sets:", p1, str(setsMatch1) + ",", p2, str(setsMatch2) + ".\n")   
#             return setsMatch1, setsMatch2

#         def pointsMatchSummary(p1, p2, setsMatch1, setsMatch2, pointsMatch1, pointsMatch2):
#             if setsMatch1 == sets_to_win:
#                 # print(p1.upper(), "(" + str(a) + ")", "beat", p2, "(" + str(b) + ") by", setsMatch1, "Sets to", str(setsMatch2) + ".")
#                 return p1
#             else:
#                 # print(p2.upper(), "(" + str(b) + ")", "beat", p1, "(" + str(a) + ") by", setsMatch2, "Sets to", str(setsMatch1) + ".")
#                 return p2

#         #initialize player one and two
#         #a is ps1 and b is ps2
#         #p1_big_point and p2_big_point are the probability
#         #of p1 and p2 winning on a big point, respectively
#         try:
#             alias1 = models.Alias.objects.get(pinn_name=slate_match.match.home_participant)
#         except models.Alias.DoesNotExist:
#             print(f'{slate_match.home_participant} does not have an alias.')
#             return
#         try:
#             alias2 = models.Alias.objects.get(pinn_name=slate_match.match.away_participant)
#         except models.Alias.DoesNotExist:
#             print(f'{slate_match.away_participant} does not have an alias.')
#             return

#         player_1 = alias1.player
#         player_2 = alias2.player
#         p1 = player_1.full_name
#         p2 = player_2.full_name

#         if common_opponents.count() >= 3:
#             a_points_won = [
#                 player_1.get_points_won_rate(
#                     vs_opponent=common_opponent,
#                     timeframe_in_weeks=52*2,
#                     on_surface=slate_match.surface
#                 ) for common_opponent in common_opponents        
#             ]
#             b_points_won = [
#                 player_2.get_points_won_rate(
#                     vs_opponent=common_opponent,
#                     timeframe_in_weeks=52*2,
#                     on_surface=slate_match.surface
#                 ) for common_opponent in common_opponents        
#             ]

#             spw_a = [d.get('spw') for d in a_points_won if d is not None]
#             spw_b = [d.get('spw') for d in b_points_won if d is not None]

#             a = numpy.average(spw_a)
#             b = numpy.average(spw_b)

#             p1_ace = player_1.get_ace_pct()
#             p2_ace = player_2.get_ace_pct()
#             p1_df = player_1.get_df_pct()
#             p2_df = player_2.get_df_pct()
#         else:
#             a = player_1.get_points_won_rate(
#                 timeframe_in_weeks=52*2,
#                 on_surface=slate_match.surface
#             ).get('spw')
#             b = player_2.get_points_won_rate(
#                 timeframe_in_weeks=52*2,
#                 on_surface=slate_match.surface
#             ).get('spw')

#             p1_ace = player_1.get_ace_pct(timeframe=52*2)
#             p2_ace = player_2.get_ace_pct(timeframe=52*2)
#             p1_df = player_1.get_df_pct(timeframe=52*2)
#             p2_df = player_2.get_df_pct(timeframe=52*2)

#         p1_big_point = a
#         p2_big_point = b

#         best_of = slate_match.best_of
#         sets_to_win = math.ceil(best_of/2)
#         p1_wins = 0
#         p2_wins = 0
#         p1_scores = []
#         p2_scores = []
#         w_p1_scores = []
#         w_p2_scores = []

#         for _ in range(0, 10000):
#             completed_sets = []
#             S = 0
#             gamesMatch = 0

#             #in all subscripted variables
#             #the subscript refers to the player
#             #for example, setsMatch1 is sets won by player1 and
#             #setsMatch2 is sets won by player2
#             pointsMatch1, pointsMatch2 = 0, 0
#             gamesMatch1, gamesMatch2 = 0, 0
#             setsMatch1, setsMatch2 = 0, 0
#             pointsTie1, pointsTie2 = 0, 0
#             pointsGame1, pointsGame2 = 0, 0
#             total_breaks1, total_breaks2 = 0, 0
#             total_aces1, total_aces2 = 0, 0
#             total_doubles1, total_doubles2 = 0, 0
#             clean_sets1, clean_sets2 = 0, 0

#             while S < best_of and max(setsMatch1, setsMatch2) < sets_to_win:
#                 gamesSet1, gamesSet2, gamesMatch, S, pointsMatch1, pointsMatch2, aces1, aces2, doubles1, doubles2, breaks1, breaks2 = simulateSet(a, b, gamesMatch, S, 
#                     pointsMatch1, pointsMatch2, 
#                     completed_sets
#                 )
#                 total_aces1 += aces1
#                 total_aces2 += aces2
#                 total_doubles1 += doubles1
#                 total_doubles2 += doubles2
#                 total_breaks1 += breaks1
#                 total_breaks2 += breaks2

#                 if gamesSet1 == 0:
#                     clean_sets2 += 1
#                 elif gamesSet2 == 0:
#                     clean_sets1 += 1

#                 # print()
#                 if gamesSet1 == 6 and gamesSet2 == 6:
#                     pointsTie1, pointsTie2, gamesMatch, pointsMatch1, pointsMatch2, aces1, aces2, doubles1, doubles2 = simulateTiebreaker(p1, p2, a, b, 
#                         gamesMatch, pointsMatch1, 
#                         pointsMatch2, 
#                         completed_sets
#                     )
#                     total_aces1 += aces1
#                     total_aces2 += aces2
#                     total_doubles1 += doubles1
#                     total_doubles2 += doubles2
                
#                 setsMatch1, setsMatch2 = printSetMatchSummary(p1, p2, gamesSet1, gamesSet2, 
#                                                             S, pointsTie1, pointsTie2, 
#                                                             setsMatch1, setsMatch2)
                
#                 if gamesSet1 == 6 and gamesSet2 == 6:
#                     if pointsTie1 > pointsTie2:
#                         completed_sets.append([gamesSet1+1, gamesSet2])
#                     else:
#                         completed_sets.append([gamesSet1, gamesSet2+1])
#                 else:
#                     completed_sets.append([gamesSet1, gamesSet2])

#                 gamesMatch1 += gamesSet1
#                 gamesMatch2 += gamesSet2

#             scoring = models.SITE_SCORING.get(slate_match.slate.site).get(str(slate_match.best_of))
#             winner = pointsMatchSummary(p1, p2, setsMatch1, setsMatch2, pointsMatch1, pointsMatch2)
            
#             # print(scoring)
#             # print(f'gamesMatch1 = {gamesMatch1}')
#             # print(f'gamesMatch2 = {gamesMatch2}')
#             # print(f'setsMatch1 = {setsMatch1}')
#             # print(f'setsMatch2 = {setsMatch2}')
#             # print(f'total_aces1 = {total_aces1}')
#             # print(f'total_aces2 = {total_aces2}')
#             # print(f'total_doubles1 = {total_doubles1}')
#             # print(f'total_doubles2 = {total_doubles2}')
#             # print(f'total_breaks1 = {total_breaks1}')
#             # print(f'total_breaks2 = {total_breaks2}')

#             # base scoring
#             score1 = scoring.get('match_played') + (scoring.get('game_won') * gamesMatch1) + (scoring.get('game_lost') * gamesMatch2) + (scoring.get('set_won') * setsMatch1) + (scoring.get('set_lost') * setsMatch2) + (scoring.get('ace') * total_aces1) + (scoring.get('double_fault') * total_doubles1) + (scoring.get('break') * total_breaks1)
#             score2 = scoring.get('match_played') + (scoring.get('game_won') * gamesMatch2) + (scoring.get('game_lost') * gamesMatch1) + (scoring.get('set_won') * setsMatch2) + (scoring.get('set_lost') * setsMatch1) + (scoring.get('ace') * total_aces2) + (scoring.get('double_fault') * total_doubles2) + (scoring.get('break') * total_breaks2)

#             # winner scoring
#             if winner == p1:
#                 p1_wins += 1
#                 score1 += scoring.get('match_won')

#                 if setsMatch2 == 0:
#                     score1 += scoring.get('straight_sets')
#             else:
#                 p2_wins += 1
#                 score2 += scoring.get('match_won')

#                 if setsMatch1 == 0:
#                     score2 += scoring.get('straight_sets')
                
#             # bonuses
#             score1 += scoring.get('clean_set') * clean_sets1
#             score2 += scoring.get('clean_set') * clean_sets2

#             if total_doubles1 == 0:
#                 score1 += scoring.get('no_double_faults')
#             if total_doubles2 == 0:
#                 score2 += scoring.get('no_double_faults')

#             if total_aces1 >= scoring.get('aces_threshold'):
#                 score1 += scoring.get('aces')
#             if total_aces2 >= scoring.get('aces_threshold'):
#                 score2 += scoring.get('aces')

#             p1_scores.append(score1)
#             p2_scores.append(score2)

#             if winner == p1:
#                 w_p1_scores.append(score1)
#             else:
#                 w_p2_scores.append(score2)

#         projection1 = models.SlatePlayerProjection.objects.get(
#             slate_player__slate=slate_match.slate,
#             slate_player__name=alias1.get_alias(slate_match.slate.site)
#         )
#         projection1.sim_scores = p1_scores
#         projection1.w_sim_scores = w_p1_scores
#         projection1.projection = numpy.median(p1_scores)
#         projection1.ceiling = numpy.percentile([float(i) for i in p1_scores], 90)
#         projection1.s75 = numpy.percentile([float(i) for i in p1_scores], 75)
#         projection1.sim_win_pct = p1_wins/10000
#         projection1.save()
        
#         projection2 = models.SlatePlayerProjection.objects.get(
#             slate_player__slate=slate_match.slate,
#             slate_player__name=alias2.get_alias(slate_match.slate.site)
#         )
#         projection2.sim_scores = p2_scores
#         projection2.w_sim_scores = w_p2_scores
#         projection2.projection = numpy.median(p2_scores)
#         projection2.ceiling = numpy.percentile([float(i) for i in p2_scores], 90)
#         projection2.s75 = numpy.percentile([float(i) for i in p2_scores], 75)
#         projection2.sim_win_pct = p2_wins/10000
#         projection2.save()

#         task.status = 'success'
#         task.content = f'Simulation of {slate_match} complete.'
#         task.save()
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem simulating {slate_match}: {e}'
#             task.save()

#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def calculate_target_scores(slate_id, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)

#         # Task implementation goes here
#         slate = models.Slate.objects.get(id=slate_id)
#         all_scores = numpy.array(
#             [
#                 p.sim_scores for p in models.SlatePlayerProjection.objects.filter(
#                     slate_player__slate=slate
#                 )
#             ]
#         )

#         n = 8
#         df_scores = pandas.DataFrame(all_scores, dtype=float)
#         top_scores = df_scores.max(axis = 0)
#         target_scores = [df_scores[c].nlargest(n).values[n-1] for c in df_scores.columns]

#         slate.top_score = numpy.mean(top_scores.to_list())
#         slate.target_score = numpy.mean(target_scores)
#         slate.save()
        
#         task.status = 'success'
#         task.content = f'Target scores calculated'
#         task.save()
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem calculating target scores: {e}'
#             task.save()

#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def build_lineups(build_id, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)

#         # Task implementation goes here
#         build = models.SlateBuild.objects.get(id=build_id)
#         lineups = optimize.optimize(build.slate.site, models.SlatePlayerProjection.objects.filter(slate_player__slate=build.slate), build.configuration, build.total_lineups * build.configuration.lineup_multiplier)

#         for lineup in lineups:
#             if build.slate.site == 'draftkings':
#                 lineup = models.SlateBuildLineup.objects.create(
#                     build=build,
#                     player_1=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[0].id, slate_player__slate=build.slate),
#                     player_2=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[1].id, slate_player__slate=build.slate),
#                     player_3=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[2].id, slate_player__slate=build.slate),
#                     player_4=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[3].id, slate_player__slate=build.slate),
#                     player_5=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[4].id, slate_player__slate=build.slate),
#                     player_6=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[5].id, slate_player__slate=build.slate),
#                     total_salary=lineup.salary_costs
#                 )
#                 # lineup = models.SlateBuildLineup.objects.create(
#                 #     build=build,
#                 #     player_1=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[0].name, slate_player__slate=build.slate),
#                 #     player_2=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[1].name, slate_player__slate=build.slate),
#                 #     player_3=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[2].name, slate_player__slate=build.slate),
#                 #     player_4=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[3].name, slate_player__slate=build.slate),
#                 #     player_5=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[4].name, slate_player__slate=build.slate),
#                 #     player_6=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[5].name, slate_player__slate=build.slate),
#                 #     total_salary=lineup.spent()
#                 # )
#                 lineup.implied_win_pct = lineup.player_1.implied_win_pct * lineup.player_2.implied_win_pct * lineup.player_3.implied_win_pct * lineup.player_4.implied_win_pct * lineup.player_5.implied_win_pct * lineup.player_6.implied_win_pct
#                 lineup.save()

#                 lineup.simulate()
#             else:
#                 raise Exception(f'{build.slate.site} is not available for building yet.')
        
#         task.status = 'success'
#         task.content = f'{build.lineups.all().count()} lineups created.'
#         task.save()
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem building lineups: {e}'
#             task.save()

#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def clean_lineups(build_id, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)

#         # Task implementation goes here
#         build = models.SlateBuild.objects.get(id=build_id)

#         ordered_lineups = build.lineups.all().order_by(f'-{build.configuration.clean_lineups_by}')
#         ordered_lineups.filter(id__in=ordered_lineups.values_list('pk', flat=True)[int(build.total_lineups):]).delete()
        
#         task.status = 'success'
#         task.content = 'Lineups cleaned.'
#         task.save()
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem cleaning lineups: {e}'
#             task.save()

#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def calculate_exposures(build_id, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)

#         # Task implementation goes here
#         build = models.SlateBuild.objects.get(id=build_id)
#         players = models.SlatePlayerProjection.objects.filter(
#             slate_player__slate=build.slate
#         )

#         for player in players:
#             exposure, _ = models.SlateBuildPlayerExposure.objects.get_or_create(
#                 build=build,
#                 player=player
#             )
#             exposure.exposure = build.lineups.filter(
#                 Q(
#                     Q(player_1=player) | 
#                     Q(player_2=player) | 
#                     Q(player_3=player) | 
#                     Q(player_4=player) | 
#                     Q(player_5=player) | 
#                     Q(player_6=player)
#                 )
#             ).count() / build.lineups.all().count()
#             exposure.save()
        
#         task.status = 'success'
#         task.content = 'Exposures calculated.'
#         task.save()
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem calculating exposures: {e}'
#             task.save()

#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def export_build_for_upload(build_id, result_path, result_url, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)
#         build = models.SlateBuild.objects.get(pk=build_id)

#         with open(result_path, 'w') as temp_csv:
#             build_writer = csv.writer(temp_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
#             build_writer.writerow(['P', 'P', 'P', 'P', 'P', 'P'])

#             lineups = build.lineups.all()

#             for lineup in lineups:
#                 if build.slate.site == 'draftkings':
#                     row = [
#                         f'{lineup.player_1.name} ({lineup.player_1.slate_player.slate_player_id})',
#                         f'{lineup.player_2.name} ({lineup.player_2.slate_player.slate_player_id})',
#                         f'{lineup.player_3.name} ({lineup.player_3.slate_player.slate_player_id})',
#                         f'{lineup.player_4.name} ({lineup.player_4.slate_player.slate_player_id})',
#                         f'{lineup.player_5.name} ({lineup.player_5.slate_player.slate_player_id})',
#                         f'{lineup.player_6.name} ({lineup.player_6.slate_player.slate_player_id})'
#                     ]
#                 else:
#                     raise Exception('{} is not a supported dfs site.'.format(build.slate.site)) 

#                 build_writer.writerow(row)

#         task.status = 'download'
#         task.content = result_url
#         task.save()
        
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem generating your export {e}'
#             task.save()
#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))

