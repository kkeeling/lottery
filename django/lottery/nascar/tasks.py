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
                race.stage_1_laps = r.get('stage_1_laps')
                race.stage_2_laps = r.get('stage_2_laps')
                race.stage_3_laps = r.get('stage_3_laps')
                race.stage_4_laps = r.get('stage_4_laps') if r.get('stage_4_laps') is not None else 0
                race.save()
        
        race_result_tasks = group([
            update_race_results.si(race.race_id, race_year) for race in models.Race.objects.filter(race_season=race_year)
        ])
        lap_data_tasks = group([
            update_lap_data_for_race.si(race.race_id, race_year) for race in models.Race.objects.filter(race_season=race_year)
        ])
        chain(race_result_tasks, lap_data_tasks)()

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
                driver = models.Driver.objects.get(nascar_driver_id=result.get('driver_id'))
                driver.manufacturer = result.get('car_make')
                driver.team = result.get('team_name')
                driver.save()

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
            # check for caution segment
            caution_segments = models.RaceCautionSegment.objects.filter(
                race=race,
                start_lap__gte=l.get('Lap'),
                end_lap__lte=l.get('Lap')
            )
            
            if caution_segments.count() < 0:
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
            task.content = f'There was an error exporting track data: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


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
        prior_races = models.Race.objects.filter(
            series=race_sim.race.series,
            race_date__lt=race_sim.race.race_date
        ).exclude(
            track__track_type=3
        )

        drivers = race_sim.get_drivers().all().annotate(
            nascar_driver_id=F('driver__nascar_driver_id'),
            name=F('driver__full_name'),
            car=F('driver__badge'),
            team=F('driver__team'),
            manufacturer=F('driver__manufacturer'),
            num_races=Count('driver__results__race', filter=Q(driver__results__race__in=prior_races), distinct=True),
            num_finish=Count('driver__results__race', filter=Q(driver__results__race__in=prior_races, driver__results__finishing_status='Running'), distinct=True),
            num_crashes=Count('driver__results__race', filter=Q(Q(driver__results__race__in=prior_races, driver__results__finishing_status='Accident')|Q(driver__results__race__in=prior_races, driver__results__finishing_status='DVP')), distinct=True),
            num_mech=F('num_races') - F('num_finish') - F('num_crashes'),
            num_penalty=Count('driver__infractions__race', filter=Q(driver__infractions__race__in=prior_races, driver__infractions__lap__gt=0), distinct=True)
        ).order_by('starting_position')

        df_drivers = pandas.DataFrame.from_records(drivers.values(
            'nascar_driver_id',
            'name',
            'car',
            'team',
            'manufacturer',
            'starting_position',
            'num_races',
            'num_finish',
            'num_crashes',
            'num_mech',
            'num_penalty',
        ))
        df_drivers['crash_rate'] = df_drivers['num_crashes']/df_drivers['num_races']
        df_drivers['mech_rate'] = df_drivers['num_mech']/df_drivers['num_races']
        df_drivers['penalty_rate'] = df_drivers['num_penalty']/df_drivers['num_races']
        df_drivers['strategy_factor'] = ''
        df_drivers['speed_min'] = ''
        df_drivers['speed_max'] = ''
        df_drivers['best_possible_speed'] = ''
        df_drivers['worst_possible_speed'] = ''

        df_race = pandas.DataFrame.from_records(models.RaceSim.objects.filter(id=sim_id).values(
            'laps_per_caution',
            'early_stage_caution_mean',
            'early_stage_caution_prob_debris',
            'early_stage_caution_prob_accident_small',
            'early_stage_caution_prob_accident_medium',
            'early_stage_caution_prob_accident_major',
            'final_stage_caution_mean',
            'final_stage_caution_prob_debris',
            'final_stage_caution_prob_accident_small',
            'final_stage_caution_prob_accident_medium',
            'final_stage_caution_prob_accident_major',
            'track_variance',
            'track_variance_late_restart',
        ))

        df_damage = pandas.DataFrame(data={
            'name': ['Small Accident', 'Medium Accident', 'Major Accident'],
            'min_cars': [1, 3, 7],
            'max_cars': [2, 6, 10],
            'prob_no_damage': [0, 0, 0.05],
            'prob_minor_damage': [.2, .05, .1],
            'prob_medium_damage': [.4, .25, .15],
            'prob_dnf': [.4, .7, .7]
        })

        df_penalty = pandas.DataFrame(data={
            'stage': [1, 1, 2, 2, 3, 3],
            'is_green': [True, False, True, False, True, False],
            'floor_impact': [8, 0, 9, 2, 10, 4],
            'ceiling_impact': [8, 0, 9, 2, 10, 4]
        })

        df_fl = pandas.DataFrame(data={
            'pct_min': [0 for _ in range (0, 15)],
            'pct_max': [0 for _ in range (0, 15)],
            'cum_min': [0 for _ in range (0, 15)],
            'cum_max': [0 for _ in range (0, 15)],
            'speed_rank_min': [i+1 for i in range (0, 15)],
            'speed_rank_max': [i+1 for i in range (0, 15)]
        })

        df_ll = pandas.DataFrame(data={
            'pct_min': [0 for _ in range (0, 15)],
            'pct_max': [0 for _ in range (0, 15)],
            'cum_min': [0 for _ in range (0, 15)],
            'cum_max': [0 for _ in range (0, 15)],
            'fl_rank_min': [i+1 for i in range (0, 15)],
            'fl_rank_max': [i+1 for i in range (0, 15)]
        })

        df_drivers = df_drivers.drop(columns=['num_finish', 'num_crashes', 'num_mech', 'num_penalty'])
        # df_drivers.to_csv(result_path)

        with pandas.ExcelWriter(result_path) as writer:
            df_race.to_excel(writer, sheet_name='race')
            df_damage.to_excel(writer, sheet_name='damage')
            df_penalty.to_excel(writer, sheet_name='penalty')
            df_fl.to_excel(writer, sheet_name='fl')
            df_ll.to_excel(writer, sheet_name='ll')
            df_drivers.to_excel(writer, sheet_name='drivers')

        task.status = 'download'
        task.content = result_url
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error exporting track data: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


# Sims

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
        fd_salaries = None

        if bool(race_sim.dk_salaries):
            dk_salaries = pandas.read_csv(race_sim.dk_salaries.path, usecols= ['Name','Salary'], index_col='Name')
        if bool(race_sim.fd_salaries):
            fd_salaries = pandas.read_csv(race_sim.fd_salaries.path, header=None, sep='\n')

        df_race = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='race')
        df_damage = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='damage')
        df_penalty = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='penalty')
        df_fl = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='fl')
        df_ll = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='ll')
        df_drivers = pandas.read_excel(race_sim.input_file.path, index_col=0, sheet_name='drivers')

        race_sim.laps_per_caution = df_race.loc[0, 'laps_per_caution']
        race_sim.early_stage_caution_mean = df_race.loc[0, 'early_stage_caution_mean']
        race_sim.early_stage_caution_prob_debris = df_race.loc[0, 'early_stage_caution_prob_debris']
        race_sim.early_stage_caution_prob_accident_small = df_race.loc[0, 'early_stage_caution_prob_accident_small']
        race_sim.early_stage_caution_prob_accident_medium = df_race.loc[0, 'early_stage_caution_prob_accident_medium']
        race_sim.early_stage_caution_prob_accident_major = df_race.loc[0, 'early_stage_caution_prob_accident_major']
        race_sim.final_stage_caution_mean = df_race.loc[0, 'final_stage_caution_mean']
        race_sim.final_stage_caution_prob_debris = df_race.loc[0, 'final_stage_caution_prob_debris']
        race_sim.final_stage_caution_prob_accident_small = df_race.loc[0, 'final_stage_caution_prob_accident_small']
        race_sim.final_stage_caution_prob_accident_medium = df_race.loc[0, 'final_stage_caution_prob_accident_medium']
        race_sim.final_stage_caution_prob_accident_major = df_race.loc[0, 'final_stage_caution_prob_accident_major']
        race_sim.track_variance = df_race.loc[0, 'track_variance']
        race_sim.track_variance_late_restart = df_race.loc[0, 'track_variance_late_restart']
        race_sim.save()

        race_sim.damage_profiles.all().delete()
        for index in range(0, len(df_damage.index)):
            models.RaceSimDamageProfile.objects.create(
                sim=race_sim,
                name=df_damage.at[index, 'name'],
                min_cars_involved=df_damage.at[index, 'min_cars'],
                max_cars_involved=df_damage.at[index, 'max_cars'],
                prob_no_damage=df_damage.at[index, 'prob_no_damage'],
                prob_minor_damage=df_damage.at[index, 'prob_minor_damage'],
                prob_medium_damage=df_damage.at[index, 'prob_medium_damage'],
                prob_dnf=df_damage.at[index, 'prob_dnf']
            )

        race_sim.penalty_profiles.all().delete()
        for index in range(0, len(df_penalty.index)):
            models.RaceSimPenaltyProfile.objects.create(
                sim=race_sim,
                stage=df_penalty.at[index, 'stage'],
                is_green=df_penalty.at[index, 'is_green'],
                floor_impact=df_penalty.at[index, 'floor_impact'],
                ceiling_impact=df_penalty.at[index, 'ceiling_impact']
            )

        race_sim.fl_profiles.all().delete()
        for index in range(0, len(df_fl.index)):
            models.RaceSimFastestLapsProfile.objects.create(
                sim=race_sim,
                pct_fastest_laps_min=df_fl.at[index, 'pct_min'],
                pct_fastest_laps_max=df_fl.at[index, 'pct_max'],
                cum_fastest_laps_min=df_fl.at[index, 'cum_min'],
                cum_fastest_laps_max=df_fl.at[index, 'cum_max'],
                eligible_speed_min=df_fl.at[index, 'speed_rank_min'],
                eligible_speed_max=df_fl.at[index, 'speed_rank_max']
            )

        race_sim.ll_profiles.all().delete()
        for index in range(0, len(df_ll.index)):
            models.RaceSimLapsLedProfile.objects.create(
                sim=race_sim,
                pct_laps_led_min=df_ll.at[index, 'pct_min'],
                pct_laps_led_max=df_ll.at[index, 'pct_max'],
                cum_laps_led_min=df_ll.at[index, 'cum_min'],
                cum_laps_led_max=df_ll.at[index, 'cum_max'],
                rank_order=df_ll.at[index, 'rank_order']
            )

        race_sim.outcomes.all().delete()
        for index in range(0, len(df_drivers.index)):
            driver = models.Driver.objects.get(nascar_driver_id=df_drivers.at[index, 'nascar_driver_id'])
            alias = models.Alias.find_alias(driver.full_name, 'nascar')

            dk_salary = dk_salaries.loc[[alias.dk_name]]['Salary'] if dk_salaries is not None else 0.0
            fd_salary = fd_salaries.loc[[alias.fd_name]] if fd_salaries is not None else 0.0

            models.RaceSimDriver.objects.create(
                sim=race_sim,
                driver=driver,
                starting_position=df_drivers.at[index, 'starting_position'],
                dk_salary=dk_salary,
                fd_salary=fd_salary,
                speed_min=df_drivers.at[index, 'speed_min'],
                speed_max=df_drivers.at[index, 'speed_max'],
                best_possible_speed=df_drivers.at[index, 'best_possible_speed'],
                worst_possible_speed=0,
                crash_rate=df_drivers.at[index, 'crash_rate'],
                mech_rate=df_drivers.at[index, 'mech_rate'],
                infraction_rate=df_drivers.at[index, 'penalty_rate'],
                strategy_factor=df_drivers.at[index, 'strategy_factor']
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


def get_speed_min(driver, current_speed_rank):
    speed_delta = 10
    speed_min = max(current_speed_rank - 5, driver.best_possible_speed)


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


@shared_task
def execute_sim_iteration(sim_id):
    race_sim = models.RaceSim.objects.get(id=sim_id)
    drivers = race_sim.outcomes.all().order_by('starting_position', 'id')
    crash_rate_sum = drivers.aggregate(crash_rate_sum=Sum('crash_rate')).get('crash_rate_sum')
    
    if race_sim.race.series == 1:
        pit_penalty_mean = 1.09375
    elif race_sim.race.series == 2:
        pit_penalty_mean = 1.366071429
    else:
        pit_penalty_mean = 1.421052632
    
    # for n in range(1, race_sim.iterations+1):
    race_drivers = list(drivers.values_list('driver__nascar_driver_id', flat=True))  # tracks drivers still in race
    driver_ids = list(drivers.values_list('driver__nascar_driver_id', flat=True))
    driver_names = list(drivers.values_list('driver__full_name', flat=True))
    driver_starting_positions = list(drivers.values_list('starting_position', flat=True))
    driver_strategy = list(drivers.values_list('strategy_factor', flat=True))

    driver_dnfs = [None for driver in drivers]
    driver_sp_mins = list(drivers.values_list('speed_min', flat=True))
    driver_sp_maxes = list(drivers.values_list('speed_max', flat=True))
    driver_bp_sp_mins = list(drivers.values_list('best_possible_speed', flat=True))
    # driver_bp_sp_maxes = list(drivers.values_list('worst_possible_speed', flat=True))

    driver_s1_penalties = [None for driver in drivers]
    # driver_s1_ranks = [None for driver in drivers]
    # driver_s1_mins = [None for driver in drivers]
    # driver_s1_maxes = [None for driver in drivers]
    # driver_s1_fl = [0 for driver in drivers]
    
    driver_s2_penalties = [None for driver in drivers]
    # driver_s2_ranks = [None for driver in drivers]
    # driver_s2_mins = [None for driver in drivers]
    # driver_s2_maxes = [None for driver in drivers]
    # driver_s2_fl = [0 for driver in drivers]
    
    driver_s3_penalties = [None for driver in drivers]
    # driver_s3_ranks = [None for driver in drivers]
    # driver_s3_mins = [None for driver in drivers]
    # driver_s3_maxes = [None for driver in drivers]
    # driver_s3_fl = [0 for driver in drivers]

    if race_sim.race.num_stages() > 3:
        driver_s4_penalties = [None for driver in drivers]
        # driver_s4_ranks = [None for driver in drivers]
        # driver_s4_fl = [0 for driver in drivers]

    driver_fl = [0 for driver in drivers]
    driver_ll = [0 for driver in drivers]
    # driver_damage = [None for driver in drivers]
    # driver_penalty = [None for driver in drivers]

    minor_damage_drivers = []
    medium_damage_drivers = []
    dnf_drivers = []

    stage_1_green_penalty_drivers = []
    stage_1_yellow_penalty_drivers = []
    stage_2_green_penalty_drivers = []
    stage_2_yellow_penalty_drivers = []
    stage_3_green_penalty_drivers = []
    stage_3_yellow_penalty_drivers = []
    stage_4_green_penalty_drivers = []
    stage_4_yellow_penalty_drivers = []

    late_caution = False
    total_cautions = 0

    for stage in range(1, race_sim.race.num_stages() + 1):
        # num_laps = race_sim.race.get_laps_for_stage(stage)
        # print(f'Stage {stage}: {num_laps} laps')

        # Find # of cautions & caution type thresholds

        if stage < race_sim.race.num_stages():
            num_cautions = scipy.stats.poisson.rvs(race_sim.early_stage_caution_mean)

            debris_caution_cutoff = race_sim.early_stage_caution_prob_debris
            accident_small_caution_cutoff = race_sim.early_stage_caution_prob_accident_small
            accident_medium_caution_cutoff = race_sim.early_stage_caution_prob_accident_medium
            # accident_major_caution_cutoff = race_sim.early_stage_caution_prob_accident_major
        else:
            num_cautions = scipy.stats.poisson.rvs(race_sim.final_stage_caution_mean)

            debris_caution_cutoff = race_sim.final_stage_caution_prob_debris
            accident_small_caution_cutoff = race_sim.final_stage_caution_prob_accident_small
            accident_medium_caution_cutoff = race_sim.final_stage_caution_prob_accident_medium
            # accident_major_caution_cutoff = race_sim.final_stage_caution_prob_accident_major

        total_cautions += num_cautions
        # print(f'  There are {num_cautions} cautions.')
        # For each caution, assign damage

        max_drivers = race_sim.damage_profiles.all().order_by('-max_cars_involved').first().max_cars_involved
        for _ in range(0, num_cautions):
            c_val = random()
            if c_val <= debris_caution_cutoff:
                min_cars = -1
                max_cars = 0
            elif c_val <= debris_caution_cutoff + accident_small_caution_cutoff:
                min_cars = min(1, len(race_drivers))
                max_cars = min(2, len(race_drivers))
            elif c_val <= debris_caution_cutoff + accident_small_caution_cutoff + accident_medium_caution_cutoff:
                min_cars = min(3, len(race_drivers))
                max_cars = min(6, len(race_drivers))
            else:
                min_cars = min(7, len(race_drivers))
                max_cars = min(max_drivers, len(race_drivers))

            num_cars = max(math.ceil(uniform(min_cars - 1, max_cars)), 0)
            # print(f'Caution {caution + 1}: {num_cars} involved.')

            # assign damage
            involved_cars = []
            for _ in range(0, num_cars):
                # create probabilty pool for wreck involvement based on remaining race drivers
                crash_pool = [] 
                for driver in drivers.filter(driver__nascar_driver_id__in=race_drivers):
                    n = round((driver.crash_rate / crash_rate_sum) * 100)
                    for _ in range(0, n):
                        crash_pool.append(driver)
                involved_car_index = round(uniform(0, len(crash_pool)-1))
                involved_car = crash_pool[involved_car_index]

                while involved_car.id in involved_cars:
                    involved_car_index = round(uniform(0, len(crash_pool)-1))
                    involved_car = crash_pool[involved_car_index]

                involved_cars.append(involved_car.id)

                # assign damage using no damage (0), minor damage (1), damage (2), and DNF (3) percentages based on the caution type (small, medium, major)
                damage_profile = race_sim.get_damage_profile(num_cars)
                
                damage_options = [0 for _ in range(0, int(damage_profile.prob_no_damage * 100))]
                damage_options += [1 for _ in range(0, int(damage_profile.prob_minor_damage * 100))]
                damage_options += [2 for _ in range(0, int(damage_profile.prob_medium_damage * 100))]
                damage_options += [3 for _ in range(0, int(damage_profile.prob_dnf * 100))]

                damage_index = round(uniform(0, len(damage_options)-1))
                damage_value = damage_options[damage_index]
                
                # driver_index = driver_ids.index(involved_car.driver.nascar_driver_id)

                if damage_value == 0:
                    # print(f'{involved_car} [{involved_car.id}] takes no damage')
                    pass
                elif damage_value == 1:
                    # print(f'{involved_car} [{involved_car.id}] takes minor damage')
                    minor_damage_drivers.append(involved_car)
                    # driver_damage[driver_index] = f'{stage}d'
                elif damage_value == 2:
                    # print(f'{involved_car} [{involved_car.id}] takes medium damage')
                    medium_damage_drivers.append(involved_car)
                    # driver_damage[driver_index] = f'{stage}D'
                else:
                    # print(f'{involved_car} [{involved_car.id}] is out of the race')
                    race_drivers = list(filter((involved_car.id).__ne__, race_drivers))
                    dnf_drivers.append(involved_car)
                    # driver_damage[driver_index] = f'{stage} DNF'

        # assign penalties based on number of cautions
        if num_cautions == 0:
            num_penalties = scipy.stats.poisson.rvs(pit_penalty_mean)
            # print(f'There are {num_penalties} penalties')

            # all penalties are green flag
            for _ in range(0, num_penalties):
                penalized_driver = race_drivers[round(uniform(0, len(race_drivers)-1))]
                # print(f'{drivers.get(driver__nascar_driver_id=penalized_driver)} had a green flag penalty')

                if stage == 1:
                    stage_1_green_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
                elif stage == 2:
                    stage_2_green_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
                elif stage == 3:
                    stage_3_green_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
                else:
                    stage_4_green_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
        else:
            # generate penalties for each caution
            for _ in range(0, num_cautions):
                num_penalties = scipy.stats.poisson.rvs(pit_penalty_mean)
                # print(f'There are {num_penalties} penalties')

                # all penalties are yellow flag
                for _ in range(0, num_penalties):
                    penalized_driver = race_drivers[round(uniform(0, len(race_drivers)-1))]
                    # print(f'{drivers.get(driver__nascar_driver_id=penalized_driver)} had a yellow flag penalty')

                    if stage == 1:
                        stage_1_yellow_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
                    elif stage == 2:
                        stage_2_yellow_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
                    elif stage == 3:
                        stage_3_yellow_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
                    else:
                        stage_4_yellow_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))

        if stage < race_sim.race.num_stages():
            # add stage caution penalties
            num_penalties = scipy.stats.poisson.rvs(pit_penalty_mean)
            # print(f'There are {num_penalties} end of stage penalties')
            
            for _ in range(0, num_penalties):
                penalized_driver = race_drivers[round(uniform(0, len(race_drivers)-1))]
                # print(f'{drivers.get(driver__nascar_driver_id=penalized_driver)} had a yellow flag penalty')

                if stage == 1:
                    stage_1_yellow_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
                elif stage == 2:
                    stage_2_yellow_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
                elif stage == 3:
                    stage_3_yellow_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))
                else:
                    stage_4_yellow_penalty_drivers.append(drivers.get(driver__nascar_driver_id=penalized_driver))

        # Update dnfs, penalties after each stage
        # speed = []
        for index, driver in enumerate(drivers):
            if driver in dnf_drivers:
                if driver_dnfs[index] is None:  # make sure driver didn't dnf in previous stage
                    # Did driver DNF?
                    driver_dnfs[index] = stage
                # speed.append(9999*(race_sim.race.num_stages()-driver_dnfs[index]+1)+index)  # DNFs always fall to the bottom, but keep them in order stage to stage
            else:
                # Assign speed
                if stage == 1:
                    # Did driver have a penalty?
                    if driver in stage_1_green_penalty_drivers:
                        driver_s1_penalties[index] = 'G'
                        # driver_penalty[index] = '1G'
                    elif driver in stage_1_yellow_penalty_drivers:
                        driver_s1_penalties[index] = 'Y'
                        # driver_penalty[index] = '1Y'

                    # flr = driver.speed_min
                    # ceil = driver.speed_max
                elif stage == 2:
                    # Did driver have a penalty?
                    if driver in stage_2_green_penalty_drivers:
                        driver_s2_penalties[index] = 'G'
                        # driver_penalty[index] = '2G'
                    elif driver in stage_2_yellow_penalty_drivers:
                        driver_s2_penalties[index] = 'Y'
                        # driver_penalty[index] = '2Y'

                    # flr = driver_s1_mins[index]
                    # ceil = driver_s1_maxes[index]
                elif stage == 3:
                    # Did driver have a penalty?
                    if driver in stage_3_green_penalty_drivers:
                        driver_s3_penalties[index] = 'G'
                        # driver_penalty[index] = '3G'
                    elif driver in stage_3_yellow_penalty_drivers:
                        driver_s3_penalties[index] = 'Y'
                        # driver_penalty[index] = '3Y'

                    # flr = driver_s2_mins[index]
                    # ceil = driver_s2_maxes[index]
                elif stage == 4:
            # Did driver have a penalty?
                    if driver in stage_4_green_penalty_drivers:
                        driver_s4_penalties[index] = 'G'
                        # driver_penalty[index] = '4G'
                    elif driver in stage_4_yellow_penalty_drivers:
                        driver_s4_penalties[index] = 'Y'
                        # driver_penalty[index] = '4Y'

                    # flr = driver_s3_mins[index]
                    # ceil = driver_s3_maxes[index]

                # Did driver take damage
                # if driver in medium_damage_drivers:
                #     flr = 40
                #     ceil = 20
                # elif driver in minor_damage_drivers:
                #     flr += 10

                # mu = numpy.average([flr, ceil])
                # stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
                # d_sr = numpy.random.normal(mu, stdev, 1)[0] + random()
                # speed.append(d_sr)

        # Update speed rank and assign FL/LL after each stage
        # if stage == 1:
        #     print('stage 1')
        #     # rank speed
        #     driver_s1_ranks = scipy.stats.rankdata(speed, method='ordinal')
        #     driver_s1_mins = [max(driver_s1_ranks[i] - 5, d.best_possible_speed) for i, d in enumerate(drivers)]
        #     driver_s1_maxes = [driver_s1_ranks[i] + 5 for i, d in enumerate(drivers)]

        #     stage_laps = race_sim.race.stage_1_laps
        #     caution_laps = int(num_cautions * race_sim.laps_per_caution)
        #     fl_laps = stage_laps - caution_laps
        #     fl_vals = [max(int(randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100), 1)/100 * fl_laps), 1) for p in race_sim.fl_profiles.all().order_by('-pct_laps_led_min')]

        #     fl_laps_remaining = fl_laps
        #     fl_laps_assigned = []
        #     for index, flp in enumerate(race_sim.fl_profiles.all().order_by('-pct_laps_led_min')):
        #         # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        #         fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        #         while fl_index in fl_laps_assigned:  # only assign FL to drivers that haven't gotten any yet this stage
        #             fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)

        #         sp_index = int(numpy.where(driver_s1_ranks == fl_index)[0][0])
        #         # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_vals[index]}')
        #         driver_s1_fl[sp_index] = fl_vals[index]
        #         fl_laps_assigned.append(fl_index)

        #         fl_laps_remaining -= fl_vals[index]
                
        #     # there may be remaining FL, assign using lowest profile
        #     flp = race_sim.fl_profiles.all().order_by('-pct_laps_led_min').last()
        #     while fl_laps_remaining > 0:
        #         # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        #         fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        #         sp_index = int(numpy.where(driver_s1_ranks == fl_index)[0][0])
        #         fl_val = max(int(randrange(int(flp.pct_laps_led_min*100), int(flp.pct_laps_led_max*100), 1)/100 * fl_laps), 1)
        #         # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_val}')
        #         driver_s1_fl[sp_index] += fl_val
        #         fl_laps_assigned.append(fl_index)

        #         fl_laps_remaining -= fl_val
        # elif stage == 2:
        #     # rank speed
        #     driver_s2_ranks = scipy.stats.rankdata(speed, method='ordinal')
        #     driver_s2_mins = [max(driver_s2_ranks[i] - 5, d.best_possible_speed) for i, d in enumerate(drivers)]
        #     driver_s2_maxes = [driver_s2_ranks[i] + 5 for i, d in enumerate(drivers)]

        #     stage_laps = race_sim.race.stage_2_laps
        #     caution_laps = int(num_cautions * race_sim.laps_per_caution)
        #     fl_laps = stage_laps - caution_laps
        #     fl_vals = [max(int(randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100), 1)/100 * fl_laps), 1) for p in race_sim.fl_profiles.all().order_by('-pct_laps_led_min')]

        #     fl_laps_remaining = fl_laps
        #     fl_laps_assigned = []
        #     for index, flp in enumerate(race_sim.fl_profiles.all().order_by('-pct_laps_led_min')):
        #         # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        #         fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        #         while fl_index in fl_laps_assigned:  # only assign FL to drivers that haven't gotten any yet this stage
        #             fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)

        #         sp_index = int(numpy.where(driver_s2_ranks == fl_index)[0][0])
        #         # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_vals[index]}')
        #         driver_s2_fl[sp_index] = fl_vals[index]
        #         fl_laps_assigned.append(fl_index)

        #         fl_laps_remaining -= fl_vals[index]
                
        #     # there may be remaining FL, assign using lowest profile
        #     flp = race_sim.fl_profiles.all().order_by('-pct_laps_led_min').last()
        #     while fl_laps_remaining > 0:
        #         # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        #         fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        #         sp_index = int(numpy.where(driver_s2_ranks == fl_index)[0][0])
        #         fl_val = max(int(randrange(int(flp.pct_laps_led_min*100), int(flp.pct_laps_led_max*100), 1)/100 * fl_laps), 1)
        #         # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_val}')
        #         driver_s2_fl[sp_index] += fl_val
        #         fl_laps_assigned.append(fl_index)

        #         fl_laps_remaining -= fl_val
        # elif stage == 3:
        #     # rank speed
        #     driver_s3_ranks = scipy.stats.rankdata(speed, method='ordinal')
        #     driver_s3_mins = [max(driver_s3_ranks[i] - 5, d.best_possible_speed) for i, d in enumerate(drivers)]
        #     driver_s3_maxes = [driver_s3_ranks[i] + 5 for i, d in enumerate(drivers)]

        #     stage_laps = race_sim.race.stage_3_laps
        #     caution_laps = int(num_cautions * race_sim.laps_per_caution)
        #     fl_laps = stage_laps - caution_laps
        #     fl_vals = [max(int(randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100), 1)/100 * fl_laps), 1) for p in race_sim.fl_profiles.all().order_by('-pct_laps_led_min')]

        #     fl_laps_remaining = fl_laps
        #     fl_laps_assigned = []
        #     for index, flp in enumerate(race_sim.fl_profiles.all().order_by('-pct_laps_led_min')):
        #         # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        #         fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        #         while fl_index in fl_laps_assigned:  # only assign FL to drivers that haven't gotten any yet this stage
        #             fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)

        #         sp_index = int(numpy.where(driver_s3_ranks == fl_index)[0][0])
        #         # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_vals[index]}')
        #         driver_s3_fl[sp_index] = fl_vals[index]
        #         fl_laps_assigned.append(fl_index)

        #         fl_laps_remaining -= fl_vals[index]
                
        #     # there may be remaining FL, assign using lowest profile
        #     flp = race_sim.fl_profiles.all().order_by('-pct_laps_led_min').last()
        #     while fl_laps_remaining > 0:
        #         # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        #         fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        #         sp_index = int(numpy.where(driver_s3_ranks == fl_index)[0][0])
        #         fl_val = max(int(randrange(int(flp.pct_laps_led_min*100), int(flp.pct_laps_led_max*100), 1)/100 * fl_laps), 1)
        #         # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_val}')
        #         driver_s3_fl[sp_index] += fl_val
        #         fl_laps_assigned.append(fl_index)

        #         fl_laps_remaining -= fl_val
        # elif stage == 4:
        #     # rank speed
        #     driver_s4_ranks = scipy.stats.rankdata(speed, method='ordinal')
        #     driver_s4_mins = [max(driver_s4_ranks[i] - 5, d.best_possible_speed) for i, d in enumerate(drivers)]
        #     driver_s4_maxes = [driver_s4_ranks[i] + 5 for i, d in enumerate(drivers)]

        #     stage_laps = race_sim.race.stage_4_laps
        #     caution_laps = int(num_cautions * race_sim.laps_per_caution)
        #     fl_laps = stage_laps - caution_laps
        #     fl_vals = [max(int(randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100), 1)/100 * fl_laps), 1) for p in race_sim.fl_profiles.all().order_by('-pct_laps_led_min')]

        #     fl_laps_remaining = fl_laps
        #     fl_laps_assigned = []
        #     for index, flp in enumerate(race_sim.fl_profiles.all().order_by('-pct_laps_led_min')):
        #         # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        #         fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        #         while fl_index in fl_laps_assigned:  # only assign FL to drivers that haven't gotten any yet this stage
        #             fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)

        #         sp_index = int(numpy.where(driver_s4_ranks == fl_index)[0][0])
        #         # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_vals[index]}')
        #         driver_s4_fl[sp_index] = fl_vals[index]
        #         fl_laps_assigned.append(fl_index)

        #         fl_laps_remaining -= fl_vals[index]
                
        #     # there may be remaining FL, assign using lowest profile
        #     flp = race_sim.fl_profiles.all().order_by('-pct_laps_led_min').last()
        #     while fl_laps_remaining > 0:
        #         # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        #         fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        #         sp_index = int(numpy.where(driver_s4_ranks == fl_index)[0][0])
        #         fl_val = max(int(randrange(int(flp.pct_laps_led_min*100), int(flp.pct_laps_led_max*100), 1)/100 * fl_laps), 1)
        #         # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_val}')
        #         driver_s4_fl[sp_index] += fl_val
        #         fl_laps_assigned.append(fl_index)

        #         fl_laps_remaining -= fl_val

        # Was there a late caution
        if stage == race_sim.race.num_stages():
            val = random()
            if num_cautions == 1:
                late_caution = val < 0.50
            elif num_cautions == 2:
                late_caution = val < 0.75
            elif num_cautions >= 3:
                late_caution = True

    # Assign final speed
    speed = []
    for index, driver in enumerate(drivers):
        if driver in dnf_drivers:
            speed.append(9999*(race_sim.race.num_stages()-driver_dnfs[index]+1)+index)  # DNFs always fall to the bottom, but keep them in order stage to stage
        else:
            flr = driver.speed_min
            ceil = driver.speed_max
            
            # Did driver take damage
            if driver in medium_damage_drivers:
                flr = 20
                ceil = 40
            elif driver in minor_damage_drivers:
                ceil += 10

            # mu = numpy.average([flr, ceil])
            # stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
            # d_sr = numpy.random.normal(mu, stdev, 1)[0] + random()
            d_sr = randrange(flr, ceil+1) + random()
            # print(f'{driver}, {d_sr}')
            speed.append(d_sr)

    # Rank final speed
    final_ranks = scipy.stats.rankdata(speed, method='ordinal')

    # print('Assign FP:')
    # print(f'Total Cautions = {total_cautions}')

    # Assign race variance based on late caution
    if late_caution:
        # print('There was a late caution')
        race_variance = race_sim.track_variance_late_restart
    else:
        race_variance = race_sim.track_variance
    
    if total_cautions <= 7:
        race_variance += 0
    elif total_cautions <= 10:
        race_variance += 1
    elif total_cautions <= 13:
        race_variance += 2
    elif total_cautions >= 14:
        race_variance += 3

    # Assign finishing position
    # final_ranks = driver_s3_ranks if race_sim.race.num_stages() == 3 else driver_s4_ranks
    fp_vals = []
    for index, final_sp in enumerate(final_ranks):
        flr = final_sp - race_variance - driver_strategy[index]
        ceil = final_sp + race_variance + driver_strategy[index]

        driver = drivers[index]
        if driver_dnfs[index] is not None:
            # DNF drivers stay where they are
            fp_vals.append(speed[index])  # DNFs always fall to the bottom, but keep them in order stage to stage
        else:
            if driver in stage_1_green_penalty_drivers:
                ceil += race_sim.get_penalty_profile(1, True).floor_impact
                flr += race_sim.get_penalty_profile(1, True).ceiling_impact
            if driver in stage_1_yellow_penalty_drivers:
                ceil += race_sim.get_penalty_profile(1, False).floor_impact
                flr += race_sim.get_penalty_profile(1, False).ceiling_impact
            if driver in stage_2_green_penalty_drivers:
                ceil += race_sim.get_penalty_profile(2, True).floor_impact
                flr += race_sim.get_penalty_profile(2, True).ceiling_impact
            if driver in stage_2_yellow_penalty_drivers:
                ceil += race_sim.get_penalty_profile(2, False).floor_impact
                flr += race_sim.get_penalty_profile(2, False).ceiling_impact
            if driver in stage_3_green_penalty_drivers:
                ceil += race_sim.get_penalty_profile(3, True).floor_impact
                flr += race_sim.get_penalty_profile(3, True).ceiling_impact
            if driver in stage_3_yellow_penalty_drivers:
                ceil += race_sim.get_penalty_profile(3, False).floor_impact
                flr += race_sim.get_penalty_profile(3, False).ceiling_impact
            if driver in stage_4_green_penalty_drivers:
                ceil += race_sim.get_penalty_profile(4, True).floor_impact
                flr += race_sim.get_penalty_profile(4, True).ceiling_impact
            if driver in stage_4_yellow_penalty_drivers:
                ceil += race_sim.get_penalty_profile(4, False).floor_impact
                flr += race_sim.get_penalty_profile(4, False).ceiling_impact
        
            mu = numpy.average([flr, ceil])
            stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
            fp_vals.append(numpy.random.normal(mu, stdev, 1)[0] + random())
    fp_ranks = scipy.stats.rankdata(fp_vals, method='ordinal')

    # Assign fastest laps
    caution_laps = int(total_cautions * race_sim.laps_per_caution)
    fl_laps = race_sim.race.scheduled_laps - caution_laps
    # fl_vals = [max(int(randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100), 1)/100 * fl_laps), 1) for p in race_sim.fl_profiles.all().order_by('-pct_laps_led_min')]

    fl_vals = []
    cum = 0
    for p in race_sim.fl_profiles.all().order_by('-pct_fastest_laps_min'):
        pct = randrange(int(p.pct_fastest_laps_min*100), max(int(p.pct_fastest_laps_max*100), 1) + 1, 1) if p.pct_fastest_laps_min < p.pct_fastest_laps_max else int(p.pct_fastest_laps_min*100)
        cum_min = int(p.cum_fastest_laps_min * 100)
        cum_max = int(p.cum_fastest_laps_max * 100)
        
        attempts = 0
        while (cum + pct < cum_min or cum + pct > cum_max) and attempts < 10:
            pct = randrange(int(p.pct_fastest_laps_min*100), max(int(p.pct_fastest_laps_max*100), 1) + 1, 1)
            attempts += 1
            # print(f'cum = {cum}; pct = {pct}; min = {int(p.pct_fastest_laps_min*100)}; max = {int(p.pct_fastest_laps_max*100)+1}')
        
        if attempts == 10:
            break

        cum += pct
        v = max(int((pct/100) * fl_laps), 1)
        fl_vals.append(v)

        if cum >= 100:  # if we run out before we get to the last profile
            break

    fl_laps_remaining = fl_laps
    fl_laps_assigned = []
    profiles = list(race_sim.fl_profiles.all().order_by('-pct_fastest_laps_min'))
    for index, fl_val in enumerate(fl_vals):
    # for index, flp in enumerate(race_sim.fl_profiles.all().order_by('-pct_fastest_laps_min')):
        flp = profiles[index]
        fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        # print(f'index = {index}; flp = {flp}; fl_val = {fl_val}; fl_index = {fl_index}')
        # while fl_index in fl_laps_assigned:  # only assign FL to drivers that haven't gotten any yet
        #     fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)

        sp_index = int(numpy.where(final_ranks == fl_index)[0][0])
        driver_fl[sp_index] = fl_val # fl_vals[index]
        fl_laps_assigned.append(fl_index)

        fl_laps_remaining -= fl_val # fl_vals[index]
        
    # there may be remaining FL, assign using lowest profile
    # flp = race_sim.fl_profiles.all().order_by('-pct_fastest_laps_min').last()
    while fl_laps_remaining > 0:
        # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        fl_index = randrange(1, 21)
        sp_index = int(numpy.where(final_ranks == fl_index)[0][0])
        fl_val = max(fl_laps_remaining, randrange(1, 3))
        # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_val}')
        driver_fl[sp_index] += fl_val
        fl_laps_assigned.append(fl_index)

        fl_laps_remaining -= fl_val

    # Assign laps led
    ll_laps = race_sim.race.scheduled_laps
    # ll_vals = [max(int(randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100), 1)/100 * ll_laps), 1) for p in race_sim.ll_profiles.all().order_by('-pct_laps_led_min')]
    
    # -- First determine the number of LL awarded to each rank
    ll_vals = []
    cum = 0
    for p in race_sim.ll_profiles.all().order_by('rank_order'):
        pct = randrange(int(p.pct_laps_led_min*100), max(int(p.pct_laps_led_max*100), 1) + 1, 1) if p.pct_laps_led_min < p.pct_laps_led_max else int(p.pct_laps_led_min*100)
        cum_min = int(p.cum_laps_led_min * 100)
        cum_max = int(p.cum_laps_led_max * 100)

        attempts = 0
        while (cum + pct < cum_min or cum + pct > cum_max) and attempts < 10:
            pct = randrange(int(p.pct_laps_led_min*100), max(int(p.pct_laps_led_max*100), 1) + 1, 1)
            attempts += 1
            # print(f'cum = {cum}; pct = {pct}; min = {int(p.pct_laps_led_min*100)}; max = {int(p.pct_laps_led_max*100)+1}')
        
        if attempts == 10:
            break
        
        cum += pct
        v = max(int((pct/100) * ll_laps), 1)
        ll_vals.append(v)

        if cum >= 100:  # if we run out before we get to the last profile
            break

    # -- Next find eligible drivers for LL by giving each driver a randbetween(0, FL%), then ranking each driver
    fl_rank_vals = []
    for i in range(0, len(driver_fl)):
        fl_rank_vals.append(randrange(0, driver_fl[i]+1) + random())
    fl_ranks = len(fl_rank_vals) + 1 - scipy.stats.rankdata(fl_rank_vals, method='ordinal')

    # -- Finally, award LL to drivers based on FL ranks
    ll_laps_remaining = ll_laps
    ll_laps_assigned = []
    profiles = list(race_sim.ll_profiles.all().order_by('rank_order'))
    for index, ll_val in enumerate(ll_vals):
    # for index, llp in enumerate(race_sim.ll_profiles.all().order_by('-pct_laps_led_min')):
        llp = profiles[index]
        ll_index = int(numpy.where(fl_ranks == llp.rank_order)[0][0])
        # ll_index = randrange(llp.eligible_fl_min, llp.eligible_fl_max+1)
        # print(f'index = {index}; llp = {llp}; ll_val = {ll_val}; ll_index = {ll_index}')
        # while ll_index in ll_laps_assigned:  # only assign LL to drivers that haven't gotten any yet
        #     ll_index = randrange(llp.eligible_fl_min, llp.eligible_fl_max+1)

        # sp_index = int(numpy.where(final_ranks == ll_index)[0][0])
        driver_ll[ll_index] = ll_val # ll_vals[index]
        ll_laps_assigned.append(ll_index)

        ll_laps_remaining -= ll_val # ll_vals[index]
        
    # there may be remaining LL, assign using lowest profile in tranches of 5
    # llp = race_sim.ll_profiles.all().order_by('-rank_order').last()
    while ll_laps_remaining > 0:
        ll_index = randrange(1, 21)
        # while ll_index in ll_laps_assigned:  # only assign LL to drivers that haven't gotten any yet
        #     ll_index = randrange(1, 21)

        # sp_index = int(numpy.where(final_ranks == ll_index)[0][0])
        ll_val = min(ll_laps_remaining, 5)
        driver_ll[ll_index] += ll_val
        ll_laps_assigned.append(ll_index)

        # print(driver_ll)
        ll_laps_remaining -= ll_val

    df_race = pandas.DataFrame({
        'driver_id': driver_ids,
        'driver': driver_names,
        'sp': driver_starting_positions,
        'speed_min': driver_sp_mins,
        'speed_max': driver_sp_maxes,
        'best_possible': driver_bp_sp_mins,
        # 'worst_possible': driver_bp_sp_maxes,
        'dnf': driver_dnfs,
        's1_penalty': driver_s1_penalties,
        # 's1_rank': driver_s1_ranks,
        # 's1_fl': driver_s1_fl,
        # 's1_min': driver_s1_mins,
        # 's1_max': driver_s1_maxes,
        's2_penalty': driver_s2_penalties,
        # 's2_rank': driver_s2_ranks,
        # 's2_fl': driver_s2_fl,
        # 's2_min': driver_s2_mins,
        # 's2_max': driver_s2_maxes,
        's3_penalty': driver_s3_penalties,
        # 's3_fl': driver_s3_fl,
    })

    if race_sim.race.num_stages() > 3:
        # df_race['s3_min'] = driver_s3_mins
        # df_race['s3_max'] = driver_s3_maxes
        df_race['s4_penalty'] = driver_s4_penalties
        # df_race['s4_rank'] = driver_s4_ranks

    df_race['sr'] = final_ranks
    df_race['fp'] = fp_ranks
    df_race['fl'] = driver_fl
    df_race['ll'] = driver_ll

    # print(df_race)
    # df_race.to_csv('data/race.csv')

    return {
        'sr': final_ranks.tolist(),
        'fp': fp_ranks.tolist(),
        'll': driver_ll,
        'fl': driver_fl,
        # 'dam': driver_damage,
        # 'pen': driver_penalty
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
        drivers = race_sim.outcomes.all().order_by('starting_position', 'id')
        
        driver_ids = list(drivers.values_list('driver__nascar_driver_id', flat=True))
        driver_names = list(drivers.values_list('driver__full_name', flat=True))

        sr_list = [obj.get('sr') for obj in results]
        fp_list = [obj.get('fp') for obj in results]
        fl_list = [obj.get('fl') for obj in results]
        ll_list = [obj.get('ll') for obj in results]
        # dam_list = [obj.get('dam') for obj in results]
        # pen_list = [obj.get('pen') for obj in results]

        df_sr = pandas.DataFrame(sr_list, columns=driver_ids)
        df_fp = pandas.DataFrame(fp_list, columns=driver_ids)
        df_fl = pandas.DataFrame(fl_list, columns=driver_ids)
        df_ll = pandas.DataFrame(ll_list, columns=driver_ids)
        # df_dam = pandas.DataFrame(dam_list, columns=driver_ids)
        # df_pen = pandas.DataFrame(pen_list, columns=driver_ids)
        for driver in drivers:
            driver.sr_outcomes = df_sr[driver.driver.nascar_driver_id].tolist()
            driver.fp_outcomes = df_fp[driver.driver.nascar_driver_id].tolist()
            driver.avg_fp = numpy.average(driver.fp_outcomes)
            driver.fl_outcomes = df_fl[driver.driver.nascar_driver_id].tolist()
            driver.avg_fl = numpy.average(driver.fl_outcomes)
            driver.ll_outcomes = df_ll[driver.driver.nascar_driver_id].tolist()
            driver.avg_ll = numpy.average(driver.ll_outcomes)
            # driver.crash_outcomes = df_dam[driver.driver.nascar_driver_id].tolist()
            # driver.penalties_outcomes = df_pen[driver.driver.nascar_driver_id].tolist()
            driver.save()

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
        scores = [d.get_scores('draftkings') for d in race_sim.outcomes.all().order_by('starting_position')]

        jobs = []
        for i in range(0, race_sim.iterations):
            jobs.append(make_optimals_for_gto.si(
                [s[i] for s in scores],
                list(race_sim.outcomes.all().order_by('starting_position').values_list('id', flat=True)),
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
    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL, Sport.NASCAR)
    else:
        optimizer = get_optimizer(Site.DRAFTKINGS, Sport.NASCAR)

    drivers = models.RaceSimDriver.objects.filter(id__in=driver_ids)
    player_list = []

    for index, driver in enumerate(drivers.order_by('starting_position')):
        if ' ' in driver.driver.full_name:
            first = driver.driver.full_name.split(' ')[0]
            last = driver.driver.full_name.split(' ')[-1]
        else:
            first = driver.driver.full_name
            last = ''

        fppg = iterations_scores[index]

        player = Player(
            driver.driver.nascar_driver_id,
            first,
            last,
            ['D'],
            'Nasca',
            driver.dk_salary if site == 'draftkings' else driver.fd_salary,
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
                count += d_count_0.loc[driver.driver.nascar_driver_id]
            except KeyError:
                pass
            
            try:
                count += d_count_1.loc[driver.driver.nascar_driver_id]
            except KeyError:
                pass
            
            try:
                count += d_count_2.loc[driver.driver.nascar_driver_id]
            except KeyError:
                pass
            
            try:
                count += d_count_3.loc[driver.driver.nascar_driver_id]
            except KeyError:
                pass
            
            try:
                count += d_count_4.loc[driver.driver.nascar_driver_id]
            except KeyError:
                pass
            
            try:
                count += d_count_5.loc[driver.driver.nascar_driver_id]
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

        # Speed rank raw outcomes and speed rank distribution
        df_sr = pandas.DataFrame([d.sr_outcomes for d in race_sim.outcomes.all()], index=[d.driver.full_name for d in race_sim.outcomes.all()]).transpose()

        sr_list = []
        for sr in range(1, race_sim.outcomes.count()+1):
            sr_list.append(
                [df_sr[d.driver.full_name].value_counts()[sr] if sr in df_sr[d.driver.full_name].value_counts() else 0 for d in race_sim.outcomes.all().order_by('starting_position', 'id')]
            )
        df_sr_results = pandas.DataFrame(sr_list, index=range(0, race_sim.outcomes.count()), columns=list(race_sim.outcomes.all().order_by('starting_position', 'id').values_list('driver__full_name', flat=True)))

        # Finishing position raw outcomes and finishing position distribution
        df_fp = pandas.DataFrame([d.fp_outcomes for d in race_sim.outcomes.all()], index=[d.driver.full_name for d in race_sim.outcomes.all()]).transpose()

        fp_list = []
        for fp in range(1, race_sim.outcomes.count()+1):
            fp_list.append(
                [df_fp[d.driver.full_name].value_counts()[fp] if fp in df_fp[d.driver.full_name].value_counts() else 0 for d in race_sim.outcomes.all().order_by('starting_position', 'id')]
            )
        df_fp_results = pandas.DataFrame(fp_list, index=range(0, race_sim.outcomes.count()), columns=list(race_sim.outcomes.all().order_by('starting_position', 'id').values_list('driver__full_name', flat=True)))

        # FL outcomes
        df_fl = pandas.DataFrame([d.fl_outcomes for d in race_sim.outcomes.all()], index=[d.driver.full_name for d in race_sim.outcomes.all()]).transpose()

        # LL outcomes
        df_ll = pandas.DataFrame([d.ll_outcomes for d in race_sim.outcomes.all()], index=[d.driver.full_name for d in race_sim.outcomes.all()]).transpose()

        # crash outcomes
        df_dam = pandas.DataFrame([d.crash_outcomes for d in race_sim.outcomes.all()], index=[d.driver.full_name for d in race_sim.outcomes.all()]).transpose()

        # penalty outcomes
        df_pen = pandas.DataFrame([d.penalty_outcomes for d in race_sim.outcomes.all()], index=[d.driver.full_name for d in race_sim.outcomes.all()]).transpose()

        # DK
        df_dk = pandas.DataFrame(data={
            'sal': [d.dk_salary for d in race_sim.outcomes.all()],
            'start': [d.starting_position for d in race_sim.outcomes.all()],
            '50p': [numpy.percentile(d.get_scores('draftkings'), float(50)) for d in race_sim.outcomes.all()],
            '60p': [numpy.percentile(d.get_scores('draftkings'), float(60)) for d in race_sim.outcomes.all()],
            '70p': [numpy.percentile(d.get_scores('draftkings'), float(70)) for d in race_sim.outcomes.all()],
            '80p': [numpy.percentile(d.get_scores('draftkings'), float(80)) for d in race_sim.outcomes.all()],
            '90p': [numpy.percentile(d.get_scores('draftkings'), float(90)) for d in race_sim.outcomes.all()],
            'gto': [d.gto for d in race_sim.outcomes.all()]
        }, index=[d.driver.full_name for d in race_sim.outcomes.all()])

        with pandas.ExcelWriter(result_path) as writer:
            df_sr.to_excel(writer, sheet_name='Speed Rank Raw')
            df_sr_results.to_excel(writer, sheet_name='Speed Rank Distribution')
            df_fp.to_excel(writer, sheet_name='Finishing Position Raw')
            df_fp_results.to_excel(writer, sheet_name='Finishing Position Distribution')
            df_fl.to_excel(writer, sheet_name='Fastest Laps Raw')
            df_ll.to_excel(writer, sheet_name='Laps Led Raw')
            df_dam.to_excel(writer, sheet_name='Damage Raw')
            df_pen.to_excel(writer, sheet_name='Penalty Raw')
            df_dk.to_excel(writer, sheet_name='DK')

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


def get_score(row, **kwargs):
    if 'site' not in kwargs:
        raise Exception('Must provide a site.')
    site = kwargs.get('site')

    if 'sp' not in kwargs:
        raise Exception('Must provide sp')
    sp = kwargs.get('sp')

    fp = row.get('fp')
    pd = sp - fp
    fl = row.get('fl')
    ll = row.get('ll')

    return float(models.SITE_SCORING.get(site).get('place_differential') * pd + models.SITE_SCORING.get(site).get('fastest_laps') * fl + models.SITE_SCORING.get(site).get('laps_led') * ll + models.SITE_SCORING.get(site).get('finishing_position').get(str(fp))) 


@shared_task
def process_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        build = models.SlateBuild.objects.get(id=build_id)

        # create (or update) the projections
        for slate_player in build.slate.players.all():
            projection, created = models.BuildPlayerProjection.objects.get_or_create(
                slate_player=slate_player,
                build=build
            )
            try:
                sim_driver = build.sim.outcomes.get(driver=slate_player.driver)
                df_scores = pandas.DataFrame(data={
                    'fp': sim_driver.fp_outcomes,
                    'fl': sim_driver.fl_outcomes,
                    'll': sim_driver.ll_outcomes
                })

                projection.starting_position = sim_driver.starting_position
                projection.sim_scores = df_scores.apply(get_score, axis=1, site=build.slate.site, sp=sim_driver.starting_position).to_list()
                projection.projection = numpy.percentile(projection.sim_scores, float(50))
                projection.ceiling = numpy.percentile(projection.sim_scores, float(90))
                projection.s75 = numpy.percentile(projection.sim_scores, float(75))
                projection.gto = sim_driver.gto
                projection.save()
            except:
                pass

        task.status = 'success'
        task.content = f'{build} processed.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error processing your buyiuld: {e}'
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
                    print(models.Driver.objects.filter(full_name=alias.get_alias('nascar')))
                    slate_player.driver = models.Driver.objects.get(full_name=alias.get_alias('nascar'))
                    slate_player.save()

                    success_count += 1
                else:
                    missing_players.append(player_name)

        task.status = 'success'
        task.content = '{} players have been successfully added to {}.'.format(success_count, str(slate)) if len(missing_players) == 0 else '{} players have been successfully added to {}. {} players could not be identified.'.format(success_count, str(slate), len(missing_players))
        task.link = '/admin/nascar/missingalias/' if len(missing_players) > 0 else None
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing slate players: {e}'
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
        if build.configuration.optimize_by_percentile == 0:
            lineups = optimize.generateRandomLineups(
                build.projections.filter(in_play=True),
                build.total_lineups * build.configuration.lineup_multiplier,
                6,
                50000
            )

            for lineup in lineups:
                if build.slate.site == 'draftkings':
                    lineup = models.SlateBuildLineup.objects.create(
                        build=build,
                        player_1=lineup[0],
                        player_2=lineup[1],
                        player_3=lineup[2],
                        player_4=lineup[3],
                        player_5=lineup[4],
                        player_6=lineup[5],
                        total_salary=sum([lp.salary for lp in lineup])
                    )

                    lineup.save()
                    lineup.simulate()
                else:
                    raise Exception(f'{build.slate.site} is not available for building yet.')

                # print(f'dup = {lineup.duplicated}; {lineup.duplicated > build.configuration.duplicate_threshold}')
                if lineup.duplicated > build.configuration.duplicate_threshold:
                    # print('delete this lineup')
                    lineup.delete()
        else:
            lineups = optimize.optimize(build.slate.site, build.projections.filter(in_play=True), build.groups.filter(active=True), build.configuration, build.total_lineups)

            for lineup in lineups:
                if build.slate.site == 'draftkings':
                    lineup = models.SlateBuildLineup.objects.create(
                        build=build,
                        player_1=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[0].id, slate_player__slate=build.slate),
                        player_2=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[1].id, slate_player__slate=build.slate),
                        player_3=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[2].id, slate_player__slate=build.slate),
                        player_4=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[3].id, slate_player__slate=build.slate),
                        player_5=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[4].id, slate_player__slate=build.slate),
                        player_6=models.BuildPlayerProjection.objects.get(build=build, slate_player__slate_player_id=lineup.players[5].id, slate_player__slate=build.slate),
                        total_salary=lineup.salary_costs
                    )

                    lineup.save()
                    lineup.simulate()
                else:
                    raise Exception(f'{build.slate.site} is not available for building yet.')

                if lineup.duplicated > build.configuration.duplicate_threshold:
                    lineup.delete()
        
        task.status = 'success'
        task.content = f'{len(lineups)} lineups created.'
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

        ordered_lineups = build.lineups.all().order_by('-sort_proj')
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
            build_writer.writerow(['D', 'D', 'D', 'D', 'D', 'D'])

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

