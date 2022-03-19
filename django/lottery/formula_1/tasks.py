import csv
import datetime
import logging
import json
import math
from re import A
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

from random import random, uniform, randrange

from celery import shared_task, chord, group, chain
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages.api import success
from django.db.models.aggregates import Count, Sum, Avg
from django.db.models import Q, F, ExpressionWrapper, FloatField
from django.db import transaction

from configuration.models import BackgroundTask
from pydfs_lineup_optimizer import Site, Sport, Player, get_optimizer

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

# @shared_task
# def update_driver_list():
#     try:
#         url = 'https://www.nascar.com/json/drivers/?limit=1000'
#         response = requests.get(url)

#         if response.status_code >= 300:
#             raise Exception(f'Error updating driver list: HTTP {response.status_code}')
        
#         data = response.json().get('response')
#         for d in data:
#             driver, _ = models.Driver.objects.get_or_create(
#                 driver_id=d.get('Driver_ID')
#             )

#             driver.driver_id = d.get('Driver_ID')
#             driver.first_name = d.get('First_Name')
#             driver.last_name = d.get('Last_Name')
#             driver.full_name = d.get('Full_Name')
#             driver.badge = d.get('Badge')
#             driver.badge_image = d.get('Badge_Image')
#             driver.manufacturer_image = d.get('Manufacturer')
#             driver.team = d.get('Team') if d.get('Team') != d.get('Badge') else None
#             driver.driver_image = d.get('Image')
#             driver.save()

#             alias, _ = models.Alias.objects.get_or_create(
#                 nascar_name=driver.full_name
#             )
#             alias.dk_name = driver.full_name if alias.dk_name is None else alias.dk_name
#             alias.fd_name = driver.full_name if alias.fd_name is None else alias.fd_name
#             alias.ma_name = driver.full_name if alias.ma_name is None else alias.ma_name
#             alias.save()

#     except Exception as e:
#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def update_race_list(race_year=2022):
#     try:
#         url = f'https://cf.nascar.com/cacher/{race_year}/race_list_basic.json'
#         response = requests.get(url)

#         if response.status_code >= 300:
#             raise Exception(f'Error updating race list: HTTP {response.status_code}')
        
#         data = response.json()

#         for series in data:
#             races = data[series]
#             for r in races:
#                 # get basic race data
#                 print(r.get('race_name'))

#                 race, _ = models.Race.objects.get_or_create(
#                     race_id=r.get('race_id')
#                 )
#                 race.series = r.get('series_id')
#                 race.race_season = r.get('race_season')
#                 race.race_name = r.get('race_name')
#                 race.race_type = r.get('race_type_id')
#                 race.restrictor_plate = r.get('restrictor_plate')

#                 track, _ = models.Track.objects.get_or_create(
#                     track_id=r.get('track_id')
#                 )

#                 track.track_name = r.get('track_name')
#                 track.save()

#                 race.track = track
#                 race.race_date = datetime.datetime.strptime(r.get('race_date'), '%Y-%m-%dT%H:%M:%S')
#                 race.qualifying_date = datetime.datetime.strptime(r.get('qualifying_date'), '%Y-%m-%dT%H:%M:%S')
#                 race.scheduled_distance = r.get('scheduled_distance')
#                 race.scheduled_laps = r.get('scheduled_laps')
#                 race.stage_1_laps = r.get('stage_1_laps')
#                 race.stage_2_laps = r.get('stage_2_laps')
#                 race.stage_3_laps = r.get('stage_3_laps')
#                 race.stage_4_laps = r.get('stage_4_laps') if r.get('stage_4_laps') is not None else 0
#                 race.save()
        
#         race_result_tasks = group([
#             update_race_results.si(race.race_id, race_year) for race in models.Race.objects.filter(race_season=race_year)
#         ])
#         lap_data_tasks = group([
#             update_lap_data_for_race.si(race.race_id, race_year) for race in models.Race.objects.filter(race_season=race_year)
#         ])
#         chain(race_result_tasks, lap_data_tasks)()

#     except Exception as e:
#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# @shared_task
# def update_race_results(race_id, race_year=2022):
#     race = models.Race.objects.get(race_id=race_id)

#     # get race results
#     race.results.all().delete()
#     race.cautions.all().delete()
#     race.infractions.all().delete()
#     weekend_url = f'https://cf.nascar.com/cacher/{race_year}/{race.series}/{race.race_id}/weekend-feed.json'

#     results_response = requests.get(weekend_url)
#     if results_response.status_code >= 300:
#         print(f'Cannot retrieve results for {race.race_name}: HTTP {results_response.status_code}')
#         return
    
#     results_data = results_response.json()
#     weekend_race = results_data.get('weekend_race')

#     for wr in weekend_race:
#         race.num_cars = wr.get('number_of_cars_in_field')
#         race.num_lead_changes = wr.get('number_of_lead_changes')
#         race.num_leaders = wr.get('number_of_leaders')
#         race.num_cautions = wr.get('number_of_cautions')
#         race.num_caution_laps = wr.get('number_of_caution_laps')
#         race.save()

#         results = wr.get('results')
#         for result in results:
#             try:
#                 driver = models.Driver.objects.get(driver_id=result.get('driver_id'))
#                 driver.manufacturer = result.get('car_make')
#                 driver.team = result.get('team_name')
#                 driver.save()

#                 models.RaceResult.objects.create(
#                     race=race,
#                     driver=models.Driver.objects.get(driver_id=result.get('driver_id')),
#                     finishing_position=result.get('finishing_position'),
#                     starting_position=result.get('starting_position'),
#                     laps_led=result.get('laps_led'),
#                     times_led=result.get('times_led'),
#                     laps_completed=result.get('laps_completed'),
#                     finishing_status=result.get('finishing_status'),
#                     disqualified=result.get('disqualified')
#                 )
#             except:
#                 pass

#         caution_segments = wr.get('caution_segments')
#         for caution in caution_segments:
#             try:
#                 models.RaceCautionSegment.objects.create(
#                     race=race,
#                     start_lap=caution.get('start_lap'),
#                     end_lap=caution.get('end_lap'),
#                     reason=caution.get('reason'),
#                     comment=caution.get('comment')
#                 )
#             except:
#                 pass

#         infractions = wr.get('infractions')
#         for infraction in infractions:
#             try:
#                 models.RaceInfraction.objects.create(
#                     race=race,
#                     driver=models.Driver.objects.get(driver_id=infraction.get('driver_id')),
#                     lap=infraction.get('lap'),
#                     lap_assessed=infraction.get('lap_assessed'),
#                     infraction=infraction.get('infraction'),
#                     penalty=infraction.get('penalty'),
#                     notes=infraction.get('notes')
#                 )
#             except:
#                 pass


# @shared_task
# def update_lap_data_for_race(race_id, race_year=2022):
#     race = models.Race.objects.get(race_id=race_id)

#     # get lap data
#     race.driver_laps.all().delete()
#     lap_times_url = f'https://cf.nascar.com/cacher/{race_year}/{race.series}/{race.race_id}/lap-times.json'

#     laps_response = requests.get(lap_times_url)
#     if laps_response.status_code >= 300:
#         print(f'Cannot retrieve results for {race.race_name}: HTTP {laps_response.status_code}')
#         return

#     laps_data = laps_response.json().get('laps')
#     for ld in laps_data:
#         driver = models.Driver.objects.get(driver_id=ld.get('NASCARDriverID'))
#         for l in ld.get('Laps'):
#             # check for caution segment
#             caution_segments = models.RaceCautionSegment.objects.filter(
#                 race=race,
#                 start_lap__gte=l.get('Lap'),
#                 end_lap__lte=l.get('Lap')
#             )
            
#             if caution_segments.count() < 0:
#                 try:
#                     models.RaceDriverLap.objects.create(
#                         race=race,
#                         driver=driver,
#                         lap=l.get('Lap'),
#                         lap_time=l.get('LapTime'),
#                         lap_speed=l.get('LapSpeed'),
#                         running_pos=l.get('RunningPos')
#                     )
#                 except:
#                     pass


# # Exports

# @shared_task
# def export_tracks(track_ids, result_path, result_url, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)

#         tracks = models.Track.objects.filter(track_id__in=track_ids)
#         df_tracks = pandas.DataFrame.from_records(tracks.values())
#         df_tracks.to_csv(result_path)

#         task.status = 'download'
#         task.content = result_url
#         task.save()

#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was an error exporting track data: {e}'
#             task.save()

#         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
#         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# Sims

@shared_task
def export_sim_template(sim_id, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        race_sim = models.RaceSim.objects.get(id=sim_id)

        drivers = race_sim.get_drivers().all().annotate(
            name=F('driver__full_name'),
            team=F('driver__team')
        ).order_by('starting_position')

        df_drivers = pandas.DataFrame.from_records(drivers.values(
            'starting_position',
            'driver_id',
            'name',
            'team'
        ))
        df_drivers['speed_min'] = ''
        df_drivers['speed_max'] = ''
        df_drivers['incident'] = ''
        df_drivers['ll_min'] = ''
        df_drivers['ll_max'] = ''

        df_race = pandas.DataFrame.from_records(models.RaceSim.objects.filter(id=sim_id).annotate(laps=F('race__scheduled_laps')).values(
            'll_mean',
            'laps'
        ))

        df_fl = pandas.DataFrame(data={
            'pct': [0 for _ in range (0, 20)],
            'fp': [i+1 for i in range (0, 20)]
        })

        df_ll = pandas.DataFrame(data={
            'min': [0 for _ in range (0, 20)],
            'max': [0 for _ in range (0, 20)],
            'fp': [i+1 for i in range (0, 20)]
        })

        print(df_drivers)
        with pandas.ExcelWriter(result_path) as writer:
            df_race.to_excel(writer, sheet_name='race')
            df_fl.to_excel(writer, sheet_name='fl')
            df_ll.to_excel(writer, sheet_name='ll')
            df_drivers.to_excel(writer, sheet_name='drivers')

        task.status = 'download'
        task.content = result_url
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error exporting sim template: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_sim_input_file(sim_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        race_sim = models.RaceSim.objects.get(id=sim_id)
        models.RaceSimDriver.objects.filter(sim=race_sim).delete()

        dk_salaries = None

        if bool(race_sim.dk_salaries):
            dk_salaries = pandas.read_csv(race_sim.dk_salaries.path, usecols= ['Name', 'ID', 'Roster Position', 'Salary'], index_col='ID')

        df_race = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='race')
        df_fl = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='fl')
        df_ll = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='ll')
        df_drivers = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='drivers')

        race_sim.race.scheduled_laps = df_race.loc[0, 'laps']
        race_sim.race.save()

        race_sim.ll_mean = df_race.loc[0, 'll_mean']
        race_sim.save()

        race_sim.fl_profiles.all().delete()
        for index in range(0, len(df_fl.index)):
            models.RaceSimFastestLapsProfile.objects.create(
                sim=race_sim,
                fp_rank=df_fl.at[index, 'fp'],
                probability=df_fl.at[index, 'pct']
            )

        race_sim.ll_profiles.all().delete()
        for index in range(0, len(df_ll.index)):
            models.RaceSimLapsLedProfile.objects.create(
                sim=race_sim,
                fp_rank=df_fl.at[index, 'fp'],
                pct_laps_led_min=df_ll.at[index, 'min'],
                pct_laps_led_max=df_ll.at[index, 'max']
            )

        race_sim.outcomes.filter(dk_position='D').delete()

        # Drivers
        for index in range(0, len(df_drivers.index)):
            driver = models.Driver.objects.get(driver_id=df_drivers.at[index, 'driver_id'])
            alias = models.Alias.find_alias(driver.full_name, 'f1')

            dk_salary = dk_salaries.loc[(dk_salaries.Name == alias.dk_name) & (dk_salaries['Roster Position'] == 'D'),'Salary'].values[0]

            models.RaceSimDriver.objects.create(
                sim=race_sim,
                driver=driver,
                dk_position='D',
                starting_position=df_drivers.at[index, 'starting_position'],
                dk_salary=dk_salary,
                speed_min=df_drivers.at[index, 'speed_min'],
                speed_max=df_drivers.at[index, 'speed_max'],
                incident_rate=df_drivers.at[index, 'incident'],
                pct_laps_led_min=df_drivers.at[index, 'll_min'],
                pct_laps_led_max=df_drivers.at[index, 'll_max']
            )

        # Drivers as CPT
        for index in range(0, len(df_drivers.index)):
            driver = models.Driver.objects.get(driver_id=df_drivers.at[index, 'driver_id'])
            alias = models.Alias.find_alias(driver.full_name, 'f1')

            dk_salary = dk_salaries.loc[(dk_salaries.Name == alias.dk_name) & (dk_salaries['Roster Position'] == 'CPT'),'Salary'].values[0]

            models.RaceSimDriver.objects.create(
                sim=race_sim,
                driver=driver,
                dk_position='CPT',
                dk_salary=dk_salary,
                speed_min=0,
                speed_max=0,
                incident_rate=0,
                pct_laps_led_min=0,
                pct_laps_led_max=0
            )

        # Constructors
        for constructor in models.Constructor.objects.all():
            dk_salary = dk_salaries.loc[(dk_salaries.Name.apply(lambda x: x.strip()) == constructor.name) & (dk_salaries['Roster Position'] == 'CNSTR'),'Salary'].values[0]

            models.RaceSimDriver.objects.create(
                sim=race_sim,
                constructor=constructor,
                dk_position='CNSTR',
                dk_salary=dk_salary,
                speed_min=0,
                speed_max=0,
                incident_rate=0,
                pct_laps_led_min=0,
                pct_laps_led_max=0
            )

        task.status = 'success'
        task.content = f'{race_sim} inputs processed.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error processing inputs for this sim: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# def get_speed_min(driver, current_speed_rank):
#     speed_delta = 10
#     speed_min = max(current_speed_rank - 5, driver.best_possible_speed)


@shared_task
def execute_sim(sim_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        race_sim = models.RaceSim.objects.get(id=sim_id)
        # chord([
        #     execute_sim_iteration.si(sim_id) for _ in range(0, race_sim.iterations)
        # ], sim_execution_complete.s(sim_id, task_id))()
        chain(
            chord([
                execute_sim_iteration.si(sim_id) for _ in range(0, race_sim.iterations)
            ], sim_execution_complete.s(sim_id, task_id)),
            find_driver_gto.si(
                race_sim.id,
                BackgroundTask.objects.create(
                    name=f'Find driver GTO for {race_sim}',
                    user=task.user
                ).id
            )
        )()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error simulating this race: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


def find_teammate_index(sim_drivers, driver):
    for index, d in enumerate(sim_drivers):
        if d.get_teammate() == driver:
            return index
    return -1


@shared_task
def execute_sim_iteration(sim_id):
    race_sim = models.RaceSim.objects.get(id=sim_id)
    drivers = race_sim.outcomes.filter(dk_position='D').order_by('starting_position', 'id')

    race_drivers = list(drivers.values_list('driver__driver_id', flat=True))  # tracks drivers still in race
    driver_ids = list(drivers.values_list('driver__driver_id', flat=True))
    driver_names = list(drivers.values_list('driver__full_name', flat=True))
    driver_starting_positions = list(drivers.values_list('starting_position', flat=True))

    driver_sp_mins = list(drivers.values_list('speed_min', flat=True))
    driver_sp_maxes = list(drivers.values_list('speed_max', flat=True))

    driver_fl = [0 for _ in drivers]
    driver_ll = [0 for _ in drivers]

    # 1. Assign driver DNFs (if any) by rand() < driver incident rate
    driver_dnfs = [1 if random() < driver.incident_rate else 0 for driver in drivers]

    # 2. Assign driver speed value as randbetween(speed min, speed max)
    sp_values = [randrange(driver.speed_min, driver.speed_max+1) + random() if driver_dnfs[index] < 1 else 9999 + random() for index, driver in enumerate(drivers)]

    # 3. Assign driver FP as rank(driver_speed_value)
    fp_ranks = scipy.stats.rankdata(sp_values, method='ordinal')

    # 4. Determine how many drivers get LL
    ll_laps = race_sim.race.scheduled_laps
    num_leaders = scipy.stats.poisson.rvs(race_sim.ll_mean) + 1

    # 5. Assign LL as randbetween(max(driver min, fp min), min(driver max, fp max))
    ll_vals = []  # holds actual LL values
    ll_pct_values = []  # holds LL pct values

    # -- determine the pct values to award
    for p in race_sim.ll_profiles.all().order_by('fp_rank')[:num_leaders]:
        driver_index = int(numpy.where(fp_ranks == p.fp_rank)[0][0])
        driver = drivers[driver_index]
        pct_min = max(driver.pct_laps_led_min, p.pct_laps_led_min)
        pct_max = min(driver.pct_laps_led_max, p.pct_laps_led_max)

        award_pct = randrange(int(pct_min*100), max(int(pct_max*100), 1) + 1, 1) if pct_min < pct_max else int(pct_min*100)
        ll_pct_values.append(award_pct)

    # -- scale values such that 100% is awarded and convert to actual LL values
    for index, v in enumerate(ll_pct_values):
        new_v = v/sum(ll_pct_values)
        new_v = int(new_v*ll_laps)  # actual value
        p = race_sim.ll_profiles.all().order_by('fp_rank')[index]
        driver_index = int(numpy.where(fp_ranks == p.fp_rank)[0][0])
        driver_ll[driver_index] = new_v

    # 6. Assign FL
    fl_prob = random()
    fp_rank = 0
    cum = 0
    for flp in race_sim.fl_profiles.all().order_by('fp_rank'):
        cum += flp.probability
        
        if fl_prob <= cum:
            fp_rank = flp.fp_rank
            break

    driver_index = int(numpy.where(fp_ranks == fp_rank)[0][0])
    driver_fl[driver_index] = 1

    driver_dk = [
        (models.SITE_SCORING.get('draftkings').get('place_differential').get(str(driver_starting_positions[index] - fp_ranks.tolist()[index])) + 
        models.SITE_SCORING.get('draftkings').get('fastest_lap') * driver_fl[index] + 
        models.SITE_SCORING.get('draftkings').get('finishing_position').get(str(fp_ranks.tolist()[index])) + 
        models.SITE_SCORING.get('draftkings').get('laps_led') * driver_ll[index] + 
        (models.SITE_SCORING.get('draftkings').get('classified') if driver_dnfs[index] == 0 else 0) +
        (models.SITE_SCORING.get('draftkings').get('defeated_teammate') if fp_ranks.tolist()[index] > fp_ranks.tolist()[find_teammate_index(drivers, d)] else 0)) for index, d in enumerate(drivers)
    ]


    # df_race = pandas.DataFrame({
    #     'driver_id': driver_ids,
    #     'driver': driver_names,
    #     'sp': driver_starting_positions,
    #     'speed_min': driver_sp_mins,
    #     'speed_max': driver_sp_maxes,
    #     'dnf': driver_dnfs,
    #     'speed': sp_values,
    #     'fp': fp_ranks,
    #     'fl': driver_fl,
    #     'll': driver_ll,
    #     'dk': driver_dk
    # })

    return {
        'dnf': driver_dnfs,
        'fp': fp_ranks.tolist(),
        'll': driver_ll,
        'fl': driver_fl,
        'dk': driver_dk
    }

@shared_task
def sim_execution_complete(results, sim_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        
        race_sim = models.RaceSim.objects.get(id=sim_id)
        drivers = race_sim.outcomes.filter(dk_position='D').order_by('starting_position', 'id')
        
        driver_ids = list(drivers.values_list('driver__driver_id', flat=True))

        dnf_list = [obj.get('dnf') for obj in results]
        fp_list = [obj.get('fp') for obj in results]
        fl_list = [obj.get('fl') for obj in results]
        ll_list = [obj.get('ll') for obj in results]
        dk_list = [obj.get('dk') for obj in results]

        df_dnf = pandas.DataFrame(dnf_list, columns=driver_ids)
        df_fp = pandas.DataFrame(fp_list, columns=driver_ids)
        df_fl = pandas.DataFrame(fl_list, columns=driver_ids)
        df_ll = pandas.DataFrame(ll_list, columns=driver_ids)
        df_dk = pandas.DataFrame(dk_list, columns=driver_ids)

        # Drivers & Captains
        for driver in drivers:
            driver.incident_outcomes = df_dnf[driver.driver.driver_id].tolist()
            driver.fp_outcomes = df_fp[driver.driver.driver_id].tolist()
            driver.avg_fp = numpy.average(driver.fp_outcomes)
            driver.fl_outcomes = df_fl[driver.driver.driver_id].tolist()
            driver.avg_fl = numpy.average(driver.fl_outcomes)
            driver.ll_outcomes = df_ll[driver.driver.driver_id].tolist()
            driver.avg_ll = numpy.average(driver.ll_outcomes)
            driver.dk_scores = df_dk[driver.driver.driver_id].tolist()
            driver.avg_dk_score = numpy.average(driver.dk_scores)
            driver.save()

            captain = race_sim.outcomes.get(driver=driver.driver, dk_position='CPT')
            captain.dk_scores = (df_dk[driver.driver.driver_id] * 1.5).tolist()
            captain.avg_dk_score = numpy.average(captain.dk_scores)
            captain.save()

        # Constructors
        for constructor in race_sim.outcomes.filter(dk_position='CNSTR'):
            teammates = drivers.filter(driver__team=constructor.constructor)

            constructor.dk_scores = [
                (teammates[0].dk_scores[index] + teammates[1].dk_scores[index] - models.SITE_SCORING.get('draftkings').get('defeated_teammate') + 
                (models.SITE_SCORING.get('draftkings').get('constructor_bonuses').get('both_classified') if int(teammates[0].incident_outcomes[index]) == 0 and int(teammates[1].incident_outcomes[index]) == 0 else 0) + 
                (models.SITE_SCORING.get('draftkings').get('constructor_bonuses').get('both_in_points') if teammates[0].fp_outcomes[index] <= 10 and teammates[1].fp_outcomes[index] <= 10 else 0) + 
                (models.SITE_SCORING.get('draftkings').get('constructor_bonuses').get('both_on_podium') if teammates[0].fp_outcomes[index] <= 3 and teammates[1].fp_outcomes[index] <= 3 else 0)) for index in range(0, race_sim.iterations)
            ]
            constructor.avg_dk_score = numpy.average(constructor.dk_scores)
            constructor.save()

        task.status = 'success'
        task.content = f'{race_sim} complete.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error simulating this race: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def find_driver_gto(sim_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        
        race_sim = models.RaceSim.objects.get(id=sim_id)
        scores = [d.dk_scores for d in race_sim.outcomes.all().order_by('-avg_dk_score')]

        jobs = []
        for i in range(0, race_sim.iterations):
            jobs.append(make_optimals_for_gto.si(
                [s[i] for s in scores],
                list(race_sim.outcomes.all().values_list('id', flat=True)),
                'draftkings'
            ))

        chord(
            group(jobs), 
            finalize_gto.s(
                race_sim.id,
                task_id
            )
        )()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error finding driver GTO exposures: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def make_optimals_for_gto(iterations_scores, driver_ids, site):
    optimizer = get_optimizer(Site.DRAFTKINGS, Sport.F1)

    drivers = models.RaceSimDriver.objects.filter(id__in=driver_ids)
    player_list = []

    for index, driver in enumerate(drivers.order_by('-avg_dk_score')):
        if driver.driver is None:
            first = driver.constructor.name
            last = ''
        else:
            if ' ' in driver.driver.full_name:
                first = driver.driver.full_name.split(' ')[0]
                last = driver.driver.full_name.split(' ')[-1]
            else:
                first = driver.driver.full_name
                last = ''

        team = driver.constructor.name if driver.driver is None else driver.driver.team.name
        fppg = iterations_scores[index]

        player = Player(
            driver.id,
            first,
            last,
            [driver.dk_position],
            team,
            driver.dk_salary,
            float(fppg),
        )

        player_list.append(player)

    optimizer.load_players(player_list)

    optimized_lineups = optimizer.optimize(
        n=1,
        randomness=False, 
    )
    
    for l in optimized_lineups:
        lineup = [p.id for p in l.players]

    return lineup

@shared_task
def finalize_gto(results, sim_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        
        race_sim = models.RaceSim.objects.get(id=sim_id)

        df_results = pandas.DataFrame(results)

        d_count_0 = df_results[0].value_counts()
        d_count_1 = df_results[1].value_counts()
        d_count_2 = df_results[2].value_counts()
        d_count_3 = df_results[3].value_counts()
        d_count_4 = df_results[4].value_counts()
        d_count_5 = df_results[5].value_counts()

        for driver in race_sim.outcomes.all():
            count = 0
            
            try:
                count += d_count_0.loc[driver.id]
            except KeyError:
                pass
            
            try:
                count += d_count_1.loc[driver.id]
            except KeyError:
                pass
            
            try:
                count += d_count_2.loc[driver.id]
            except KeyError:
                pass
            
            try:
                count += d_count_3.loc[driver.id]
            except KeyError:
                pass
            
            try:
                count += d_count_4.loc[driver.id]
            except KeyError:
                pass
            
            try:
                count += d_count_5.loc[driver.id]
            except KeyError:
                pass
                            
            driver.gto = count / race_sim.iterations
            driver.save()
        
        task.status = 'success'
        task.content = f'GTO for {race_sim} complete.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error finding driver GTO exposures: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def export_results(sim_id, result_path, result_url, task_id):
    task = None

    try:
        start = time.time()
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        race_sim = models.RaceSim.objects.get(id=sim_id)

        # Finishing position raw outcomes and finishing position distribution
        df_fp = pandas.DataFrame([d.fp_outcomes for d in race_sim.outcomes.filter(dk_position='D')], index=[d.driver.full_name for d in race_sim.outcomes.filter(dk_position='D')]).transpose()

        fp_list = []
        for fp in range(1, race_sim.outcomes.count()+1):
            fp_list.append(
                [df_fp[d.driver.full_name].value_counts()[fp] if fp in df_fp[d.driver.full_name].value_counts() else 0 for d in race_sim.outcomes.filter(dk_position='D').order_by('starting_position', 'id')]
            )
        df_fp_results = pandas.DataFrame(fp_list, index=range(0, race_sim.outcomes.count()), columns=list(race_sim.outcomes.filter(dk_position='D').order_by('starting_position', 'id').values_list('driver__full_name', flat=True)))

        # FL outcomes
        df_fl = pandas.DataFrame([d.fl_outcomes for d in race_sim.outcomes.filter(dk_position='D')], index=[d.driver.full_name for d in race_sim.outcomes.filter(dk_position='D')]).transpose()

        # LL outcomes
        df_ll = pandas.DataFrame([d.ll_outcomes for d in race_sim.outcomes.filter(dk_position='D')], index=[d.driver.full_name for d in race_sim.outcomes.filter(dk_position='D')]).transpose()

        # DK
        df_dk_raw = pandas.DataFrame([d.dk_scores for d in race_sim.outcomes.all()], index=[d.constructor.name if d.driver is None else d.driver.full_name for d in race_sim.outcomes.all()]).transpose()
        df_dk = pandas.DataFrame(data={
            'pos': [d.dk_position for d in race_sim.outcomes.all()],
            'sal': [d.dk_salary for d in race_sim.outcomes.all()],
            'start': [d.starting_position for d in race_sim.outcomes.all()],
            '50p': [numpy.percentile(d.dk_scores, float(50)) for d in race_sim.outcomes.all()],
            '60p': [numpy.percentile(d.dk_scores, float(60)) for d in race_sim.outcomes.all()],
            '70p': [numpy.percentile(d.dk_scores, float(70)) for d in race_sim.outcomes.all()],
            '80p': [numpy.percentile(d.dk_scores, float(80)) for d in race_sim.outcomes.all()],
            '90p': [numpy.percentile(d.dk_scores, float(90)) for d in race_sim.outcomes.all()],
            'gto': [d.gto for d in race_sim.outcomes.all()]
        }, index=[d.constructor.name if d.driver is None else d.driver.full_name for d in race_sim.outcomes.all()])
        

        with pandas.ExcelWriter(result_path) as writer:
            df_fp.to_excel(writer, sheet_name='Finishing Position Raw')
            df_fp_results.to_excel(writer, sheet_name='Finishing Position Distribution')
            df_fl.to_excel(writer, sheet_name='Fastest Laps Raw')
            df_ll.to_excel(writer, sheet_name='Laps Led Raw')
            df_dk.to_excel(writer, sheet_name='DK')
            df_dk_raw.to_excel(writer, sheet_name='DK Raw')

        print(f'export took {time.time() - start}s')
        task.status = 'download'
        task.content = result_url
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error exporting FP results: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# def get_score(row, **kwargs):
#     if 'site' not in kwargs:
#         raise Exception('Must provide a site.')
#     site = kwargs.get('site')

#     if 'sp' not in kwargs:
#         raise Exception('Must provide sp')
#     sp = kwargs.get('sp')

#     fp = row.get('fp')
#     pd = sp - fp
#     fl = row.get('fl')
#     ll = row.get('ll')

#     return float(models.SITE_SCORING.get(site).get('place_differential') * pd + models.SITE_SCORING.get(site).get('fastest_laps') * fl + models.SITE_SCORING.get(site).get('laps_led') * ll + models.SITE_SCORING.get(site).get('finishing_position').get(str(fp))) 


# @shared_task
# def process_build(build_id, task_id):
#     task = None

#     try:
#         try:
#             task = BackgroundTask.objects.get(id=task_id)
#         except BackgroundTask.DoesNotExist:
#             time.sleep(0.2)
#             task = BackgroundTask.objects.get(id=task_id)

#         build = models.SlateBuild.objects.get(id=build_id)

#         # create (or update) the projections
#         for slate_player in build.slate.players.all():
#             projection, created = models.BuildPlayerProjection.objects.get_or_create(
#                 slate_player=slate_player,
#                 build=build
#             )
#             try:
#                 sim_driver = build.sim.outcomes.get(driver=slate_player.driver)
#                 df_scores = pandas.DataFrame(data={
#                     'fp': sim_driver.fp_outcomes,
#                     'fl': sim_driver.fl_outcomes,
#                     'll': sim_driver.ll_outcomes
#                 })

#                 projection.starting_position = sim_driver.starting_position
#                 projection.sim_scores = df_scores.apply(get_score, axis=1, site=build.slate.site, sp=sim_driver.starting_position).to_list()
#                 projection.projection = numpy.percentile(projection.sim_scores, float(50))
#                 projection.ceiling = numpy.percentile(projection.sim_scores, float(90))
#                 projection.s75 = numpy.percentile(projection.sim_scores, float(75))
#                 projection.gto = sim_driver.gto
#                 projection.save()
#             except:
#                 pass

#         task.status = 'success'
#         task.content = f'{build} processed.'
#         task.save()

#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was an error processing your buyiuld: {e}'
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
#                     print(models.Driver.objects.filter(full_name=alias.get_alias('nascar')))
#                     slate_player.driver = models.Driver.objects.get(full_name=alias.get_alias('nascar'))
#                     slate_player.save()

#                     success_count += 1
#                 else:
#                     missing_players.append(player_name)

#         task.status = 'success'
#         task.content = '{} players have been successfully added to {}.'.format(success_count, str(slate)) if len(missing_players) == 0 else '{} players have been successfully added to {}. {} players could not be identified.'.format(success_count, str(slate), len(missing_players))
#         task.link = '/admin/nascar/missingalias/' if len(missing_players) > 0 else None
#         task.save()
#     except Exception as e:
#         if task is not None:
#             task.status = 'error'
#             task.content = f'There was a problem processing slate players: {e}'
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
#         if build.configuration.optimize_by_percentile == 0:
#             lineups = optimize.generateRandomLineups(
#                 build.projections.filter(in_play=True),
#                 build.total_lineups * build.configuration.lineup_multiplier,
#                 6,
#                 50000
#             )

#             for lineup in lineups:
#                 if build.slate.site == 'draftkings':
#                     lineup = models.SlateBuildLineup.objects.create(
#                         build=build,
#                         player_1=lineup[0],
#                         player_2=lineup[1],
#                         player_3=lineup[2],
#                         player_4=lineup[3],
#                         player_5=lineup[4],
#                         player_6=lineup[5],
#                         total_salary=sum([lp.salary for lp in lineup])
#                     )

#                     lineup.save()
#                     lineup.simulate()
#                 else:
#                     raise Exception(f'{build.slate.site} is not available for building yet.')

#                 # print(f'dup = {lineup.duplicated}; {lineup.duplicated > build.configuration.duplicate_threshold}')
#                 if lineup.duplicated > build.configuration.duplicate_threshold:
#                     # print('delete this lineup')
#                     lineup.delete()
#         else:
#             lineups = optimize.optimize(build.slate.site, build.projections.filter(in_play=True), build.groups.filter(active=True), build.configuration, build.total_lineups)

#             for lineup in lineups:
#                 if build.slate.site == 'draftkings':
#                     lineup = models.SlateBuildLineup.objects.create(
#                         build=build,
#                         player_1=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[0].id, slate_player__slate=build.slate),
#                         player_2=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[1].id, slate_player__slate=build.slate),
#                         player_3=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[2].id, slate_player__slate=build.slate),
#                         player_4=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[3].id, slate_player__slate=build.slate),
#                         player_5=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[4].id, slate_player__slate=build.slate),
#                         player_6=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[5].id, slate_player__slate=build.slate),
#                         total_salary=lineup.salary_costs
#                     )

#                     lineup.save()
#                     lineup.simulate()
#                 else:
#                     raise Exception(f'{build.slate.site} is not available for building yet.')

#                 if lineup.duplicated > build.configuration.duplicate_threshold:
#                     lineup.delete()
        
#         task.status = 'success'
#         task.content = f'{len(lineups)} lineups created.'
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

#         ordered_lineups = build.lineups.all().order_by('-sort_proj')
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


# # @shared_task
# # def calculate_exposures(build_id, task_id):
# #     task = None

# #     try:
# #         try:
# #             task = BackgroundTask.objects.get(id=task_id)
# #         except BackgroundTask.DoesNotExist:
# #             time.sleep(0.2)
# #             task = BackgroundTask.objects.get(id=task_id)

# #         # Task implementation goes here
# #         build = models.SlateBuild.objects.get(id=build_id)
# #         players = models.SlatePlayerProjection.objects.filter(
# #             slate_player__slate=build.slate
# #         )

# #         for player in players:
# #             exposure, _ = models.SlateBuildPlayerExposure.objects.get_or_create(
# #                 build=build,
# #                 player=player
# #             )
# #             exposure.exposure = build.lineups.filter(
# #                 Q(
# #                     Q(player_1=player) | 
# #                     Q(player_2=player) | 
# #                     Q(player_3=player) | 
# #                     Q(player_4=player) | 
# #                     Q(player_5=player) | 
# #                     Q(player_6=player)
# #                 )
# #             ).count() / build.lineups.all().count()
# #             exposure.save()
        
# #         task.status = 'success'
# #         task.content = 'Exposures calculated.'
# #         task.save()
# #     except Exception as e:
# #         if task is not None:
# #             task.status = 'error'
# #             task.content = f'There was a problem calculating exposures: {e}'
# #             task.save()

# #         logger.error("Unexpected error: " + str(sys.exc_info()[0]))
# #         logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


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
#             build_writer.writerow(['D', 'D', 'D', 'D', 'D', 'D'])

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

