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

        df_drivers = df_drivers.drop(columns=['num_finish', 'num_crashes', 'num_mech', 'num_penalty'])
        df_drivers.to_csv(result_path)

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

        with open(race_sim.input_file.path, mode='r') as input_file:
            csv_reader = csv.DictReader(input_file)

            for row in csv_reader:
                driver_id = row['nascar_driver_id']
                starting_position = row['starting_position']
                crash_rate = row['crash_rate']
                mech_rate = row['mech_rate']
                penalty_rate = row['penalty_rate']
                strategy_factor = row['strategy_factor']
                speed_min = row['speed_min']
                speed_max = row['speed_max']
                best_possible_speed = row['best_possible_speed']
                worst_possible_speed = row['worst_possible_speed']

                driver = models.Driver.objects.get(nascar_driver_id=driver_id)
                alias = models.Alias.find_alias(driver.full_name, 'nascar')

                dk_salary = dk_salaries.loc[[alias.dk_name]]['Salary'] if dk_salaries is not None else 0.0
                fd_salary = fd_salaries.loc[[alias.fd_name]] if fd_salaries is not None else 0.0

                models.RaceSimDriver.objects.create(
                    sim=race_sim,
                    driver=driver,
                    starting_position=starting_position,
                    dk_salary=dk_salary,
                    fd_salary=fd_salary,
                    speed_min=speed_min,
                    speed_max=speed_max,
                    best_possible_speed=best_possible_speed,
                    worst_possible_speed=worst_possible_speed,
                    crash_rate=crash_rate,
                    mech_rate=mech_rate,
                    infraction_rate=penalty_rate,
                    strategy_factor=strategy_factor
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
        chord([
            execute_sim_iteration.si(sim_id) for _ in range(0, race_sim.iterations)
        ], sim_execution_complete.s(sim_id, task_id))()

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
    driver_s1_ranks = [None for driver in drivers]
    driver_s1_mins = [None for driver in drivers]
    driver_s1_maxes = [None for driver in drivers]
    # driver_s1_fl = [0 for driver in drivers]
    
    driver_s2_penalties = [None for driver in drivers]
    driver_s2_ranks = [None for driver in drivers]
    driver_s2_mins = [None for driver in drivers]
    driver_s2_maxes = [None for driver in drivers]
    # driver_s2_fl = [0 for driver in drivers]
    
    driver_s3_penalties = [None for driver in drivers]
    driver_s3_ranks = [None for driver in drivers]
    driver_s3_mins = [None for driver in drivers]
    driver_s3_maxes = [None for driver in drivers]
    # driver_s3_fl = [0 for driver in drivers]

    if race_sim.race.num_stages() > 3:
        driver_s4_penalties = [None for driver in drivers]
        driver_s4_ranks = [None for driver in drivers]
        # driver_s4_fl = [0 for driver in drivers]

    driver_fl = [0 for driver in drivers]
    driver_ll = [0 for driver in drivers]

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
        num_laps = race_sim.race.get_laps_for_stage(stage)
        # print(f'Stage {stage}: {num_laps} laps')

        # Find # of cautions & caution type thresholds

        if stage < race_sim.race.num_stages():
            num_cautions = scipy.stats.poisson.rvs(race_sim.early_stage_caution_mean)

            debris_caution_cutoff = race_sim.early_stage_caution_prob_debris
            accident_small_caution_cutoff = race_sim.early_stage_caution_prob_accident_small
            accident_medium_caution_cutoff = race_sim.early_stage_caution_prob_accident_medium
            accident_major_caution_cutoff = race_sim.early_stage_caution_prob_accident_major
        else:
            num_cautions = scipy.stats.poisson.rvs(race_sim.final_stage_caution_mean)

            debris_caution_cutoff = race_sim.final_stage_caution_prob_debris
            accident_small_caution_cutoff = race_sim.final_stage_caution_prob_accident_small
            accident_medium_caution_cutoff = race_sim.final_stage_caution_prob_accident_medium
            accident_major_caution_cutoff = race_sim.final_stage_caution_prob_accident_major

        total_cautions += num_cautions
        # print(f'  There are {num_cautions} cautions.')
        # For each caution, assign damage

        for caution in range(0, num_cautions):
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
                max_cars = min(21, len(race_drivers))

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

                if damage_value == 0:
                    # print(f'{involved_car} [{involved_car.id}] takes no damage')
                    pass
                elif damage_value == 1:
                    # print(f'{involved_car} [{involved_car.id}] takes minor damage')
                    minor_damage_drivers.append(involved_car)
                elif damage_value == 2:
                    # print(f'{involved_car} [{involved_car.id}] takes medium damage')
                    medium_damage_drivers.append(involved_car)
                else:
                    # print(f'{involved_car} [{involved_car.id}] is out of the race')
                    race_drivers = list(filter((involved_car.id).__ne__, race_drivers))
                    dnf_drivers.append(involved_car)

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
                    elif driver in stage_1_yellow_penalty_drivers:
                        driver_s1_penalties[index] = 'Y'

                    # flr = driver.speed_min
                    # ceil = driver.speed_max
                elif stage == 2:
                    # Did driver have a penalty?
                    if driver in stage_2_green_penalty_drivers:
                        driver_s2_penalties[index] = 'G'
                    elif driver in stage_2_yellow_penalty_drivers:
                        driver_s2_penalties[index] = 'Y'

                    # flr = driver_s1_mins[index]
                    # ceil = driver_s1_maxes[index]
                elif stage == 3:
                    # Did driver have a penalty?
                    if driver in stage_3_green_penalty_drivers:
                        driver_s3_penalties[index] = 'G'
                    elif driver in stage_3_yellow_penalty_drivers:
                        driver_s3_penalties[index] = 'Y'

                    # flr = driver_s2_mins[index]
                    # ceil = driver_s2_maxes[index]
                elif stage == 4:
            # Did driver have a penalty?
                    if driver in stage_4_green_penalty_drivers:
                        driver_s4_penalties[index] = 'G'
                    elif driver in stage_4_yellow_penalty_drivers:
                        driver_s4_penalties[index] = 'Y'

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
                flr = 40
                ceil = 20
            elif driver in minor_damage_drivers:
                flr += 10

            mu = numpy.average([flr, ceil])
            stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
            d_sr = numpy.random.normal(mu, stdev, 1)[0] + random()
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
    fl_vals = [max(int(randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100), 1)/100 * fl_laps), 1) for p in race_sim.fl_profiles.all().order_by('-pct_laps_led_min')]

    fl_laps_remaining = fl_laps
    fl_laps_assigned = []
    for index, flp in enumerate(race_sim.fl_profiles.all().order_by('-pct_laps_led_min')):
        # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        while fl_index in fl_laps_assigned:  # only assign FL to drivers that haven't gotten any yet this stage
            fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)

        sp_index = int(numpy.where(final_ranks == fl_index)[0][0])
        # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_vals[index]}')
        driver_fl[sp_index] = fl_vals[index]
        fl_laps_assigned.append(fl_index)

        fl_laps_remaining -= fl_vals[index]
        
    # there may be remaining FL, assign using lowest profile
    flp = race_sim.fl_profiles.all().order_by('-pct_laps_led_min').last()
    while fl_laps_remaining > 0:
        # print(f'{fl_laps_remaining} fl laps remaining out of {fl_laps}')
        fl_index = randrange(flp.eligible_speed_min, flp.eligible_speed_max+1)
        sp_index = int(numpy.where(final_ranks == fl_index)[0][0])
        fl_val = max(int(randrange(int(flp.pct_laps_led_min*100), int(flp.pct_laps_led_max*100), 1)/100 * fl_laps), 1)
        # print(f'fl_index={fl_index}; sp_index={sp_index}; fl_val={fl_val}')
        driver_fl[sp_index] += fl_val
        fl_laps_assigned.append(fl_index)

        fl_laps_remaining -= fl_val

    # Assign laps led
    ll_laps = race_sim.race.scheduled_laps
    # ll_vals = [max(int(randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100), 1)/100 * ll_laps), 1) for p in race_sim.ll_profiles.all().order_by('-pct_laps_led_min')]
    
    ll_vals = []
    cum = 0
    for p in race_sim.ll_profiles.all().order_by('-pct_laps_led_min'):
        pct = randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100)+1, 1) if p.pct_laps_led_min < p.pct_laps_led_max else int(p.pct_laps_led_min*100)
        cum_min = int(p.cum_laps_led_min * 100)
        cum_max = int(p.cum_laps_led_max * 100)

        # print(f'p = {p}; pct = {pct}; cum = {cum}')
        while cum + pct < cum_min or cum + pct > cum_max:
            pct = randrange(int(p.pct_laps_led_min*100), int(p.pct_laps_led_max*100)+1, 1)
            # print(f'p = {p}; pct = {pct}; cum = {cum}')
        
        cum += pct
        v = max(int((pct/100) * ll_laps), 1)
        ll_vals.append(v)

        if cum >= 100:  # if we run out before we get to the last profile
            break

    ll_laps_remaining = ll_laps
    ll_laps_assigned = []
    profiles = list(race_sim.ll_profiles.all().order_by('-pct_laps_led_min'))
    for index, ll_val in enumerate(ll_vals):
    # for index, llp in enumerate(race_sim.ll_profiles.all().order_by('-pct_laps_led_min')):
        llp = profiles[index]
        ll_index = randrange(llp.eligible_fl_min, llp.eligible_fl_max+1)
        # print(f'index = {index}; llp = {llp}; ll_val = {ll_val}; ll_index = {ll_index}')
        while ll_index in ll_laps_assigned:  # only assign LL to drivers that haven't gotten any yet
            ll_index = randrange(llp.eligible_fl_min, llp.eligible_fl_max+1)

        sp_index = int(numpy.where(final_ranks == ll_index)[0][0])
        driver_ll[sp_index] = ll_val # ll_vals[index]
        ll_laps_assigned.append(ll_index)

        ll_laps_remaining -= ll_val # ll_vals[index]
        
    # there may be remaining LL, assign using lowest profile in tranches of 5
    llp = race_sim.ll_profiles.all().order_by('-pct_laps_led_min').last()
    while ll_laps_remaining > 0:
        ll_index = randrange(1, 21)
        # while ll_index in ll_laps_assigned:  # only assign LL to drivers that haven't gotten any yet
        #     ll_index = randrange(1, 21)

        sp_index = int(numpy.where(final_ranks == ll_index)[0][0])
        ll_val = max(ll_laps_remaining, 5)
        driver_ll[sp_index] += ll_val
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
        'fp': fp_ranks.tolist(),
        'll': driver_ll,
        'fl': driver_fl
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

        fp_list = [obj.get('fp') for obj in results]
        fl_list = [obj.get('fl') for obj in results]
        ll_list = [obj.get('ll') for obj in results]

        df_fp = pandas.DataFrame(fp_list, columns=driver_ids)
        df_fl = pandas.DataFrame(fl_list, columns=driver_ids)
        df_ll = pandas.DataFrame(ll_list, columns=driver_ids)
        for driver in drivers:
            driver.fp_outcomes = df_fp[driver.driver.nascar_driver_id].tolist()
            driver.avg_fp = numpy.average(driver.fp_outcomes)
            driver.fl_outcomes = df_fl[driver.driver.nascar_driver_id].tolist()
            driver.avg_fl = numpy.average(driver.fl_outcomes)
            driver.ll_outcomes = df_ll[driver.driver.nascar_driver_id].tolist()
            driver.avg_ll = numpy.average(driver.ll_outcomes)
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
def export_results(sim_id, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        race_sim = models.RaceSim.objects.get(id=sim_id)

        # Finishing position raw outcomes and finishing position distribution
        df_fp = pandas.DataFrame([d.fp_outcomes for d in race_sim.outcomes.all()], index=[d.driver.full_name for d in race_sim.outcomes.all()]).transpose()

        fp_list = []
        for fp in range(1, race_sim.outcomes.count()+1):
            fp_list.append(
                [df_fp[d.driver.full_name].value_counts()[fp] if fp in df_fp[d.driver.full_name].value_counts() else 0 for d in race_sim.outcomes.all().order_by('starting_position')]
            )
        df_fp_results = pandas.DataFrame(fp_list, index=range(0, race_sim.outcomes.count()), columns=list(race_sim.outcomes.all().order_by('starting_position').values_list('driver__full_name', flat=True)))

        # FL distribution
        df_fl = pandas.DataFrame([d.fl_outcomes for d in race_sim.outcomes.all()], index=[d.driver.full_name for d in race_sim.outcomes.all()]).transpose()

        # LL distribution
        df_ll = pandas.DataFrame([d.ll_outcomes for d in race_sim.outcomes.all()], index=[d.driver.full_name for d in race_sim.outcomes.all()]).transpose()

        # DK
        df_dk = pandas.DataFrame(data={
            'sal': [d.dk_salary for d in race_sim.outcomes.all()],
            'start': [d.starting_position for d in race_sim.outcomes.all()],
            '50p': [numpy.percentile(d.get_scores('draftkings'), float(50)) for d in race_sim.outcomes.all()],
            '60p': [numpy.percentile(d.get_scores('draftkings'), float(60)) for d in race_sim.outcomes.all()],
            '70p': [numpy.percentile(d.get_scores('draftkings'), float(70)) for d in race_sim.outcomes.all()],
            '80p': [numpy.percentile(d.get_scores('draftkings'), float(80)) for d in race_sim.outcomes.all()],
            '90p': [numpy.percentile(d.get_scores('draftkings'), float(90)) for d in race_sim.outcomes.all()],
        }, index=[d.driver.full_name for d in race_sim.outcomes.all()])


        with pandas.ExcelWriter(result_path) as writer:
            df_fp.to_excel(writer, sheet_name='Finishing Position Raw')
            df_fp_results.to_excel(writer, sheet_name='Finishing Position Distribution')
            df_fl.to_excel(writer, sheet_name='Fastest Laps Raw')
            df_ll.to_excel(writer, sheet_name='Laps Led Raw')
            df_dk.to_excel(writer, sheet_name='DK')

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
    pd = fp - sp
    fl = row.get('fl')
    ll = row.get('ll')

    return (models.SITE_SCORING.get(site).get('place_differential') * pd + models.SITE_SCORING.get(site).get('fastest_laps') * fl + models.SITE_SCORING.get(site).get('laps_led') * ll + models.SITE_SCORING.get(site).get('finishing_position').get(str(fp))) 


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
            projection.save()

        task.status = 'success'
        task.content = f'{build} processed.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error exporting FP results: {e}'
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

