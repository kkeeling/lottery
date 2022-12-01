import csv
import datetime
import decimal
import itertools
import json
import logging
import math
import numpy
import os
import pandas
import random
import re
import requests
import scipy
import sqlalchemy
import sys
import time
import traceback
import uuid

from celery import shared_task, chord, group, chain
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages.api import success
from django.db.models.aggregates import Count, Sum
from django.db.models import Q, F
from django.db import transaction

from io import StringIO

from configuration.models import BackgroundTask

from fanduel import models as fanduel_models
from yahoo import models as yahoo_models

from . import models
from . import optimize

from lottery.celery import app

logger = logging.getLogger(__name__)

user = settings.DATABASES['default']['USER']
password = settings.DATABASES['default']['PASSWORD']
database_name = settings.DATABASES['default']['NAME']
database_url = 'postgresql://{user}:{password}@db:5432/{database_name}'.format(
    user=user,
    password=password,
    database_name=database_name,
)

engine = sqlalchemy.create_engine(database_url, echo=False)


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
def update_vegas_for_week(week_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here

        week = models.Week.objects.get(id=week_id)
        week.update_vegas()

        task.status = 'success'
        task.content = 'Odds updated for {}.'.format(str(week))
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem updating vegas odds: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def update_market_projections():
    logger.info('Update Market Projections')
    r = requests.get(models.MARKET_PROJECTIONS_URL)
    
    if r.status_code < 300:
        projection_sets = r.json()
        logger.info(datetime.date.today())
        week = models.Week.objects.get(
            start__lte=datetime.date.today(),
            end__gte=datetime.date.today()
        )

        logger.info(week)
        if 'rg_fd' in projection_sets:
            models.MarketProjections.objects.create(
                site='fanduel',
                projection_site='rg',
                data=json.dumps(projection_sets.get('rg_fd')),
                week=week
            )
        if 'rg_dk' in projection_sets:
            models.MarketProjections.objects.create(
                site='draftkings',
                projection_site='rg',
                data=json.dumps(projection_sets.get('rg_dk')),
                week=week
            )
        if 'four_fd' in projection_sets:
            models.MarketProjections.objects.create(
                site='fanduel',
                projection_site='4for4',
                data=json.dumps(projection_sets.get('four_fd')),
                week=week
            )
        if 'four_dk' in projection_sets:
            models.MarketProjections.objects.create(
                site='draftkings',
                projection_site='4for4',
                data=json.dumps(projection_sets.get('four_dk')),
                week=week
            )
        if 'etr' in projection_sets:
            models.MarketProjections.objects.create(
                site='fanduel',
                projection_site='etr',
                data=json.dumps(projection_sets.get('etr')),
                week=week
            )
        if 'etr' in projection_sets:
            models.MarketProjections.objects.create(
                site='draftkings',
                projection_site='etr',
                data=json.dumps(projection_sets.get('etr')),
                week=week
            )
    logger.info('Done.')


@shared_task
def read_market_projection_csv(market_projections_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        market_projections = models.MarketProjections.objects.get(id=market_projections_id)
        df = pandas.read_csv(market_projections.projection_sheet)
        market_projections.data = json.dumps(df.to_dict('records'))
        market_projections.save()

        task.status = 'success'
        task.content = f'Market projections processed for {market_projections.projection_site}'
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem updating vegas odds: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def create_slates(week_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        week = models.Week.objects.get(id=week_id)

        # for each dfs site, create Th-M, early, aft, primetime, main, and showdown slates
        for site in models.SITE_OPTIONS:
            # Th-M slate
            slate, _ = models.Slate.objects.get_or_create(
                datetime=datetime.datetime(week.start.year, week.start.month, week.start.day, 20, 15, 0),
                end_datetime=datetime.datetime(week.end.year, week.end.month, week.end.day, 23, 59, 59),
                name=f'ThuMon-{str(week.slate_year)[-2:]}-{site[1]}-{str(week.num).zfill(2)}',
                week=week,
                site=site[0],
                is_main_slate=False,
                is_showdown=False,
                is_complete=False
            )
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='4for4_thu_mon'
            )
            if created:
                spi.projection_weight = 0.25
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='etr_all'
            )
            if created:
                spi.projection_weight = 0.32
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='rg_thu_mon'
            )
            if created:
                spi.projection_weight = 0.33
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_thu_mon'
            )
            if created:
                spi.projection_weight = 0.10
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_own_thu_mon'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            # spi, created = models.SlateProjectionImport.objects.get_or_create(
            #     slate=slate,
            #     projection_site='dailyroto_thu_mon'
            # )
            # if created:
            #     spi.projection_weight = 0.0
            #     spi.ownership_weight = 0.0
            #     spi.field_lineup_count = 100
            #     spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='linestar_thu_mon'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 100
                spi.save()

            build, _ = models.FindWinnerBuild.objects.get_or_create(
                slate=slate
            )
            build.field_lineup_creation_strategy = 'optimize_by_ownership'
            build.save()
            
            find_slate_games(
                slate.id,
                BackgroundTask.objects.create(
                    name=f'Finding slate games for {slate}',
                    user=task.user
                ).id
            )

            # Sun-Mon slate
            sunday = week.start + datetime.timedelta(days=(6 - week.start.weekday() + 7) % 7)
            slate, _ = models.Slate.objects.get_or_create(
                datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 13, 0, 0),
                end_datetime=datetime.datetime(week.end.year, week.end.month, week.end.day, 23, 59, 59),
                name=f'SunMon-{str(week.slate_year)[-2:]}-{site[1]}-{str(week.num).zfill(2)}',
                week=week,
                site=site[0],
                is_main_slate=False,
                is_showdown=False,
                is_complete=False
            )
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='4for4_sun_mon'
            )
            if created:
                spi.projection_weight = 0.25
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='etr_all'
            )
            if created:
                spi.projection_weight = 0.32
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='rg_sun_mon'
            )
            if created:
                spi.projection_weight = 0.33
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_sun_mon'
            )
            if created:
                spi.projection_weight = 0.10
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_own_sun_mon'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            # spi, created = models.SlateProjectionImport.objects.get_or_create(
            #     slate=slate,
            #     projection_site='dailyroto_sun_mon'
            # )
            # if created:
            #     spi.projection_weight = 0.0
            #     spi.ownership_weight = 0.0
            #     spi.field_lineup_count = 100
            #     spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='linestar_sun_mon'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 100
                spi.save()

            build, _ = models.FindWinnerBuild.objects.get_or_create(
                slate=slate
            )
            build.field_lineup_creation_strategy = 'optimize_by_ownership'
            build.save()
            
            find_slate_games(
                slate.id,
                BackgroundTask.objects.create(
                    name=f'Finding slate games for {slate}',
                    user=task.user
                ).id
            )

            # early slate
            slate, _ = models.Slate.objects.get_or_create(
                datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 13, 0, 0),
                end_datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 15, 59, 59),
                name=f'Early-{str(week.slate_year)[-2:]}-{site[1]}-{str(week.num).zfill(2)}',
                week=week,
                site=site[0],
                is_main_slate=False,
                is_showdown=False,
                is_complete=False
            )
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='4for4_early'
            )
            if created:
                spi.projection_weight = 0.25
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 100
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='etr'
            )
            if created:
                spi.projection_weight = 0.32
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 100
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='rg_early'
            )
            if created:
                spi.projection_weight = 0.33
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 100
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_early'
            )
            if created:
                spi.projection_weight = 0.10
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_own_early'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 100
                spi.save()

            build, _ = models.FindWinnerBuild.objects.get_or_create(
                slate=slate
            )
            build.field_lineup_creation_strategy = 'optimize_by_ownership'
            build.save()
            
            find_slate_games(
                slate.id,
                BackgroundTask.objects.create(
                    name=f'Finding slate games for {slate}',
                    user=task.user
                ).id
            )

            # main slate
            slate, _ = models.Slate.objects.get_or_create(
                datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 13, 0, 0),
                end_datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 19, 59, 59),
                name=f'Main-{str(week.slate_year)[-2:]}-{site[1]}-{str(week.num).zfill(2)}',
                week=week,
                site=site[0],
                is_main_slate=True,
                is_showdown=False,
                is_complete=False
            )
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='4for4'
            )
            if created:
                spi.projection_weight = 0.25
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 100
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='etr'
            )
            if created:
                spi.projection_weight = 0.32
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 100
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='rg'
            )
            if created:
                spi.projection_weight = 0.33
                spi.ownership_weight = 0.25
                spi.field_lineup_count = 100
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo'
            )
            if created:
                spi.projection_weight = 0.10
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_own'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.25
                spi.field_lineup_count = 100
                spi.save()

            build, _ = models.FindWinnerBuild.objects.get_or_create(
                slate=slate
            )
            build.field_lineup_creation_strategy = 'optimize_by_ownership'
            build.save()
            
            find_slate_games(
                slate.id,
                BackgroundTask.objects.create(
                    name=f'Finding slate games for {slate}',
                    user=task.user
                ).id
            )

            # afternoon slate
            slate, _ = models.Slate.objects.get_or_create(
                datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 16, 5, 0),
                end_datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 19, 59, 59),
                name=f'Aft-{str(week.slate_year)[-2:]}-{site[1]}-{str(week.num).zfill(2)}',
                week=week,
                site=site[0],
                is_main_slate=False,
                is_showdown=False,
                is_complete=False
            )
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='4for4_afternoon'
            )
            if created:
                spi.projection_weight = 0.25
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='etr'
            )
            if created:
                spi.projection_weight = 0.32
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='rg_afternoon'
            )
            if created:
                spi.projection_weight = 0.33
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_afternoon'
            )
            if created:
                spi.projection_weight = 0.10
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_own_afternoon'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            # spi, created = models.SlateProjectionImport.objects.get_or_create(
            #     slate=slate,
            #     projection_site='dailyroto_afternoon'
            # )
            # if created:
            #     spi.projection_weight = 0.0
            #     spi.ownership_weight = 0.0
            #     spi.field_lineup_count = 100
            #     spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='linestar_afternoon'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 100
                spi.save()

            build, _ = models.FindWinnerBuild.objects.get_or_create(
                slate=slate
            )
            build.field_lineup_creation_strategy = 'optimize_by_ownership'
            build.save()
            
            find_slate_games(
                slate.id,
                BackgroundTask.objects.create(
                    name=f'Finding slate games for {slate}',
                    user=task.user
                ).id
            )

            # turbo slate
            slate, _ = models.Slate.objects.get_or_create(
                datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 16, 25, 0),
                end_datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 19, 59, 59),
                name=f'Turbo-{str(week.slate_year)[-2:]}-{site[1]}-{str(week.num).zfill(2)}',
                week=week,
                site=site[0],
                is_main_slate=False,
                is_showdown=False,
                is_complete=False
            )
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='4for4_turbo'
            )
            if created:
                spi.projection_weight = 0.25
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='etr'
            )
            if created:
                spi.projection_weight = 0.32
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='rg_turbo'
            )
            if created:
                spi.projection_weight = 0.33
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_turbo'
            )
            if created:
                spi.projection_weight = 0.10
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_own_turbo'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            # spi, created = models.SlateProjectionImport.objects.get_or_create(
            #     slate=slate,
            #     projection_site='dailyroto_turbo'
            # )
            # if created:
            #     spi.projection_weight = 0.0
            #     spi.ownership_weight = 0.0
            #     spi.field_lineup_count = 100
            #     spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='linestar_turbo'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 100
                spi.save()

            build, _ = models.FindWinnerBuild.objects.get_or_create(
                slate=slate
            )
            build.field_lineup_creation_strategy = 'optimize_by_ownership'
            build.save()
            
            find_slate_games(
                slate.id,
                BackgroundTask.objects.create(
                    name=f'Finding slate games for {slate}',
                    user=task.user
                ).id
            )

            # primetime slate
            slate, _ = models.Slate.objects.get_or_create(
                datetime=datetime.datetime(sunday.year, sunday.month, sunday.day, 20, 20, 0),
                end_datetime=datetime.datetime(week.end.year, week.end.month, week.end.day, 23, 59, 59),
                name=f'PT-{str(week.slate_year)[-2:]}-{site[1]}-{str(week.num).zfill(2)}',
                week=week,
                site=site[0],
                is_main_slate=False,
                is_showdown=False,
                is_complete=False
            )
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='4for4_primetime'
            )
            if created:
                spi.projection_weight = 0.25
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='etr_all'
            )
            if created:
                spi.projection_weight = 0.32
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='rg_primetime'
            )
            if created:
                spi.projection_weight = 0.33
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_primetime'
            )
            if created:
                spi.projection_weight = 0.10
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 0
                spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='awesemo_own_primetime'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.5
                spi.field_lineup_count = 150
                spi.save()
        
            # spi, created = models.SlateProjectionImport.objects.get_or_create(
            #     slate=slate,
            #     projection_site='dailyroto_primetime'
            # )
            # if created:
            #     spi.projection_weight = 0.0
            #     spi.ownership_weight = 0.0
            #     spi.field_lineup_count = 100
            #     spi.save()
        
            spi, created = models.SlateProjectionImport.objects.get_or_create(
                slate=slate,
                projection_site='linestar_primetime'
            )
            if created:
                spi.projection_weight = 0.0
                spi.ownership_weight = 0.0
                spi.field_lineup_count = 100
                spi.save()

            build, _ = models.FindWinnerBuild.objects.get_or_create(
                slate=slate
            )
            build.field_lineup_creation_strategy = 'optimize_by_ownership'
            build.save()
            
            find_slate_games(
                slate.id,
                BackgroundTask.objects.create(
                    name=f'Finding slate games for {slate}',
                    user=task.user
                ).id
            )

            # showdown slates
            for game in week.games.all():
                is_island = (game.game_date == datetime.datetime(week.start.year, week.start.month, week.start.day, 20, 15, 0)) or (game.game_date == datetime.datetime(sunday.year, sunday.month, sunday.day, 20, 20, 0)) or (game.game_date == datetime.datetime(week.end.year, week.end.month, week.end.day, 20, 15, 0))

                slate, _ = models.Slate.objects.get_or_create(
                    datetime=game.game_date,
                    name=f'SD-{str(week.slate_year)[-2:]}-{site[1]}-{str(week.num).zfill(2)}-{game.away_team}@{game.home_team}',
                    week=week,
                    site=site[0],
                    is_main_slate=False,
                    is_showdown=True,
                    is_complete=False
                )
        
                # spi, created = models.SlateProjectionImport.objects.get_or_create(
                #     slate=slate,
                #     projection_site='4for4'
                # )
                # if created:
                #     spi.projection_weight = 0.25
                #     spi.ownership_weight = 0.0
                #     spi.field_lineup_count = 0
                #     spi.save()
        
                spi, created = models.SlateProjectionImport.objects.get_or_create(
                    slate=slate,
                    projection_site='etr_sd' if is_island else 'etr_all'
                )
                if created:
                    spi.projection_weight = 0.42
                    spi.ownership_weight = 0.5 if is_island else 0.0
                    spi.field_lineup_count = 0
                    spi.save()
            
                spi, created = models.SlateProjectionImport.objects.get_or_create(
                    slate=slate,
                    projection_site='rg_sd' if is_island else 'rg_all'
                )
                if created:
                    spi.projection_weight = 0.43
                    spi.ownership_weight = 0.25 if is_island else 0.0
                    spi.field_lineup_count = 0
                    spi.save()
            
                spi, created = models.SlateProjectionImport.objects.get_or_create(
                    slate=slate,
                    projection_site='awesemo_sd' if is_island else 'awesemo'
                )
                if created:
                    spi.projection_weight = 0.15
                    spi.ownership_weight = 0.0
                    spi.field_lineup_count = 0
                    spi.save()
            
                if is_island:
                    spi, created = models.SlateProjectionImport.objects.get_or_create(
                        slate=slate,
                        projection_site='awesemo_own_sd'
                    )
                    if created:
                        spi.projection_weight = 0.0
                        spi.ownership_weight = 0.25
                        spi.field_lineup_count = 0
                        spi.save()

                models.FindWinnerBuild.objects.get_or_create(
                    slate=slate,
                    field_lineup_creation_strategy='optimize_by_projection'
                )

                models.FindWinnerBuild.objects.get_or_create(
                    slate=slate,
                    build_type='se',
                    field_lineup_creation_strategy='csv_upload'
                )
                
                models.SlateGame.objects.get_or_create(
                    slate=slate,
                    game=game
                )

        task.status = 'success'
        task.content = 'Slates created for {}.'.format(str(week))
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem updating vegas odds: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def update_slate_from_mp(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        slate = models.Slate.objects.get(id=slate_id)

        success_count = 0
        missing_players = []

        # For each projection source, update raw projections
        for proj_src in slate.projection_imports.all():
            logger.info(proj_src.projection_site)
            # delete previous raw projections
            models.SlatePlayerRawProjection.objects.filter(
                projection_site=proj_src.projection_site,
                slate_player__slate=slate
            ).delete()

            mps = slate.week.market_projections.filter(
                site=slate.site,
                projection_site=proj_src.projection_site
            ).order_by('-pull_time')

            logger.info(mps)
            if mps.count() > 0:
                mp = mps[0]
                df = pandas.read_json(mp.data)

                column_headers = models.SheetColumnHeaders.objects.get(
                    projection_site=proj_src.projection_site,
                    site=slate.site,
                    use_for_data_feed=not bool(mp.projection_sheet.name)
                )

                # if proj_src.projection_site == 'etr':
                #     column_headers.column_player_name = df.columns[0]
                #     column_headers.save()

                if df is not None:
                    for _, row in df.iterrows():
                        try:
                            player_name = row[column_headers.column_player_name].strip()
                        except:
                            continue

                        if player_name is None:
                            continue

                        if row[column_headers.column_team] is None or row[column_headers.column_team] == '':
                            continue
                        
                        try:
                            if row[column_headers.column_team] == 'JAX':
                                team = 'JAC'
                            elif row[column_headers.column_team] == 'LA':
                                team = 'LAR'
                            elif row[column_headers.column_team] == 'LVR':
                                team = 'LV'
                            elif row[column_headers.column_team] == 'KCC':
                                team = 'KC'
                            elif row[column_headers.column_team] == 'LVR':
                                team = 'LV'
                            elif row[column_headers.column_team] == 'GBP':
                                team = 'GB'
                            elif row[column_headers.column_team] == 'NOS':
                                team = 'NO'
                            else:
                                team = row[column_headers.column_team].strip()
                        except:
                            continue
                        
                        median_projection = row[column_headers.column_median_projection] if column_headers.column_median_projection is not None and row[column_headers.column_median_projection] != '' and not math.isnan(float(row[column_headers.column_median_projection])) else 0.0
                        floor_projection = row[column_headers.column_floor_projection] if column_headers.column_floor_projection is not None and row[column_headers.column_floor_projection] != '' and not math.isnan(float(row[column_headers.column_floor_projection])) else 0.0
                        ceiling_projection = row[column_headers.column_ceiling_projection] if column_headers.column_ceiling_projection is not None and row[column_headers.column_ceiling_projection] != '' and not math.isnan(float(row[column_headers.column_ceiling_projection])) else 0.0
                        rush_att_projection = row[column_headers.column_rush_att_projection] if column_headers.column_rush_att_projection is not None and row[column_headers.column_rush_att_projection] != '' and not math.isnan(float(row[column_headers.column_rush_att_projection])) else 0.0
                        rec_projection = row[column_headers.column_rec_projection] if column_headers.column_rec_projection is not None and row[column_headers.column_rec_projection] != '' and not math.isnan(float(row[column_headers.column_rec_projection])) else 0.0
                        
                        # TODO: don't include OP
                        ownership_projection = float(row[column_headers.column_own_projection]) if column_headers.column_own_projection is not None and row[column_headers.column_own_projection] != '' and row[column_headers.column_own_projection] != '-' and not math.isnan(float(row[column_headers.column_own_projection])) else 0.0

                        if proj_src.projection_site == 'etr_all':
                            ownership_projection /= 100.0
                            alias = models.Alias.find_alias(player_name, proj_src.projection_site)
                        elif proj_src.projection_site.startswith('etr'):
                            ownership_projection /= 100.0
                            alias = models.Alias.find_alias(player_name, slate.site if bool(mp.projection_sheet.name) else proj_src.projection_site)  # use site name if market projection is from csv, otherwise use projection site alias
                        elif proj_src.projection_site.startswith('rg'):
                            ownership_projection /= 100.0
                            alias = models.Alias.find_alias(player_name, slate.site if bool(mp.projection_sheet.name) else proj_src.projection_site)  # use site name if market projection is from csv, otherwise use projection site alias
                        elif proj_src.projection_site.startswith('awesemo_own'):
                            ownership_projection /= 100.0
                            alias = models.Alias.find_alias(player_name, proj_src.projection_site)
                        elif proj_src.projection_site.startswith('dailyroto'):
                            ownership_projection /= 100.0
                            alias = models.Alias.find_alias(player_name, proj_src.projection_site)
                        elif proj_src.projection_site.startswith('linestar'):
                            ownership_projection /= 100.0
                            alias = models.Alias.find_alias(player_name, proj_src.projection_site)
                        elif proj_src.projection_site == 'sabersim':
                            ownership_projection /= 100.0
                            alias = models.Alias.find_alias(player_name, proj_src.projection_site)
                        else:
                            alias = models.Alias.find_alias(player_name, proj_src.projection_site)

                        if alias is not None:
                            try:
                                slate_player = models.SlatePlayer.objects.get(
                                    slate=slate,
                                    name=alias.get_alias(slate.site),
                                    team=team,
                                    roster_position__in=['QB', 'RB', 'WR', 'TE', 'DST', 'D', 'DEF', 'FLEX', 'UTIL']
                                )

                                mu = 0.0
                                ceil = 0.0
                                flr = 0.0
                                stdev = 0.0

                                if median_projection is not None and median_projection != '' and median_projection > 0.0:
                                    mu = float(median_projection)

                                    if floor_projection is not None and ceiling_projection is not None:
                                        ceil = float(ceiling_projection)
                                        flr = float(floor_projection)

                                        stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
                                
                                if slate.site == 'yahoo':
                                    val = mu / slate_player.salary
                                else:
                                    val = mu / (slate_player.salary / 1000)

                                try:
                                    p = models.SlatePlayerRawProjection.objects.create(
                                        slate_player=slate_player,
                                        projection_site=proj_src.projection_site,
                                        projection=mu,
                                        value=val,
                                        floor=flr,
                                        ceiling=ceil,
                                        stdev=stdev,
                                        ownership_projection=float(ownership_projection) if float(ownership_projection) < 1.0 else float(ownership_projection)/100.0,
                                        adjusted_opportunity=float(rec_projection) * 2.75 + float(rush_att_projection) if slate.site == 'draftkings' else float(rec_projection) * 2.0 + float(rush_att_projection)
                                    )

                                    # create captain/mvp version if necessary
                                    try:
                                        cpt_slate_player = models.SlatePlayer.objects.get(
                                            slate=slate,
                                            name=alias.get_alias(slate.site),
                                            team=team,
                                            roster_position__in=['CPT', 'MVP']
                                        )

                                        mu = 0.0
                                        ceil = 0.0
                                        flr = 0.0
                                        stdev = 0.0

                                        if median_projection is not None and median_projection != '' and median_projection > 0.0:
                                            mu = float(median_projection) * 1.5

                                            if floor_projection is not None and ceiling_projection is not None:
                                                ceil = float(ceiling_projection) * 1.5
                                                flr = float(floor_projection) * 1.5

                                                stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
                                        
                                        if slate.site == 'yahoo':
                                            val = mu / cpt_slate_player.salary
                                        else:
                                            val = mu / (cpt_slate_player.salary / 1000)

                                        models.SlatePlayerRawProjection.objects.create(
                                            slate_player=cpt_slate_player,
                                            projection_site=proj_src.projection_site,
                                            projection=mu,
                                            value=val,
                                            floor=flr,
                                            ceiling=ceil,
                                            stdev=stdev,
                                            ownership_projection=float(ownership_projection) if float(ownership_projection) < 1.0 else float(ownership_projection)/100.0,
                                            adjusted_opportunity=float(rec_projection) * 2.75 + float(rush_att_projection) if slate.site == 'draftkings' else float(rec_projection) * 2.0 + float(rush_att_projection)
                                        )
                                    except models.SlatePlayer.DoesNotExist:
                                        pass
                                    
                                    success_count += 1
                                except:
                                    logger.info(f'Could not create projection for {slate_player.name} with {proj_src.projection_site}')
                            except models.SlatePlayer.DoesNotExist:
                                pass
                                # logger.info(f'{alias} does not exist.')
                        else:
                            missing_players.append(player_name)
        
        task.status = 'success'
        task.content = 'Market projections have been successfully updated for {}.'.format(str(slate)) if len(missing_players) == 0 else 'Market projections have been successfully updated for {}. {} players could not be identified.'.format(str(slate), len(missing_players))
        task.link = '/admin/nfl/missingalias/' if len(missing_players) > 0 else None
        task.save()        
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem updating slate from market projections: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


def find_qbs(qb=None):
    '''
    Query DB for relevant QBs.

    If qb parameter is used, find opposing qb
    '''
    if qb is None:
        qbs = models.SlatePlayer.objects.filter(
            slate__site='fanduel',
            site_pos='QB',
            projection__projection__gt=9.9,
            fantasy_points__gt=4.9,
            slate_game__isnull=False,
            slate__is_main_slate=True
        ).select_related('projection').annotate(proj=F('projection__projection'))
    else:
        qbs = models.SlatePlayer.objects.filter(
            slate=qb.slate,
            site_pos='QB',
            projection__projection__gt=9.9,
            fantasy_points__gt=4.9,
            team=qb.get_opponent()
        ).select_related(
            'projection'
        ).annotate(
            proj=F('projection__projection')
        )
    
    return qbs


def find_players(qb, position, depth, find_opponent=False):
    team = qb.get_opponent() if find_opponent else qb.team
    players = models.SlatePlayer.objects.filter(
        slate=qb.slate,
        site_pos=position,
        team=team,
        projection__isnull=False
    ).select_related(
        'projection'
    ).annotate(
        proj=F('projection__projection')
    ).order_by('-proj')

    if players.count() < depth:
        return players
    return players[:depth]


def get_corr_matrix(site, is_sd=False):
    if site == 'fanduel' or site == 'yahoo':
        r_df = pandas.read_csv('data/r.csv', index_col=0)
    elif site == 'draftkings':
        if is_sd:
            r_df = pandas.read_csv('data/dk_r_sd.csv', index_col=0)
        else:
            r_df = pandas.read_csv('data/dk_r.csv', index_col=0)
    return r_df


@shared_task
def simulate_game(game_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        game = models.SlateGame.objects.get(id=game_id)
        logger.info(game)

        N = models.SIM_ITERATIONS
        if game.slate.site == 'fanduel':
            dst_label = 'D' 
        elif game.slate.site == 'yahoo':
            dst_label = 'DEF' 
        else:
            dst_label = 'DST' 

        # set up correlation
        r_df = get_corr_matrix(game.slate.site, game.slate.is_showdown)
        c_target = r_df.to_numpy()
        r0 = [0] * c_target.shape[0]
        mv_norm = scipy.stats.multivariate_normal(mean=r0, cov=c_target)
        rand_Nmv = mv_norm.rvs(N) 
        rand_U = scipy.stats.norm.cdf(rand_Nmv)

        # initialize variables
        home_qb = None
        home_rb1 = None
        home_rb2 = None
        home_rb3 = None
        home_wr1 = None
        home_wr2 = None
        home_wr3 = None
        home_wr4 = None
        home_wr5 = None
        home_te1 = None
        home_te2 = None
        home_k = None
        home_dst = None
        away_qb = None
        away_rb1 = None
        away_rb2 = None
        away_rb3 = None
        away_wr1 = None
        away_wr2 = None
        away_wr3 = None
        away_wr4 = None
        away_wr5 = None
        away_te1 = None
        away_te2 = None
        away_k = None
        away_dst = None

        home_qb_rv = None 
        home_rb1_rv = None 
        home_rb2_rv = None 
        home_rb3_rv = None 
        home_wr1_rv = None 
        home_wr2_rv = None 
        home_wr3_rv = None 
        home_wr4_rv = None 
        home_wr5_rv = None 
        home_te1_rv = None 
        home_te2_rv = None 
        home_k_rv = None 
        home_dst_rv = None 
        away_qb_rv = None 
        away_rb1_rv = None 
        away_rb2_rv = None 
        away_rb3_rv = None 
        away_wr1_rv = None 
        away_wr2_rv = None 
        away_wr3_rv = None 
        away_wr4_rv = None 
        away_wr5_rv = None 
        away_te1_rv = None 
        away_te2_rv = None 
        away_k_rv = None 
        away_dst_rv = None 

        cpt_home_qb = None
        cpt_home_rb1 = None
        cpt_home_rb2 = None
        cpt_home_rb3 = None
        cpt_home_wr1 = None
        cpt_home_wr2 = None
        cpt_home_wr3 = None
        cpt_home_wr4 = None
        cpt_home_wr5 = None
        cpt_home_te1 = None
        cpt_home_te2 = None
        cpt_home_k = None
        cpt_home_dst = None
        cpt_away_qb = None
        cpt_away_rb1 = None
        cpt_away_rb2 = None
        cpt_away_rb3 = None
        cpt_away_wr1 = None
        cpt_away_wr2 = None
        cpt_away_wr3 = None
        cpt_away_wr4 = None
        cpt_away_wr5 = None
        cpt_away_te1 = None
        cpt_away_te2 = None
        cpt_away_k = None
        cpt_away_dst = None

        # Set up game players
        home_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_home_players().values_list('id', flat=True)).exclude(slate_player__roster_position__in=['CPT', 'MVP'])
        away_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_away_players().values_list('id', flat=True)).exclude(slate_player__roster_position__in=['CPT', 'MVP'])

        home_qbs = home_players.filter(slate_player__site_pos='QB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_rbs = home_players.filter(slate_player__site_pos='RB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_wrs = home_players.filter(slate_player__site_pos='WR').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_tes = home_players.filter(slate_player__site_pos='TE').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_ks = home_players.filter(slate_player__site_pos='K').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_dsts = home_players.filter(slate_player__site_pos=dst_label).exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')

        home_qb = home_qbs[0]
        home_rb1 = home_rbs[0]
        if home_rbs.count() > 1:
            home_rb2 = home_rbs[1]
        if home_rbs.count() > 2:
            home_rb3 = home_rbs[2]
        home_wr1 = home_wrs[0]
        home_wr2 = home_wrs[1]
        if home_wrs.count() > 2:
            home_wr3 = home_wrs[2]
        if home_wrs.count() > 3:
            home_wr4 = home_wrs[3]
        if home_wrs.count() > 4:
            home_wr5 = home_wrs[4]
        home_te1 = home_tes[0]
        if home_tes.count() > 1:
            home_te2 = home_tes[1]
        if home_ks.count() > 0:
            home_k = home_ks[0]
        home_dst = home_dsts[0]

        away_qbs = away_players.filter(slate_player__site_pos='QB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_rbs = away_players.filter(slate_player__site_pos='RB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_wrs = away_players.filter(slate_player__site_pos='WR').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_tes = away_players.filter(slate_player__site_pos='TE').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_ks = away_players.filter(slate_player__site_pos='K').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_dsts = away_players.filter(slate_player__site_pos=dst_label).exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')

        away_qb = away_qbs[0]
        away_rb1 = away_rbs[0]
        if away_rbs.count() > 1:
            away_rb2 = away_rbs[1]
        if away_rbs.count() > 2:
            away_rb3 = away_rbs[2]
        away_wr1 = away_wrs[0]
        away_wr2 = away_wrs[1]
        if away_wrs.count() > 2:
            away_wr3 = away_wrs[2]
        if away_wrs.count() > 3:
            away_wr4 = away_wrs[3]
        if away_wrs.count() > 4:
            away_wr5 = away_wrs[4]
        away_te1 = away_tes[0]
        if away_tes.count() > 1:
            away_te2 = away_tes[1]
        if away_ks.count() > 0:
            away_k = away_ks[0]
        away_dst = away_dsts[0]

        # Simulate

        home_qb_rv = scipy.stats.gamma((float(home_qb.projection)/float(home_qb.stdev))**2, scale=(float(home_qb.stdev)**2)/float(home_qb.projection))
        home_rb1_rv = scipy.stats.gamma((float(home_rb1.projection)/float(home_rb1.stdev))**2, scale=(float(home_rb1.stdev)**2)/float(home_rb1.projection))
        if home_rb2:
            home_rb2_rv = scipy.stats.gamma((float(home_rb2.projection)/float(home_rb2.stdev))**2, scale=(float(home_rb2.stdev)**2)/float(home_rb2.projection))
        if home_rb3:
            home_rb3_rv = scipy.stats.gamma((float(home_rb3.projection)/float(home_rb3.stdev))**2, scale=(float(home_rb3.stdev)**2)/float(home_rb3.projection))
        home_wr1_rv = scipy.stats.gamma((float(home_wr1.projection)/float(home_wr1.stdev))**2, scale=(float(home_wr1.stdev)**2)/float(home_wr1.projection))
        home_wr2_rv = scipy.stats.gamma((float(home_wr2.projection)/float(home_wr2.stdev))**2, scale=(float(home_wr2.stdev)**2)/float(home_wr2.projection))
        if home_wr3:
            home_wr3_rv = scipy.stats.gamma((float(home_wr3.projection)/float(home_wr3.stdev))**2, scale=(float(home_wr3.stdev)**2)/float(home_wr3.projection))
        if home_wr4:
            home_wr4_rv = scipy.stats.gamma((float(home_wr4.projection)/float(home_wr4.stdev))**2, scale=(float(home_wr4.stdev)**2)/float(home_wr4.projection))
        if home_wr5:
            home_wr5_rv = scipy.stats.gamma((float(home_wr5.projection)/float(home_wr5.stdev))**2, scale=(float(home_wr5.stdev)**2)/float(home_wr5.projection))
        home_te1_rv = scipy.stats.gamma((float(home_te1.projection)/float(home_te1.stdev))**2, scale=(float(home_te1.stdev)**2)/float(home_te1.projection))
        if home_te2:
            home_te2_rv = scipy.stats.gamma((float(home_te2.projection)/float(home_te2.stdev))**2, scale=(float(home_te2.stdev)**2)/float(home_te2.projection))
        if home_k:
            home_k_rv = scipy.stats.gamma((float(home_k.projection)/float(home_k.stdev))**2, scale=(float(home_k.stdev)**2)/float(home_k.projection))
        home_dst_rv = scipy.stats.gamma((float(home_dst.projection)/float(home_dst.stdev))**2, scale=(float(home_dst.stdev)**2)/float(home_dst.projection))
        
        away_qb_rv = scipy.stats.gamma((float(away_qb.projection)/float(away_qb.stdev))**2, scale=(float(away_qb.stdev)**2)/float(away_qb.projection))
        away_rb1_rv = scipy.stats.gamma((float(away_rb1.projection)/float(away_rb1.stdev))**2, scale=(float(away_rb1.stdev)**2)/float(away_rb1.projection))
        if away_rb2:
            away_rb2_rv = scipy.stats.gamma((float(away_rb2.projection)/float(away_rb2.stdev))**2, scale=(float(away_rb2.stdev)**2)/float(away_rb2.projection))
        if away_rb3:
            away_rb3_rv = scipy.stats.gamma((float(away_rb3.projection)/float(away_rb3.stdev))**2, scale=(float(away_rb3.stdev)**2)/float(away_rb3.projection))
        away_wr1_rv = scipy.stats.gamma((float(away_wr1.projection)/float(away_wr1.stdev))**2, scale=(float(away_wr1.stdev)**2)/float(away_wr1.projection))
        away_wr2_rv = scipy.stats.gamma((float(away_wr2.projection)/float(away_wr2.stdev))**2, scale=(float(away_wr2.stdev)**2)/float(away_wr2.projection))
        if away_wr3:
            away_wr3_rv = scipy.stats.gamma((float(away_wr3.projection)/float(away_wr3.stdev))**2, scale=(float(away_wr3.stdev)**2)/float(away_wr3.projection))
        if away_wr4:
            away_wr4_rv = scipy.stats.gamma((float(away_wr4.projection)/float(away_wr4.stdev))**2, scale=(float(away_wr4.stdev)**2)/float(away_wr4.projection))
        if away_wr5:
            away_wr5_rv = scipy.stats.gamma((float(away_wr5.projection)/float(away_wr5.stdev))**2, scale=(float(away_wr5.stdev)**2)/float(away_wr5.projection))
        away_te1_rv = scipy.stats.gamma((float(away_te1.projection)/float(away_te1.stdev))**2, scale=(float(away_te1.stdev)**2)/float(away_te1.projection))
        if away_te2:
            away_te2_rv = scipy.stats.gamma((float(away_te2.projection)/float(away_te2.stdev))**2, scale=(float(away_te2.stdev)**2)/float(away_te2.projection))
        if away_k:
            away_k_rv = scipy.stats.gamma((float(away_k.projection)/float(away_k.stdev))**2, scale=(float(away_k.stdev)**2)/float(away_k.projection))
        away_dst_rv = scipy.stats.gamma((float(away_dst.projection)/float(away_dst.stdev))**2, scale=(float(away_dst.stdev)**2)/float(away_dst.projection))

        arr = []

        i = 0
        rand_home_qb = home_qb_rv.ppf(rand_U[:,i])
        arr.append(rand_home_qb)

        i += 1
        rand_home_rb1 = home_rb1_rv.ppf(rand_U[:,i])
        arr.append(rand_home_rb1)

        if home_rb2_rv:
            i += 1
            rand_home_rb2 = home_rb2_rv.ppf(rand_U[:,i])
            arr.append(rand_home_rb2)

        if home_rb3_rv:
            i += 1
            rand_home_rb3 = home_rb3_rv.ppf(rand_U[:,i])
            arr.append(rand_home_rb3)

        i += 1
        rand_home_wr1 = home_wr1_rv.ppf(rand_U[:,i])
        arr.append(rand_home_wr1)

        i += 1
        rand_home_wr2 = home_wr2_rv.ppf(rand_U[:,i])
        arr.append(rand_home_wr2)

        if home_wr3_rv:
            i += 1
            rand_home_wr3 = home_wr3_rv.ppf(rand_U[:,i])
            arr.append(rand_home_wr3)

        if home_wr4_rv:
            i += 1
            rand_home_wr4 = home_wr4_rv.ppf(rand_U[:,i])
            arr.append(rand_home_wr4)

        if home_wr5_rv:
            i += 1
            rand_home_wr5 = home_wr5_rv.ppf(rand_U[:,i])
            arr.append(rand_home_wr5)

        i += 1
        rand_home_te1 = home_te1_rv.ppf(rand_U[:,i])
        arr.append(rand_home_te1)

        if home_te2_rv:
            i += 1
            rand_home_te2 = home_te2_rv.ppf(rand_U[:, i])
            arr.append(rand_home_te2)

        if home_k_rv:
            i += 1
            rand_home_k = home_k_rv.ppf(rand_U[:, i])
            arr.append(rand_home_k)

        i += 1
        rand_home_dst = home_dst_rv.ppf(rand_U[:, i])
        arr.append(rand_home_dst)

        i += 1
        rand_away_qb = away_qb_rv.ppf(rand_U[:,i])
        arr.append(rand_away_qb)

        i += 1
        rand_away_rb1 = away_rb1_rv.ppf(rand_U[:,i])
        arr.append(rand_away_rb1)

        if away_rb2_rv:
            i += 1
            rand_away_rb2 = away_rb2_rv.ppf(rand_U[:,i])
            arr.append(rand_away_rb2)

        if away_rb3_rv:
            i += 1
            rand_away_rb3 = away_rb3_rv.ppf(rand_U[:,i])
            arr.append(rand_away_rb3)

        i += 1
        rand_away_wr1 = away_wr1_rv.ppf(rand_U[:,i])
        arr.append(rand_away_wr1)

        i += 1
        rand_away_wr2 = away_wr2_rv.ppf(rand_U[:,i])
        arr.append(rand_away_wr2)

        if away_wr3_rv:
            i += 1
            rand_away_wr3 = away_wr3_rv.ppf(rand_U[:,i])
            arr.append(rand_away_wr3)

        if away_wr4_rv:
            i += 1
            rand_away_wr4 = away_wr4_rv.ppf(rand_U[:,i])
            arr.append(rand_away_wr4)

        if away_wr5_rv:
            i += 1
            rand_away_wr5 = away_wr5_rv.ppf(rand_U[:,i])
            arr.append(rand_away_wr5)

        i += 1
        rand_away_te1 = away_te1_rv.ppf(rand_U[:,i])
        arr.append(rand_away_te1)

        if away_te2_rv:
            i += 1
            rand_away_te2 = away_te2_rv.ppf(rand_U[:, i])
            arr.append(rand_away_te2)

        if away_k_rv:
            i += 1
            rand_away_k = away_k_rv.ppf(rand_U[:, i])
            arr.append(rand_away_k)

        i += 1
        rand_away_dst = away_dst_rv.ppf(rand_U[:, i])
        arr.append(rand_away_dst)

        df_scores = pandas.DataFrame(arr)
        # logger.info(df_scores)

        game.game_sim = json.dumps(df_scores.to_json())
        game.save()
        
        # assign outcomes to players
        home_qb.sim_scores = numpy.round(rand_home_qb, 2).tolist()
        home_qb.median = numpy.median(home_qb.sim_scores)
        home_qb.s20 = numpy.percentile(home_qb.sim_scores, 20)
        home_qb.s75 = numpy.percentile(home_qb.sim_scores, 75)
        home_qb.s90 = numpy.percentile(home_qb.sim_scores, 90)
        home_qb.save()
        home_rb1.sim_scores = numpy.round(rand_home_rb1, 2).tolist()
        home_rb1.median = numpy.median(home_rb1.sim_scores)
        home_rb1.s20 = numpy.percentile(home_rb1.sim_scores, 20)
        home_rb1.s75 = numpy.percentile(home_rb1.sim_scores, 75)
        home_rb1.s90 = numpy.percentile(home_rb1.sim_scores, 90)
        home_rb1.save()
        if home_rb2:
            home_rb2.sim_scores = numpy.round(rand_home_rb2, 2).tolist()
            home_rb2.median = numpy.median(home_rb2.sim_scores)
            home_rb2.s20 = numpy.percentile(home_rb2.sim_scores, 20)
            home_rb2.s75 = numpy.percentile(home_rb2.sim_scores, 75)
            home_rb2.s90 = numpy.percentile(home_rb2.sim_scores, 90)
            home_rb2.save()
        if home_rb3:
            home_rb3.sim_scores = numpy.round(rand_home_rb3, 2).tolist()
            home_rb3.median = numpy.median(home_rb3.sim_scores)
            home_rb3.s20 = numpy.percentile(home_rb3.sim_scores, 20)
            home_rb3.s75 = numpy.percentile(home_rb3.sim_scores, 75)
            home_rb3.s90 = numpy.percentile(home_rb3.sim_scores, 90)
            home_rb3.save()
        home_wr1.sim_scores = numpy.round(rand_home_wr1, 2).tolist()
        home_wr1.median = numpy.median(home_wr1.sim_scores)
        home_wr1.s20 = numpy.percentile(home_wr1.sim_scores, 20)
        home_wr1.s75 = numpy.percentile(home_wr1.sim_scores, 75)
        home_wr1.s90 = numpy.percentile(home_wr1.sim_scores, 90)
        home_wr1.save()
        home_wr2.sim_scores = numpy.round(rand_home_wr2, 2).tolist()
        home_wr2.median = numpy.median(home_wr2.sim_scores)
        home_wr2.s20 = numpy.percentile(home_wr2.sim_scores, 20)
        home_wr2.s75 = numpy.percentile(home_wr2.sim_scores, 75)
        home_wr2.s90 = numpy.percentile(home_wr2.sim_scores, 90)
        home_wr2.save()
        if home_wr3:
            home_wr3.sim_scores = numpy.round(rand_home_wr3, 2).tolist()
            home_wr3.median = numpy.median(home_wr3.sim_scores)
            home_wr3.s20 = numpy.percentile(home_wr3.sim_scores, 20)
            home_wr3.s75 = numpy.percentile(home_wr3.sim_scores, 75)
            home_wr3.s90 = numpy.percentile(home_wr3.sim_scores, 90)
            home_wr3.save()
        if home_wr4:
            home_wr4.sim_scores = numpy.round(rand_home_wr4, 2).tolist()
            home_wr4.median = numpy.median(home_wr4.sim_scores)
            home_wr4.s20 = numpy.percentile(home_wr4.sim_scores, 20)
            home_wr4.s75 = numpy.percentile(home_wr4.sim_scores, 75)
            home_wr4.s90 = numpy.percentile(home_wr4.sim_scores, 90)
            home_wr4.save()
        if home_wr5:
            home_wr5.sim_scores = numpy.round(rand_home_wr5, 2).tolist()
            home_wr5.median = numpy.median(home_wr5.sim_scores)
            home_wr5.s20 = numpy.percentile(home_wr5.sim_scores, 20)
            home_wr5.s75 = numpy.percentile(home_wr5.sim_scores, 75)
            home_wr5.s90 = numpy.percentile(home_wr5.sim_scores, 90)
            home_wr5.save()
        home_te1.sim_scores = numpy.round(rand_home_te1, 2).tolist()
        home_te1.median = numpy.median(home_te1.sim_scores)
        home_te1.s20 = numpy.percentile(home_te1.sim_scores, 20)
        home_te1.s75 = numpy.percentile(home_te1.sim_scores, 75)
        home_te1.s90 = numpy.percentile(home_te1.sim_scores, 90)
        home_te1.save()
        if home_te2:
            home_te2.sim_scores = numpy.round(rand_home_te2, 2).tolist()
            home_te2.median = numpy.median(home_te2.sim_scores)
            home_te2.s20 = numpy.percentile(home_te2.sim_scores, 20)
            home_te2.s75 = numpy.percentile(home_te2.sim_scores, 75)
            home_te2.s90 = numpy.percentile(home_te2.sim_scores, 90)
            home_te2.save()
        if home_k:
            home_k.sim_scores = numpy.round(rand_home_k, 2).tolist()
            home_k.median = numpy.median(home_k.sim_scores)
            home_k.s20 = numpy.percentile(home_k.sim_scores, 20)
            home_k.s75 = numpy.percentile(home_k.sim_scores, 75)
            home_k.s90 = numpy.percentile(home_k.sim_scores, 90)
            home_k.save()
        home_dst.sim_scores = numpy.round(rand_home_dst, 2).tolist()
        home_dst.median = numpy.median(home_dst.sim_scores)
        home_dst.s20 = numpy.percentile(home_dst.sim_scores, 20)
        home_dst.s75 = numpy.percentile(home_dst.sim_scores, 75)
        home_dst.s90 = numpy.percentile(home_dst.sim_scores, 90)
        home_dst.save()
        away_qb.sim_scores = numpy.round(rand_away_qb, 2).tolist()
        away_qb.median = numpy.median(away_qb.sim_scores)
        away_qb.s20 = numpy.percentile(away_qb.sim_scores, 20)
        away_qb.s75 = numpy.percentile(away_qb.sim_scores, 75)
        away_qb.s90 = numpy.percentile(away_qb.sim_scores, 90)
        away_qb.save()
        away_rb1.sim_scores = numpy.round(rand_away_rb1, 2).tolist()
        away_rb1.median = numpy.median(away_rb1.sim_scores)
        away_rb1.s20 = numpy.percentile(away_rb1.sim_scores, 20)
        away_rb1.s75 = numpy.percentile(away_rb1.sim_scores, 75)
        away_rb1.s90 = numpy.percentile(away_rb1.sim_scores, 90)
        away_rb1.save()
        if away_rb2:
            away_rb2.sim_scores = numpy.round(rand_away_rb2, 2).tolist()
            away_rb2.median = numpy.median(away_rb2.sim_scores)
            away_rb2.s20 = numpy.percentile(away_rb2.sim_scores, 20)
            away_rb2.s75 = numpy.percentile(away_rb2.sim_scores, 75)
            away_rb2.s90 = numpy.percentile(away_rb2.sim_scores, 90)
            away_rb2.save()
        if away_rb3:
            away_rb3.sim_scores = numpy.round(rand_away_rb3, 2).tolist()
            away_rb3.median = numpy.median(away_rb3.sim_scores)
            away_rb3.s20 = numpy.percentile(away_rb3.sim_scores, 20)
            away_rb3.s75 = numpy.percentile(away_rb3.sim_scores, 75)
            away_rb3.s90 = numpy.percentile(away_rb3.sim_scores, 90)
            away_rb3.save()
        away_wr1.sim_scores = numpy.round(rand_away_wr1, 2).tolist()
        away_wr1.median = numpy.median(away_wr1.sim_scores)
        away_wr1.s20 = numpy.percentile(away_wr1.sim_scores, 20)
        away_wr1.s75 = numpy.percentile(away_wr1.sim_scores, 75)
        away_wr1.s90 = numpy.percentile(away_wr1.sim_scores, 90)
        away_wr1.save()
        away_wr2.sim_scores = numpy.round(rand_away_wr2, 2).tolist()
        away_wr2.median = numpy.median(away_wr2.sim_scores)
        away_wr2.s20 = numpy.percentile(away_wr2.sim_scores, 20)
        away_wr2.s75 = numpy.percentile(away_wr2.sim_scores, 75)
        away_wr2.s90 = numpy.percentile(away_wr2.sim_scores, 90)
        away_wr2.save()
        if away_wr3:
            away_wr3.sim_scores = numpy.round(rand_away_wr3, 2).tolist()
            away_wr3.median = numpy.median(away_wr3.sim_scores)
            away_wr3.s20 = numpy.percentile(away_wr3.sim_scores, 20)
            away_wr3.s75 = numpy.percentile(away_wr3.sim_scores, 75)
            away_wr3.s90 = numpy.percentile(away_wr3.sim_scores, 90)
            away_wr3.save()
        if away_wr4:
            away_wr4.sim_scores = numpy.round(rand_away_wr4, 2).tolist()
            away_wr4.median = numpy.median(away_wr4.sim_scores)
            away_wr4.s20 = numpy.percentile(away_wr4.sim_scores, 20)
            away_wr4.s75 = numpy.percentile(away_wr4.sim_scores, 75)
            away_wr4.s90 = numpy.percentile(away_wr4.sim_scores, 90)
            away_wr4.save()
        if away_wr5:
            away_wr5.sim_scores = numpy.round(rand_away_wr5, 2).tolist()
            away_wr5.median = numpy.median(away_wr5.sim_scores)
            away_wr5.s20 = numpy.percentile(away_wr5.sim_scores, 20)
            away_wr5.s75 = numpy.percentile(away_wr5.sim_scores, 75)
            away_wr5.s90 = numpy.percentile(away_wr5.sim_scores, 90)
            away_wr5.save()
        away_te1.sim_scores = numpy.round(rand_away_te1, 2).tolist()
        away_te1.median = numpy.median(away_te1.sim_scores)
        away_te1.s20 = numpy.percentile(away_te1.sim_scores, 20)
        away_te1.s75 = numpy.percentile(away_te1.sim_scores, 75)
        away_te1.s90 = numpy.percentile(away_te1.sim_scores, 90)
        away_te1.save()
        if away_te2:
            away_te2.sim_scores = numpy.round(rand_away_te2, 2).tolist()
            away_te2.median = numpy.median(away_te2.sim_scores)
            away_te2.s20 = numpy.percentile(away_te2.sim_scores, 20)
            away_te2.s75 = numpy.percentile(away_te2.sim_scores, 75)
            away_te2.s90 = numpy.percentile(away_te2.sim_scores, 90)
            away_te2.save()
        if away_k:
            away_k.sim_scores = numpy.round(rand_away_k, 2).tolist()
            away_k.median = numpy.median(away_k.sim_scores)
            away_k.s20 = numpy.percentile(away_k.sim_scores, 20)
            away_k.s75 = numpy.percentile(away_k.sim_scores, 75)
            away_k.s90 = numpy.percentile(away_k.sim_scores, 90)
            away_k.save()
        away_dst.sim_scores = numpy.round(rand_away_dst, 2).tolist()
        away_dst.median = numpy.median(away_dst.sim_scores)
        away_dst.s20 = numpy.percentile(away_dst.sim_scores, 20)
        away_dst.s75 = numpy.percentile(away_dst.sim_scores, 75)
        away_dst.s90 = numpy.percentile(away_dst.sim_scores, 90)
        away_dst.save()
        
        # assign outcomes to captains if necessary
        cpt_home_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_home_players().values_list('id', flat=True)).filter(slate_player__roster_position__in=['CPT', 'MVP'])
        cpt_away_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_away_players().values_list('id', flat=True)).filter(slate_player__roster_position__in=['CPT', 'MVP'])

        cpt_home_qbs = cpt_home_players.filter(slate_player__site_pos='QB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_home_rbs = cpt_home_players.filter(slate_player__site_pos='RB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_home_wrs = cpt_home_players.filter(slate_player__site_pos='WR').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_home_tes = cpt_home_players.filter(slate_player__site_pos='TE').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_home_ks = cpt_home_players.filter(slate_player__site_pos='K').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_home_dsts = cpt_home_players.filter(slate_player__site_pos=dst_label).exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')

        if cpt_home_qbs.count() > 0:
            cpt_home_qb = cpt_home_qbs[0]
        if cpt_home_rbs.count() > 0:
            cpt_home_rb1 = cpt_home_rbs[0]
        if cpt_home_rbs.count() > 1:
            cpt_home_rb2 = cpt_home_rbs[1]
        if cpt_home_rbs.count() > 2:
            cpt_home_rb3 = cpt_home_rbs[2]
        if cpt_home_wrs.count() > 0:
            cpt_home_wr1 = cpt_home_wrs[0]
        if cpt_home_wrs.count() > 1:
            cpt_home_wr2 = cpt_home_wrs[1]
        if cpt_home_wrs.count() > 2:
            cpt_home_wr3 = cpt_home_wrs[2]
        if cpt_home_wrs.count() > 3:
            cpt_home_wr4 = cpt_home_wrs[3]
        if cpt_home_wrs.count() > 4:
            cpt_home_wr5 = cpt_home_wrs[4]
        if cpt_home_tes.count() > 0:
            cpt_home_te1 = cpt_home_tes[0]
        if cpt_home_tes.count() > 1:
            cpt_home_te2 = cpt_home_tes[1]
        if cpt_home_ks.count() > 0:
            cpt_home_k = cpt_home_ks[0]
        if cpt_home_dsts.count() > 0:
            cpt_home_dst = cpt_home_dsts[0]

        cpt_away_qbs = cpt_away_players.filter(slate_player__site_pos='QB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_away_rbs = cpt_away_players.filter(slate_player__site_pos='RB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_away_wrs = cpt_away_players.filter(slate_player__site_pos='WR').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_away_tes = cpt_away_players.filter(slate_player__site_pos='TE').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_away_ks = cpt_away_players.filter(slate_player__site_pos='K').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        cpt_away_dsts = cpt_away_players.filter(slate_player__site_pos=dst_label).exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')

        if cpt_away_qbs.count() > 0:
            cpt_away_qb = cpt_away_qbs[0]
        if cpt_away_rbs.count() > 0:
            cpt_away_rb1 = cpt_away_rbs[0]
        if cpt_away_rbs.count() > 1:
            cpt_away_rb2 = cpt_away_rbs[1]
        if cpt_away_rbs.count() > 2:
            cpt_away_rb3 = cpt_away_rbs[2]
        if cpt_away_wrs.count() > 0:
            cpt_away_wr1 = cpt_away_wrs[0]
        if cpt_away_wrs.count() > 1:
            cpt_away_wr2 = cpt_away_wrs[1]
        if cpt_away_wrs.count() > 2:
            cpt_away_wr3 = cpt_away_wrs[2]
        if cpt_away_wrs.count() > 3:
            cpt_away_wr4 = cpt_away_wrs[3]
        if cpt_away_wrs.count() > 4:
            cpt_away_wr5 = cpt_away_wrs[4]
        if cpt_away_tes.count() > 0:
            cpt_away_te1 = cpt_away_tes[0]
        if cpt_away_tes.count() > 1:
            cpt_away_te2 = cpt_away_tes[1]
        if cpt_away_ks.count() > 0:
            cpt_away_k = cpt_away_ks[0]
        if cpt_away_dsts.count() > 0:
            cpt_away_dst = cpt_away_dsts[0]

        if cpt_home_qb:
            cpt_home_qb.sim_scores = (numpy.round(rand_home_qb, 2) * 1.5).tolist()
            cpt_home_qb.median = numpy.median(cpt_home_qb.sim_scores)
            cpt_home_qb.s20 = numpy.percentile(cpt_home_qb.sim_scores, 20)
            cpt_home_qb.s75 = numpy.percentile(cpt_home_qb.sim_scores, 75)
            cpt_home_qb.s90 = numpy.percentile(cpt_home_qb.sim_scores, 90)
            cpt_home_qb.save()
        if cpt_home_rb1:
            cpt_home_rb1.sim_scores = (numpy.round(rand_home_rb1, 2) * 1.5).tolist()
            cpt_home_rb1.median = numpy.median(cpt_home_rb1.sim_scores)
            cpt_home_rb1.s20 = numpy.percentile(cpt_home_rb1.sim_scores, 20)
            cpt_home_rb1.s75 = numpy.percentile(cpt_home_rb1.sim_scores, 75)
            cpt_home_rb1.s90 = numpy.percentile(cpt_home_rb1.sim_scores, 90)
            cpt_home_rb1.save()
        if cpt_home_rb2:
            cpt_home_rb2.sim_scores = (numpy.round(rand_home_rb2, 2) * 1.5).tolist()
            cpt_home_rb2.median = numpy.median(cpt_home_rb2.sim_scores)
            cpt_home_rb2.s20 = numpy.percentile(cpt_home_rb2.sim_scores, 20)
            cpt_home_rb2.s75 = numpy.percentile(cpt_home_rb2.sim_scores, 75)
            cpt_home_rb2.s90 = numpy.percentile(cpt_home_rb2.sim_scores, 90)
            cpt_home_rb2.save()
        if cpt_home_rb3:
            cpt_home_rb3.sim_scores = (numpy.round(rand_home_rb3, 2) * 1.5).tolist()
            cpt_home_rb3.median = numpy.median(cpt_home_rb3.sim_scores)
            cpt_home_rb3.s20 = numpy.percentile(cpt_home_rb3.sim_scores, 20)
            cpt_home_rb3.s75 = numpy.percentile(cpt_home_rb3.sim_scores, 75)
            cpt_home_rb3.s90 = numpy.percentile(cpt_home_rb3.sim_scores, 90)
            cpt_home_rb3.save()
        if cpt_home_wr1:
            cpt_home_wr1.sim_scores = (numpy.round(rand_home_wr1, 2) * 1.5).tolist()
            cpt_home_wr1.median = numpy.median(cpt_home_wr1.sim_scores)
            cpt_home_wr1.s20 = numpy.percentile(cpt_home_wr1.sim_scores, 20)
            cpt_home_wr1.s75 = numpy.percentile(cpt_home_wr1.sim_scores, 75)
            cpt_home_wr1.s90 = numpy.percentile(cpt_home_wr1.sim_scores, 90)
            cpt_home_wr1.save()
        if cpt_home_wr2:
            cpt_home_wr2.sim_scores = (numpy.round(rand_home_wr2, 2) * 1.5).tolist()
            cpt_home_wr2.median = numpy.median(cpt_home_wr2.sim_scores)
            cpt_home_wr2.s20 = numpy.percentile(cpt_home_wr2.sim_scores, 20)
            cpt_home_wr2.s75 = numpy.percentile(cpt_home_wr2.sim_scores, 75)
            cpt_home_wr2.s90 = numpy.percentile(cpt_home_wr2.sim_scores, 90)
            cpt_home_wr2.save()
        if cpt_home_wr3:
            cpt_home_wr3.sim_scores = (numpy.round(rand_home_wr3, 2) * 1.5).tolist()
            cpt_home_wr3.median = numpy.median(cpt_home_wr3.sim_scores)
            cpt_home_wr3.s20 = numpy.percentile(cpt_home_wr3.sim_scores, 20)
            cpt_home_wr3.s75 = numpy.percentile(cpt_home_wr3.sim_scores, 75)
            cpt_home_wr3.s90 = numpy.percentile(cpt_home_wr3.sim_scores, 90)
            cpt_home_wr3.save()
        if cpt_home_wr4:
            cpt_home_wr4.sim_scores = (numpy.round(rand_home_wr4, 2) * 1.5).tolist()
            cpt_home_wr4.median = numpy.median(cpt_home_wr4.sim_scores)
            cpt_home_wr4.s20 = numpy.percentile(cpt_home_wr4.sim_scores, 20)
            cpt_home_wr4.s75 = numpy.percentile(cpt_home_wr4.sim_scores, 75)
            cpt_home_wr4.s90 = numpy.percentile(cpt_home_wr4.sim_scores, 90)
            cpt_home_wr4.save()
        if cpt_home_wr5:
            cpt_home_wr5.sim_scores = (numpy.round(rand_home_wr5, 2) * 1.5).tolist()
            cpt_home_wr5.median = numpy.median(cpt_home_wr5.sim_scores)
            cpt_home_wr5.s20 = numpy.percentile(cpt_home_wr5.sim_scores, 20)
            cpt_home_wr5.s75 = numpy.percentile(cpt_home_wr5.sim_scores, 75)
            cpt_home_wr5.s90 = numpy.percentile(cpt_home_wr5.sim_scores, 90)
            cpt_home_wr5.save()
        if cpt_home_te1:
            cpt_home_te1.sim_scores = (numpy.round(rand_home_te1, 2) * 1.5).tolist()
            cpt_home_te1.median = numpy.median(cpt_home_te1.sim_scores)
            cpt_home_te1.s20 = numpy.percentile(cpt_home_te1.sim_scores, 20)
            cpt_home_te1.s75 = numpy.percentile(cpt_home_te1.sim_scores, 75)
            cpt_home_te1.s90 = numpy.percentile(cpt_home_te1.sim_scores, 90)
            cpt_home_te1.save()
        if cpt_home_te2:
            cpt_home_te2.sim_scores = (numpy.round(rand_home_te2, 2) * 1.5).tolist()
            cpt_home_te2.median = numpy.median(cpt_home_te2.sim_scores)
            cpt_home_te2.s20 = numpy.percentile(cpt_home_te2.sim_scores, 20)
            cpt_home_te2.s75 = numpy.percentile(cpt_home_te2.sim_scores, 75)
            cpt_home_te2.s90 = numpy.percentile(cpt_home_te2.sim_scores, 90)
            cpt_home_te2.save()
        if cpt_home_k:
            cpt_home_k.sim_scores = (numpy.round(rand_home_k, 2) * 1.5).tolist()
            cpt_home_k.median = numpy.median(cpt_home_k.sim_scores)
            cpt_home_k.s20 = numpy.percentile(cpt_home_k.sim_scores, 20)
            cpt_home_k.s75 = numpy.percentile(cpt_home_k.sim_scores, 75)
            cpt_home_k.s90 = numpy.percentile(cpt_home_k.sim_scores, 90)
            cpt_home_k.save()

        if cpt_home_dst:
            cpt_home_dst.sim_scores = (numpy.round(rand_home_dst, 2) * 1.5).tolist()
            cpt_home_dst.median = numpy.median(cpt_home_dst.sim_scores)
            cpt_home_dst.s20 = numpy.percentile(cpt_home_dst.sim_scores, 20)
            cpt_home_dst.s75 = numpy.percentile(cpt_home_dst.sim_scores, 75)
            cpt_home_dst.s90 = numpy.percentile(cpt_home_dst.sim_scores, 90)
            cpt_home_dst.save()

        if cpt_away_qb:
            cpt_away_qb.sim_scores = (numpy.round(rand_away_qb, 2) * 1.5).tolist()
            cpt_away_qb.median = numpy.median(cpt_away_qb.sim_scores)
            cpt_away_qb.s20 = numpy.percentile(cpt_away_qb.sim_scores, 20)
            cpt_away_qb.s75 = numpy.percentile(cpt_away_qb.sim_scores, 75)
            cpt_away_qb.s90 = numpy.percentile(cpt_away_qb.sim_scores, 90)
            cpt_away_qb.save()
        if cpt_away_rb1:
            cpt_away_rb1.sim_scores = (numpy.round(rand_away_rb1, 2) * 1.5).tolist()
            cpt_away_rb1.median = numpy.median(cpt_away_rb1.sim_scores)
            cpt_away_rb1.s20 = numpy.percentile(cpt_away_rb1.sim_scores, 20)
            cpt_away_rb1.s75 = numpy.percentile(cpt_away_rb1.sim_scores, 75)
            cpt_away_rb1.s90 = numpy.percentile(cpt_away_rb1.sim_scores, 90)
            cpt_away_rb1.save()
        if cpt_away_rb2:
            cpt_away_rb2.sim_scores = (numpy.round(rand_away_rb2, 2) * 1.5).tolist()
            cpt_away_rb2.median = numpy.median(cpt_away_rb2.sim_scores)
            cpt_away_rb2.s20 = numpy.percentile(cpt_away_rb2.sim_scores, 20)
            cpt_away_rb2.s75 = numpy.percentile(cpt_away_rb2.sim_scores, 75)
            cpt_away_rb2.s90 = numpy.percentile(cpt_away_rb2.sim_scores, 90)
            cpt_away_rb2.save()
        if cpt_away_rb3:
            cpt_away_rb3.sim_scores = (numpy.round(rand_away_rb3, 2) * 1.5).tolist()
            cpt_away_rb3.median = numpy.median(cpt_away_rb3.sim_scores)
            cpt_away_rb3.s20 = numpy.percentile(cpt_away_rb3.sim_scores, 20)
            cpt_away_rb3.s75 = numpy.percentile(cpt_away_rb3.sim_scores, 75)
            cpt_away_rb3.s90 = numpy.percentile(cpt_away_rb3.sim_scores, 90)
            cpt_away_rb3.save()
        if cpt_away_wr1:
            cpt_away_wr1.sim_scores = (numpy.round(rand_away_wr1, 2) * 1.5).tolist()
            cpt_away_wr1.median = numpy.median(cpt_away_wr1.sim_scores)
            cpt_away_wr1.s20 = numpy.percentile(cpt_away_wr1.sim_scores, 20)
            cpt_away_wr1.s75 = numpy.percentile(cpt_away_wr1.sim_scores, 75)
            cpt_away_wr1.s90 = numpy.percentile(cpt_away_wr1.sim_scores, 90)
            cpt_away_wr1.save()
        if cpt_away_wr2:
            cpt_away_wr2.sim_scores = (numpy.round(rand_away_wr2, 2) * 1.5).tolist()
            cpt_away_wr2.median = numpy.median(cpt_away_wr2.sim_scores)
            cpt_away_wr2.s20 = numpy.percentile(cpt_away_wr2.sim_scores, 20)
            cpt_away_wr2.s75 = numpy.percentile(cpt_away_wr2.sim_scores, 75)
            cpt_away_wr2.s90 = numpy.percentile(cpt_away_wr2.sim_scores, 90)
            cpt_away_wr2.save()
        if cpt_away_wr3:
            cpt_away_wr3.sim_scores = (numpy.round(rand_away_wr3, 2) * 1.5).tolist()
            cpt_away_wr3.median = numpy.median(cpt_away_wr3.sim_scores)
            cpt_away_wr3.s20 = numpy.percentile(cpt_away_wr3.sim_scores, 20)
            cpt_away_wr3.s75 = numpy.percentile(cpt_away_wr3.sim_scores, 75)
            cpt_away_wr3.s90 = numpy.percentile(cpt_away_wr3.sim_scores, 90)
            cpt_away_wr3.save()
        if cpt_away_wr4:
            cpt_away_wr4.sim_scores = (numpy.round(rand_away_wr4, 2) * 1.5).tolist()
            cpt_away_wr4.median = numpy.median(cpt_away_wr4.sim_scores)
            cpt_away_wr4.s20 = numpy.percentile(cpt_away_wr4.sim_scores, 20)
            cpt_away_wr4.s75 = numpy.percentile(cpt_away_wr4.sim_scores, 75)
            cpt_away_wr4.s90 = numpy.percentile(cpt_away_wr4.sim_scores, 90)
            cpt_away_wr4.save()
        if cpt_away_wr5:
            cpt_away_wr5.sim_scores = (numpy.round(rand_away_wr5, 2) * 1.5).tolist()
            cpt_away_wr5.median = numpy.median(cpt_away_wr5.sim_scores)
            cpt_away_wr5.s20 = numpy.percentile(cpt_away_wr5.sim_scores, 20)
            cpt_away_wr5.s75 = numpy.percentile(cpt_away_wr5.sim_scores, 75)
            cpt_away_wr5.s90 = numpy.percentile(cpt_away_wr5.sim_scores, 90)
            cpt_away_wr5.save()
        if cpt_away_te1:
            cpt_away_te1.sim_scores = (numpy.round(rand_away_te1, 2) * 1.5).tolist()
            cpt_away_te1.median = numpy.median(cpt_away_te1.sim_scores)
            cpt_away_te1.s20 = numpy.percentile(cpt_away_te1.sim_scores, 20)
            cpt_away_te1.s75 = numpy.percentile(cpt_away_te1.sim_scores, 75)
            cpt_away_te1.s90 = numpy.percentile(cpt_away_te1.sim_scores, 90)
            cpt_away_te1.save()
        if cpt_away_te2:
            cpt_away_te2.sim_scores = (numpy.round(rand_away_te2, 2) * 1.5).tolist()
            cpt_away_te2.median = numpy.median(cpt_away_te2.sim_scores)
            cpt_away_te2.s20 = numpy.percentile(cpt_away_te2.sim_scores, 20)
            cpt_away_te2.s75 = numpy.percentile(cpt_away_te2.sim_scores, 75)
            cpt_away_te2.s90 = numpy.percentile(cpt_away_te2.sim_scores, 90)
            cpt_away_te2.save()
        if cpt_away_k:
            cpt_away_k.sim_scores = (numpy.round(rand_away_k, 2) * 1.5).tolist()
            cpt_away_k.median = numpy.median(cpt_away_k.sim_scores)
            cpt_away_k.s20 = numpy.percentile(cpt_away_k.sim_scores, 20)
            cpt_away_k.s75 = numpy.percentile(cpt_away_k.sim_scores, 75)
            cpt_away_k.s90 = numpy.percentile(cpt_away_k.sim_scores, 90)
            cpt_away_k.save()
        if cpt_away_dst:
            cpt_away_dst.sim_scores = (numpy.round(rand_away_dst, 2) * 1.5).tolist()
            cpt_away_dst.median = numpy.median(cpt_away_dst.sim_scores)
            cpt_away_dst.s20 = numpy.percentile(cpt_away_dst.sim_scores, 20)
            cpt_away_dst.s75 = numpy.percentile(cpt_away_dst.sim_scores, 75)
            cpt_away_dst.s90 = numpy.percentile(cpt_away_dst.sim_scores, 90)
            cpt_away_dst.save()

        task.status = 'success'
        task.content = f'Simulation of {game} complete.'
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem simulating {game}: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def flatten_base_projections(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here

        slate = models.Slate.objects.get(id=slate_id)
        slate.flatten_base_projections()

        task.status = 'success'
        task.content = 'Projections flattened'
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem flattening projections: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def prepare_projections_for_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        chain(
            update_projections_for_build.s(build_id),
            find_in_play_for_build.s(build_id),
            find_stack_only_for_build.s(build_id),
            prepare_projections_for_build_complete.s(build_id, task.id)
        )()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem preparing projections: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def update_projections_for_build(build_id):
    build = models.SlateBuild.objects.get(id=build_id)
    build.update_projections(True)


@shared_task
def find_in_play_for_build(chained_results, build_id):
    build = models.SlateBuild.objects.get(id=build_id)
    group([
        find_in_play_for_projection.s(id) for id in list(build.projections.all().values_list('id', flat=True))
    ])()


@shared_task
def find_in_play_for_projection(projection_id):
    projection = models.BuildPlayerProjection.objects.get(id=projection_id)
    projection.find_in_play()


@shared_task
def find_stack_only_for_build(chained_results, build_id):
    build = models.SlateBuild.objects.get(id=build_id)
    build.find_stack_only()


@shared_task
def prepare_projections_for_build_complete(chained_results, build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)
        build.calc_projections_ready()

        qbs = build.num_in_play('QB')
        rbs = build.num_in_play('RB')
        wrs = build.num_in_play('WR')
        tes = build.num_in_play('TE')
        if build.slate.site == 'fanduel':
            dsts = build.num_in_play('D') 
        elif build.slate.site == 'yahoo':
            dsts = build.num_in_play('DEF') 
        else:
            dsts = build.num_in_play('DST')
        
        task.status = 'success'
        task.content = 'Projections ready for {}: {} qbs in play, {} rbs in play, {} wrs in play, {} tes in play, {} dsts in play'.format(str(build), qbs, rbs, wrs, tes, dsts)
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem preparing projections: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def prepare_construction_for_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)
        build.prepare_construction(task)
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem preparing groups and stacks: {e}'
            task.save()

        if build is not None:
            build.status = 'error'
            build.error_message = str(e)
            build.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def execute_build(build_id, user_id):
    build = models.SlateBuild.objects.get(pk=build_id)
    user = User.objects.get(pk=user_id)

    build.execute_build(user)


@shared_task
def optimize_for_ownership(projection_site, build_id, raw_projections, num_lineups, add_to_field=True):
    build = models.FindWinnerBuild.objects.get(id=build_id)
    r_proj = models.SlatePlayerRawProjection.objects.filter(id__in=raw_projections)
    player_sim_scores = {}

    # get the player outcomes
    for p in build.slate.get_projections().filter(slate_player__id__in=r_proj.values_list('slate_player__id', flat=True)):
        player_sim_scores[p.slate_player.player_id] = p.sim_scores
        if p.sim_scores is not None and len(p.sim_scores) > models.SIM_ITERATIONS:
            logger.info(f'{p} has {len(p.sim_scores)} outcomes.')

    if build.slate.is_showdown:
        lineups = optimize.optimize_for_showdown(
            build.slate.site,
            r_proj,
            num_lineups,
            0.8,
            'ownership_projection'
        )

        make_sd_lineups(build, lineups, player_sim_scores, add_to_field)
    else:
        lineups = optimize.optimize_for_classic(
            build.slate.site,
            r_proj,
            num_lineups,
            0.99,
            'ownership_projection',
            build.allow_two_tes
        )

        make_classic_lineups(build, lineups, player_sim_scores, projection_site, add_to_field)


@shared_task
def optimize_for_mean_projection(build_id, num_lineups, add_to_field=True):
    build = models.FindWinnerBuild.objects.get(id=build_id)
    projections = build.slate.get_projections().filter(projection__gte=0.5).exclude(sim_scores=None)
    player_sim_scores = {}

    # get the player outcomes
    for p in projections:
        player_sim_scores[p.slate_player.player_id] = p.sim_scores

    if build.slate.is_showdown:
        lineups = optimize.optimize_for_showdown(
            build.slate.site,
            projections,
            num_lineups,
            0.8,
            'projection'
        )

        make_sd_lineups(build, lineups, player_sim_scores, add_to_field)
    else:
        lineups = optimize.optimize_for_classic(
            build.slate.site,
            projections,
            num_lineups,
            0.99,
            'projection',
            build.allow_two_tes
        )

        make_classic_lineups(build, lineups, player_sim_scores, 'aggregate', add_to_field)


@shared_task
def optimize_for_locked_captain(build_id, num_lineups, locked_captain_id, add_to_field=True):
    build = models.FindWinnerBuild.objects.get(id=build_id)
    projections = build.slate.get_projections().filter(projection__gte=0.5).exclude(sim_scores=None)
    player_sim_scores = {}

    # get the player outcomes
    for p in projections:
        player_sim_scores[p.slate_player.player_id] = p.sim_scores
    
    lineups = optimize.optimize_for_showdown(
        build.slate.site,
        projections,
        num_lineups,
        0.8,
        'projection',
        locked_captain_id
    )

    make_sd_lineups(build, lineups, player_sim_scores, add_to_field)


@shared_task
def execute_h2h_workflow(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        
        from . import filters

        # Task implementation goes here
        build = models.FindWinnerBuild.objects.get(id=build_id)

        if build.field_lineup_creation_strategy == 'optimize_by_projection':
            build.matchups.all().delete()
            build.field_lineups_to_beat.all().delete()
            build.winning_lineups.all().delete()
            build.sd_matchups.all().delete()
            build.field_sd_lineups_to_beat.all().delete()
            build.winning_sd_lineups.all().delete()

            chain([
                optimize_for_mean_projection.si(
                    build.id,
                    100
                ), 
                start_h2h_comparison.si(
                    build.id, 
                    task.id
                )
            ])()
        elif build.field_lineup_creation_strategy == 'optimize_by_ownership':
            build.matchups.all().delete()
            build.field_lineups_to_beat.all().delete()
            build.winning_lineups.all().delete()
            build.sd_matchups.all().delete()
            build.field_sd_lineups_to_beat.all().delete()
            build.winning_sd_lineups.all().delete()

            chord([
                optimize_for_ownership.si(
                    s.projection_site,
                    build.id,
                    list(models.SlatePlayerRawProjection.objects.filter(
                        projection_site=s.projection_site,
                        slate_player__slate=build.slate,
                        ownership_projection__gte=0.05
                    ).values_list('id', flat=True)), s.field_lineup_count
                ) for s in build.slate.projection_imports.filter(field_lineup_count__gt=0)
            ], start_h2h_comparison.si(build.id, task.id))()
        else:
            build.matchups.all().delete()
            build.winning_lineups.all().delete()
            build.sd_matchups.all().delete()
            build.winning_sd_lineups.all().delete()
            
            start_h2h_comparison.delay(build.id, task.id)
            
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem running h2h workflow: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


def make_classic_lineups(build, lineups, player_sim_scores, projection_site, add_to_field=True):
    for (index, lineup) in enumerate(lineups):
        qb = lineup.players[0].id
        rb1 = lineup.players[1].id
        rb2 = lineup.players[2].id
        wr1 = lineup.players[3].id
        wr2 = lineup.players[4].id
        wr3 = lineup.players[5].id
        te = lineup.players[6].id
        flex = lineup.players[7].id
        dst = lineup.players[8].id

        slate_lineup = build.slate.possible_lineups.filter(
            qb__player_id=qb,
            rb1__player_id__in=[rb1, rb2, flex],
            rb2__player_id__in=[rb1, rb2, flex],
            wr1__player_id__in=[wr1, wr2, wr3, flex],
            wr2__player_id__in=[wr1, wr2, wr3, flex],
            wr3__player_id__in=[wr1, wr2, wr3, flex],
            te__player_id__in=[te, flex],
            flex__player_id__in=[rb1, rb2, wr1, wr2, wr3, te, flex],
            dst__player_id=dst
        )
        
        if slate_lineup.count() == 0:
            slate_lineup = models.SlateLineup.objects.create(
                slate=build.slate,
                qb=models.SlatePlayer.objects.get(slate=build.slate, player_id=qb),
                rb1=models.SlatePlayer.objects.get(slate=build.slate, player_id=rb1),
                rb2=models.SlatePlayer.objects.get(slate=build.slate, player_id=rb2),
                wr1=models.SlatePlayer.objects.get(slate=build.slate, player_id=wr1),
                wr2=models.SlatePlayer.objects.get(slate=build.slate, player_id=wr2),
                wr3=models.SlatePlayer.objects.get(slate=build.slate, player_id=wr3),
                te=models.SlatePlayer.objects.get(slate=build.slate, player_id=te),
                flex=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex),
                dst=models.SlatePlayer.objects.get(slate=build.slate, player_id=dst)
            )
            slate_lineup.simulate()

            # score the lineup
            sim_scores = numpy.array(player_sim_scores[qb], dtype=numpy.float64) + numpy.array(player_sim_scores[rb1], dtype=numpy.float64) + numpy.array(player_sim_scores[rb2], dtype=numpy.float64) + numpy.array(player_sim_scores[wr1], dtype=numpy.float64) + numpy.array(player_sim_scores[wr2], dtype=numpy.float64) + numpy.array(player_sim_scores[wr3], dtype=numpy.float64) + numpy.array(player_sim_scores[te], dtype=numpy.float64) + numpy.array(player_sim_scores[flex], dtype=numpy.float64) + numpy.array(player_sim_scores[dst], dtype=numpy.float64)
            
            slate_lineup.sim_scores = sim_scores.tolist()
            slate_lineup.save()

            slate_lineup = [slate_lineup]

            if add_to_field:
                l = models.FieldLineupToBeat.objects.create(
                    build=build,
                    opponent_handle=f'{projection_site}_{index}',
                    slate_lineup=slate_lineup[0]
                )

                l.median = numpy.median(sim_scores)
                l.s75 = numpy.percentile(sim_scores, 75)
                l.s90 = numpy.percentile(sim_scores, 90)
                l.save()


def make_sd_lineups(build, lineups, player_sim_scores, add_to_field=True):
    for (index, lineup) in enumerate(lineups):
        cpt = lineup.players[0].id
        flex1 = lineup.players[1].id
        flex2 = lineup.players[2].id
        flex3 = lineup.players[3].id
        flex4 = lineup.players[4].id
        flex5 = lineup.players[5].id if len(lineup.players) > 5 else None

        # score the lineup
        sim_scores = numpy.array(player_sim_scores[cpt], dtype=numpy.float64) + numpy.array(player_sim_scores[flex1], dtype=numpy.float64) + numpy.array(player_sim_scores[flex2], dtype=numpy.float64) + numpy.array(player_sim_scores[flex3], dtype=numpy.float64) + numpy.array(player_sim_scores[flex4], dtype=numpy.float64)
        if flex5 is not None:
            sim_scores += numpy.array(player_sim_scores[flex5], dtype=numpy.float64)

            slate_lineup = build.slate.possible_sd_lineups.filter(
                cpt__player_id=cpt,
                flex1__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                flex2__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                flex3__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                flex4__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                flex5__player_id__in=[flex1, flex2, flex3, flex4, flex5]
            )
        else:
            slate_lineup = build.slate.possible_sd_lineups.filter(
                cpt__player_id=cpt,
                flex1__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                flex2__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                flex3__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                flex4__player_id__in=[flex1, flex2, flex3, flex4, flex5]
            )
        
        if slate_lineup.count() == 0:
            slate_lineup = models.SlateSDLineup.objects.create(
                slate=build.slate,
                cpt=models.SlatePlayer.objects.get(slate=build.slate, player_id=cpt),
                flex1=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex1),
                flex2=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex2),
                flex3=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex3),
                flex4=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex4),
                flex5=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex5) if flex5 is not None else None
            )
            slate_lineup.simulate()
            
            slate_lineup.sim_scores = sim_scores.tolist()
            slate_lineup.save()

            slate_lineup = [slate_lineup]

        if add_to_field:
            l = models.FieldSDLineupToBeat.objects.create(
                build=build,
                opponent_handle=f'{index}',
                slate_lineup=slate_lineup[0]
            )

            l.median = numpy.median(sim_scores)
            l.s75 = numpy.percentile(sim_scores, 75)
            l.s90 = numpy.percentile(sim_scores, 90)
            l.save()


@shared_task
def start_h2h_comparison(build_id, task_id):
    task = BackgroundTask.objects.get(id=task_id)
    build = models.FindWinnerBuild.objects.get(id=build_id)

    start = time.time()
    if build.slate.is_showdown:
        field_lineups = build.field_sd_lineups_to_beat.all().values_list('slate_lineup_id', flat=True)
        possible_lineups = models.SlateSDLineup.objects.filter(id__in=field_lineups).order_by('id').values_list('id', flat=True)
    else:
        field_lineups = build.field_lineups_to_beat.all().values_list('slate_lineup_id', flat=True)
        possible_lineups = models.SlateLineup.objects.filter(id__in=field_lineups).order_by('id').values_list('id', flat=True)
    logger.info(f'Filtered slate lineups took {time.time() - start}s. There are {len(possible_lineups)} lineups.')

    chunk_size = 10
    chord([
        compare_lineups_h2h.si(possible_lineups[i:i+chunk_size], build.id) for i in range(0, len(possible_lineups), chunk_size)
    ], complete_h2h_workflow.si(task.id))()


@shared_task
def compare_lineups_h2h(lineup_ids, build_id):
    build = models.FindWinnerBuild.objects.get(id=build_id)

    start = time.time()
    if build.slate.is_showdown:
        slate_lineups = models.SlateSDLineup.objects.filter(id__in=lineup_ids).order_by('id')
        field_lineups = build.field_sd_lineups_to_beat.all().order_by('id')
    else:
        slate_lineups = models.SlateLineup.objects.filter(id__in=lineup_ids).order_by('id')
        field_lineups = build.field_lineups_to_beat.all().order_by('id')
    logger.info(f'Getting lineups took {time.time() - start}s')
    
    for l in slate_lineups:
        if l.sim_scores is None:
            logger.info(f'{l.id} - SIM SCORES ARE NULL')
    
    start = time.time()
    df_slate_lineups = pandas.DataFrame(slate_lineups.values_list('sim_scores', flat=True), index=list(slate_lineups.values_list('id', flat=True)), dtype=numpy.float16)
    logger.info(f'  Initial dataframe took {time.time() - start}s')
    logger.info(df_slate_lineups)

    # start = time.time()
    # field_lineups = build.field_lineups_to_beat.all().order_by('id')
    # logger.info(f'Getting field lineups took {time.time() - start}s.')

    start = time.time()
    df_field_lineups = pandas.DataFrame(field_lineups.values_list('slate_lineup__sim_scores', flat=True), index=list(field_lineups.values_list('id', flat=True)), dtype=numpy.float16)
    logger.info(f'  Initial dataframe took {time.time() - start}s')
    logger.info(df_field_lineups)

    start = time.time()
    matchups  = list(itertools.product(slate_lineups.values_list('id', flat=True), field_lineups.values_list('id', flat=True)))
    df_matchups = pandas.DataFrame(matchups, columns=['slate_lineup_id', 'field_lineup_id'])
    df_matchups['win_rate'] = df_matchups.apply(lambda x: numpy.count_nonzero((numpy.array(df_slate_lineups.loc[x['slate_lineup_id']]) - numpy.array(df_field_lineups.loc[x['field_lineup_id']])) > 0.0) / models.SIM_ITERATIONS, axis=1)
    logger.info(df_matchups)
    # df_matchups = df_matchups[(df_matchups.win_rate > 0.55)]
    df_matchups['build_id'] = build.id
    logger.info(f'Matchups took {time.time() - start}s. There are {df_matchups.size} matchups.')

    start = time.time()
    if build.slate.is_showdown:
        df_matchups.to_sql('nfl_lineupsdmatchup', engine, if_exists='append', index=False, chunksize=1000)
        logger.info(f'Write matchups to db took {time.time() - start}s')

        start = time.time()
        build_lineup_ids = df_matchups.slate_lineup_id.unique()
        for bl in build_lineup_ids:
            try:
                sim_scores = df_slate_lineups.loc[int(bl)].to_list()
                opponents = list(build.field_sd_lineups_to_beat.all().values_list('opponent_handle', flat=True))
                opponents = list(set(opponents))
                win_rates = list(build.sd_matchups.filter(slate_lineup_id=bl).values_list('win_rate', flat=True))
                rake_free_win_rates = list(filter(lambda wr: wr >= 0.55, win_rates))

                logger.info(rake_free_win_rates)
                models.WinningSDLineup.objects.create(
                    build=build,
                    slate_lineup_id=bl,
                    median=numpy.median(sim_scores),
                    s75=numpy.percentile(sim_scores, 75),
                    s90=numpy.percentile(sim_scores, 90),
                    win_rate=numpy.median(rake_free_win_rates) if len(rake_free_win_rates) > 0 else 0.0,
                    win_count=len(rake_free_win_rates) if len(rake_free_win_rates) > 0 else 0.0,
                    rating=numpy.median(rake_free_win_rates) * (2 * len(rake_free_win_rates)) if len(rake_free_win_rates) > 0 else 0.0
                )
            except KeyError:
                pass
        logger.info(f'Adding build lineups took {time.time() - start}s')
    else:
        df_matchups.to_sql('nfl_lineupmatchup', engine, if_exists='append', index=False, chunksize=1000)
        logger.info(f'Write matchups to db took {time.time() - start}s')

        start = time.time()
        build_lineup_ids = df_matchups.slate_lineup_id.unique()
        for bl in build_lineup_ids:
            try:
                sim_scores = df_slate_lineups.loc[int(bl)].to_list()
                opponents = list(build.field_lineups_to_beat.all().values_list('opponent_handle', flat=True))
                opponents = list(set(opponents))
                win_rates = list(build.matchups.filter(slate_lineup_id=bl).values_list('win_rate', flat=True))
                rake_free_win_rates = list(filter(lambda wr: wr >= 0.55, win_rates))

                logger.info(rake_free_win_rates)
                models.WinningLineup.objects.create(
                    build=build,
                    slate_lineup_id=bl,
                    median=numpy.median(sim_scores),
                    s75=numpy.percentile(sim_scores, 75),
                    s90=numpy.percentile(sim_scores, 90),
                    win_rate=numpy.median(rake_free_win_rates) if len(rake_free_win_rates) > 0 else 0.0,
                    win_count=len(rake_free_win_rates) if len(rake_free_win_rates) > 0 else 0.0,
                    rating=numpy.median(rake_free_win_rates) * (2 * len(rake_free_win_rates)) if len(rake_free_win_rates) > 0 else 0.0
                )
            except KeyError:
                pass
        logger.info(f'Adding build lineups took {time.time() - start}s')


@shared_task
def complete_h2h_workflow(task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        task.status = 'success'
        task.content = f'H2H workflow complete'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem running cash workflow: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def execute_se_workflow(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        
        from . import filters

        # Task implementation goes here
        build = models.FindWinnerBuild.objects.get(id=build_id)

        if build.field_lineup_creation_strategy == 'optimize_by_projection':
            build.matchups.all().delete()
            build.field_lineups_to_beat.all().delete()
            build.winning_lineups.all().delete()
            build.sd_matchups.all().delete()
            build.field_sd_lineups_to_beat.all().delete()
            build.winning_sd_lineups.all().delete()

            chain([
                optimize_for_mean_projection.si(
                    build.id,
                    100
                ), 
                start_non_h2h_comparison.si(
                    build.id, 
                    task.id
                )
            ])()
        elif build.field_lineup_creation_strategy == 'optimize_by_ownership':
            build.matchups.all().delete()
            build.field_lineups_to_beat.all().delete()
            build.winning_lineups.all().delete()
            build.sd_matchups.all().delete()
            build.field_sd_lineups_to_beat.all().delete()
            build.winning_sd_lineups.all().delete()

            chord([
                optimize_for_ownership.si(
                    s.projection_site,
                    build.id,
                    list(models.SlatePlayerRawProjection.objects.filter(
                        projection_site=s.projection_site,
                        slate_player__slate=build.slate,
                        ownership_projection__gte=0.05
                    ).values_list('id', flat=True)), s.field_lineup_count
                ) for s in build.slate.projection_imports.filter(field_lineup_count__gt=0)
            ], start_non_h2h_comparison.si(build.id, task.id))()
        else:
            if build.slate.is_showdown:
                build.sd_matchups.all().delete()
                build.winning_sd_lineups.all().delete()

                chord([
                    optimize_for_locked_captain.si(
                        build.id,
                        20,
                        p.slate_player.player_id,
                        False
                    ) for p in build.slate.get_projections().filter(
                        slate_player__roster_position__in=['CPT', 'MVP'], 
                        projection__gte=3.0
                    )
                ], start_non_h2h_comparison.si(build.id, task.id))()
            else:
                build.field_lineups_to_beat.all().delete()
                build.winning_lineups.all().delete()
                build.field_sd_lineups_to_beat.all().delete()
                build.winning_sd_lineups.all().delete()

                start_non_h2h_comparison.delay(build.id, task.id)
            
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem running SE workflow: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def start_non_h2h_comparison(build_id, task_id):
    task = BackgroundTask.objects.get(id=task_id)
    build = models.FindWinnerBuild.objects.get(id=build_id)

    start = time.time()
    if build.slate.is_showdown:
        # field_lineups = build.field_sd_lineups_to_beat.all().values_list('slate_lineup_id', flat=True)
        possible_lineups = models.SlateSDLineup.objects.filter(slate=build.slate).order_by('id').values_list('id', flat=True)
    else:
        # field_lineups = build.field_lineups_to_beat.all().values_list('slate_lineup_id', flat=True)
        possible_lineups = models.SlateLineup.objects.filter(slate=build.slate).order_by('id').values_list('id', flat=True)
    logger.info(f'Filtered slate lineups took {time.time() - start}s. There are {len(possible_lineups)} lineups.')

    chunk_size = 1
    chord([
        compare_lineups_se.si(possible_lineups[i:i+chunk_size], build.id) for i in range(0, len(possible_lineups), chunk_size)
    ], complete_se_workflow.si(task.id))()


@shared_task
def compare_lineups_se(lineup_ids, build_id):
    build = models.FindWinnerBuild.objects.get(id=build_id)

    start = time.time()
    if build.slate.is_showdown:
        slate_lineups = models.SlateSDLineup.objects.filter(id__in=lineup_ids).order_by('id')
        field_lineups = build.field_sd_lineups_to_beat.all().order_by('id')
    else:
        slate_lineups = models.SlateLineup.objects.filter(id__in=lineup_ids).order_by('id')
        field_lineups = build.field_lineups_to_beat.all().order_by('id')
    logger.info(f'Getting slate lineups took {time.time() - start}s')
    
    for l in slate_lineups:
        if l.sim_scores is None:
            logger.info(f'{l.id} - SIM SCORES ARE NULL')
    
    start = time.time()
    df_slate_lineups = pandas.DataFrame(slate_lineups.values_list('sim_scores', flat=True), index=list(slate_lineups.values_list('id', flat=True)), dtype=numpy.float16)
    logger.info(f'  Initial slate lineups dataframe took {time.time() - start}s')
    logger.info(df_slate_lineups)

    start = time.time()
    df_field_lineups = pandas.DataFrame(field_lineups.values_list('slate_lineup__sim_scores', flat=True), index=list(field_lineups.values_list('id', flat=True)), dtype=numpy.float16)
    logger.info(f'  Initial field lineups dataframe took {time.time() - start}s')
    logger.info(df_field_lineups)

    start = time.time()
    df_matchups = pandas.concat([df_field_lineups, df_slate_lineups])
    df_matchups = df_matchups.rank(method="min", ascending=False).iloc[field_lineups.count():field_lineups.count()+slate_lineups.count()] <= df_matchups.rank(method="min", ascending=False).iloc[0:field_lineups.count()].min(axis=0)
    df_matchups['win_count'] = df_matchups.apply(lambda x: numpy.count_nonzero(x), axis=1)
    df_matchups['win_rate'] = df_matchups['win_count'] / models.SIM_ITERATIONS
    # df_matchups = df_matchups[(df_matchups.win_rate >= 0.20)]

    df_lineups = df_matchups.filter(['win_rate'], axis=1)
    if not df_lineups.empty:
        df_lineups['slate_lineup_id'] = df_lineups.index
        try:
            df_lineups['median'] = df_lineups.apply(lambda x: numpy.median(numpy.array(df_slate_lineups.loc[x['slate_lineup_id']])), axis=1)
            df_lineups['s75'] = df_lineups.apply(lambda x: numpy.percentile(numpy.array(df_slate_lineups.loc[x['slate_lineup_id']]), 75.0), axis=1)
            df_lineups['s90'] = df_lineups.apply(lambda x: numpy.percentile(numpy.array(df_slate_lineups.loc[x['slate_lineup_id']]), 90.0), axis=1)
        except:
            df_lineups['median'] = None
            df_lineups['s75'] = None
            df_lineups['s90'] = None
            logger.info(df_lineups)
        df_lineups['build_id'] = build.id
        df_lineups['win_count'] = 0
        df_lineups['rating'] = 0

    logger.info(f'Matchups took {time.time() - start}s.')

    start = time.time()
    if build.slate.is_showdown:
        df_lineups.to_sql('nfl_winningsdlineup', engine, if_exists='append', index=False, chunksize=1000)
    else:
        df_lineups.to_sql('nfl_winninglineup', engine, if_exists='append', index=False, chunksize=1000)
    logger.info(f'Adding build lineups took {time.time() - start}s. There are {len(df_lineups.index)} lineups.')


@shared_task
def complete_se_workflow(task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        task.status = 'success'
        task.content = f'SE workflow complete'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem running se workflow: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def export_build_lineups(build_id, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        build = models.FindWinnerBuild.objects.get(id=build_id)

        if build.slate.is_showdown:
            if build.slate.site != 'fanduel':
                winning_lineups = pandas.DataFrame.from_records(build.winning_sd_lineups.all().order_by('-rating').values(
                    'slate_lineup_id', 
                    'slate_lineup__cpt__csv_name', 
                    'slate_lineup__flex1__csv_name', 
                    'slate_lineup__flex2__csv_name', 
                    'slate_lineup__flex3__csv_name', 
                    'slate_lineup__flex4__csv_name', 
                    'slate_lineup__flex5__csv_name', 
                    'win_rate',
                    'win_count',
                    'rating',
                    'median', 
                    's75', 
                    's90'
                ))
            else:
                winning_lineups = pandas.DataFrame.from_records(build.winning_sd_lineups.all().order_by('-rating').values(
                    'slate_lineup_id', 
                    'slate_lineup__cpt__csv_name', 
                    'slate_lineup__flex1__csv_name', 
                    'slate_lineup__flex2__csv_name', 
                    'slate_lineup__flex3__csv_name', 
                    'slate_lineup__flex4__csv_name', 
                    'win_rate',
                    'win_count',
                    'rating',
                    'median', 
                    's75', 
                    's90'
                ))
        else:
            winning_lineups = pandas.DataFrame.from_records(build.winning_lineups.all().order_by('-rating').values(
                'slate_lineup_id', 
                'slate_lineup__qb__csv_name', 
                'slate_lineup__rb1__csv_name', 
                'slate_lineup__rb2__csv_name', 
                'slate_lineup__wr1__csv_name', 
                'slate_lineup__wr2__csv_name', 
                'slate_lineup__wr3__csv_name', 
                'slate_lineup__te__csv_name', 
                'slate_lineup__flex__csv_name', 
                'slate_lineup__dst__csv_name', 
                'slate_lineup__total_salary', 
                'win_rate',
                'win_count',
                'rating',
                'median', 
                's75', 
                's90'
            ))

        with pandas.ExcelWriter(result_path) as writer:
            winning_lineups.to_excel(writer, sheet_name='Lineups')

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


@shared_task
def build_lineups_for_stack(stack_id, lineup_number, num_qb_stacks):
    stack = models.SlateBuildStack.objects.get(id=stack_id)
    stack.build_lineups_for_stack(lineup_number, num_qb_stacks)

    return list(stack.lineups.all().values_list('id', flat=True))


@shared_task
def calculate_actuals_for_stacks(stack_ids):
    task = None

    try:
        stacks = models.SlateBuildStack.objects.filter(id__in=stack_ids)
        for stack in (stacks):
            stack.calc_actual_score()

    except Exception as e:
        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def calculate_actuals_for_lineups(lineup_ids):
    task = None

    try:
        lineups = models.SlateBuildLineup.objects.filter(id__in=lineup_ids)
        for lineup in (lineups):
            lineup.calc_actual_score()
    except Exception as e:
        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def calculate_actuals_for_build(chained_results, build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here

        build = models.SlateBuild.objects.get(id=build_id)
        contests = build.slate.contests.filter(use_for_actuals=True)
        if contests.count() > 0:
            contest = contests[0]

            lineups = build.lineups.all().order_by('-actual')
            metrics = lineups.aggregate(
                total_cashes=Count('pk', filter=Q(actual__gte=contest.mincash_score)),
                total_one_pct=Count('pk', filter=Q(actual__gte=contest.one_pct_score)),
                total_half_pct=Count('pk', filter=Q(actual__gte=contest.half_pct_score))
            )

            build.top_score = lineups[0].actual
            build.total_cashes = metrics.get('total_cashes')
            build.total_one_pct = metrics.get('total_one_pct')
            build.total_half_pct = metrics.get('total_half_pct')
            build.great_build = (lineups[0].actual >= contest.great_score)
            build.binked = (lineups[0].actual >= contest.winning_score)
            build.save()

            task.status = 'success'
            task.content = 'Actual build metrics calculated.'
            task.save()
        else:
            task.status = 'error'
            task.content = 'Actual build metrics calculated, but no contest data was available so only lineup actuals calculated.'
            task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating actuals: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def initialize_backtest(backtest_id):
    try:
        backtest = models.Backtest.objects.get(id=backtest_id)
        backtest.reset()
    except Exception as exc:
        traceback.print_exc()

        backtest.status = 'error'
        backtest.error_message = str(exc)
        backtest.save()


@shared_task
def prepare_projections_for_backtest(backtest_id):
    try:
        backtest = models.Backtest.objects.get(id=backtest_id)
        backtest.prepare_projections()
    except Exception as exc:
        traceback.print_exc()

        backtest.status = 'error'
        backtest.error_message = str(exc)
        backtest.save()


@shared_task
def prepare_construction_for_backtest(backtest_id):
    try:
        backtest = models.Backtest.objects.get(id=backtest_id)
        backtest.prepare_construction()
    except Exception as exc:
        traceback.print_exc()

        backtest.status = 'error'
        backtest.error_message = str(exc)
        backtest.save()


@shared_task
def analyze_backtest(backtest_id):
    try:
        backtest = models.Backtest.objects.get(id=backtest_id)
        backtest.analyze()
    except Exception as exc:
        traceback.print_exc()


@shared_task
def prepare_projections(build_id):
    try:
        build = models.SlateBuild.objects.get(id=build_id)
        build.prepare_projections()
    except Exception as exc:
        traceback.print_exc()

        build.status = 'error'
        build.error_message = str(exc)
        build.save()


@shared_task
def prepare_construction(build_id):
    try:
        build = models.SlateBuild.objects.get(id=build_id)
        build.prepare_construction()
    except Exception as exc:
        traceback.print_exc()

        build.status = 'error'
        build.error_message = str(exc)
        build.save()


@shared_task
def flatten_exposure(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here

        build = models.SlateBuild.objects.get(id=build_id)
        build.flatten_exposure()

        task.status = 'success'
        task.content = 'Exposures flattened'
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem flattening exposure: {e}'
            task.save()

        if build is not None:
            build.status = 'error'
            build.error_message = str(e)
            build.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def create_groups_for_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        build = models.SlateBuild.objects.get(id=build_id)

        # Make groups for lineup construction rules
        if build.lineup_construction is not None:
            for (index, group_rule) in enumerate(build.lineup_construction.group_rules.all()):
                group = models.SlateBuildGroup.objects.create(
                    build=build,
                    name='{}: Group {}'.format(build.slate.name, index+1),
                    min_from_group=group_rule.at_least,
                    max_from_group=group_rule.at_most
                )

                # add players to group
                for projection in build.projections.filter(in_play=True, slate_player__site_pos__in=group_rule.allowed_positions):
                    if group_rule.meets_threshold(projection):
                        models.SlateBuildGroupPlayer.objects.create(
                            group=group,
                            slate_player=projection.slate_player
                        )

                group.save()

        # Make anti-ministack groups
        games = build.slate.games.all()
        for game in games:
            # find anti-ministack players
            anti_mini_players = build.projections.filter(
                slate_player__slate_game=game,
                disallow_ministack=True
            )

            if anti_mini_players.count() > 0:
                # find stacked players
                stacked_players = build.projections.filter(
                    Q(Q(qb_stack_only=True) | Q(opp_qb_stack_only=True)),
                    slate_player__slate_game=game,
                    disallow_ministack=False
                )

                # make groups for each stacked player with each anti-ministack player
                for stacked_player in stacked_players:
                    group = models.SlateBuildGroup.objects.create(
                        build=build,
                        name=f'AM1 {game.game.home_team}/{game.game.away_team} - {stacked_player.name}',
                        min_from_group=0,
                        max_from_group=1
                    )

                    # add stacked player to group
                    models.SlateBuildGroupPlayer.objects.create(
                        group=group,
                        slate_player=stacked_player.slate_player
                    )

                    # add anti-ministack players
                    for anti_mini_player in anti_mini_players:
                        models.SlateBuildGroupPlayer.objects.create(
                            group=group,
                            slate_player=anti_mini_player.slate_player
                        )

                # handle players who are not both anti-mini and anti-leverage (see below)
                if stacked_players.count() == 0:
                    anti_mini_2 = anti_mini_players.filter(use_as_antileverage=False)

                    if anti_mini_2.count() > 0:
                        group = models.SlateBuildGroup.objects.create(
                            build=build,
                            name=f'AM1 {game.game.home_team}/{game.game.away_team} - Anti-Mini Global',
                            min_from_group=0,
                            max_from_group=1
                        )

                        # add anti-ministack players
                        for anti_mini_player in anti_mini_players:
                            models.SlateBuildGroupPlayer.objects.create(
                                group=group,
                                slate_player=anti_mini_player.slate_player
                            )

        # Make anti-leverage group
        anti_lev_players = build.projections.filter(
            use_as_antileverage=True
        )

        group = models.SlateBuildGroup.objects.create(
            build=build,
            name='AM1 - Bobo + Lev',
            min_from_group=0,
            max_from_group=1
        )

        for anti_lev_player in anti_lev_players:
            models.SlateBuildGroupPlayer.objects.create(
                group=group,
                slate_player=anti_lev_player.slate_player
            )


        task.status = 'success'
        task.content = f'{build.groups.all().count()} groups created.'
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a creating groups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))
   

@shared_task
def create_stacks_for_qb(build_id, qb_id, total_qb_projection):
    build = models.SlateBuild.objects.get(pk=build_id)
    qb = models.BuildPlayerProjection.objects.get(pk=qb_id)

    qb_lineup_count = round(float(qb.projection)/float(total_qb_projection) * float(build.total_lineups))

    print('Making stacks for {} {} lineups...'.format(qb_lineup_count, qb.name))
    stack_players = build.projections.filter(
        Q(Q(slate_player__site_pos__in=build.configuration.qb_stack_positions) | Q(slate_player__site_pos__in=build.configuration.opp_qb_stack_positions))
    ).filter(
        Q(Q(qb_stack_only=True, slate_player__team=qb.team) | Q(opp_qb_stack_only=True, slate_player__team=qb.get_opponent()))
    )

    # team_players includes all in-play players on same team as qb, including stack-only players
    team_players = stack_players.filter(slate_player__team=qb.team, slate_player__site_pos__in=build.configuration.qb_stack_positions).order_by('-projection')
    # opp_players includes all in-play players on opposing team, including stack-only players that are allowed in opponent stack
    opp_players = stack_players.filter(slate_player__slate_game=qb.game, slate_player__site_pos__in=build.configuration.opp_qb_stack_positions).exclude(slate_player__team=qb.team).order_by('-projection')

    am1_players = team_players.filter(
        stack_only=True
    )
    team_has_all_stack_only = (am1_players.count() == team_players.count())

    if build.configuration.game_stack_size == 3 or opp_players.count() == 0:
        # For each player, loop over opposing player to make a group for each possible stack combination
        count = 0
        for (index, player) in enumerate(team_players):
            for opp_player in opp_players:
                count += 1

                # add mini stacks if configured
                if build.configuration.use_super_stacks:
                    for game in build.slate.games.all():
                        if game == qb.game:
                            continue
                    
                        home_players = game.get_home_players()
                        away_players = game.get_away_players()

                        # First make all mini stacks with 2 home team players
                        for (idx, home_player_1) in enumerate(build.projections.filter(slate_player__in=home_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')):
                            for home_player_2 in build.projections.filter(slate_player__in=home_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).exclude(slate_player=home_player_1.slate_player).order_by('-projection', 'slate_player__site_pos'):
                                stack = models.SlateBuildStack.objects.create(
                                    build=build,
                                    game=qb.game,
                                    mini_game=game,
                                    build_order=count,
                                    qb=qb,
                                    player_1=player,
                                    opp_player=opp_player,
                                    mini_player_1=home_player_1,
                                    mini_player_2=home_player_2,
                                    salary=sum(p.slate_player.salary for p in [qb, player, opp_player, home_player_1, home_player_2]),
                                    projection=sum(p.projection for p in [qb, player, opp_player, home_player_1, home_player_2])
                                )

                                if build.stack_construction is not None:
                                    if build.stack_construction.passes_rule(stack):
                                        stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)
                                        stack.save()
                                    else:
                                        stack.delete()                                            

                        # Next make all mini stacks with 2 away team players
                        for (idx, away_player_1) in enumerate(build.projections.filter(slate_player__in=away_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')):
                            for away_player_2 in build.projections.filter(slate_player__in=away_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).exclude(slate_player=away_player_1.slate_player).order_by('-projection', 'slate_player__site_pos'):
                                stack = models.SlateBuildStack.objects.create(
                                    build=build,
                                    game=qb.game,
                                    mini_game=game,
                                    build_order=count,
                                    qb=qb,
                                    player_1=player,
                                    opp_player=opp_player,
                                    mini_player_1=away_player_1,
                                    mini_player_2=away_player_2,
                                    salary=sum(p.slate_player.salary for p in [qb, player, opp_player, away_player_1, away_player_2]),
                                    projection=sum(p.projection for p in [qb, player, opp_player, away_player_1, away_player_2])
                                )

                                if build.stack_construction is not None:
                                    if build.stack_construction.passes_rule(stack):
                                        stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)
                                        stack.save()
                                    else:
                                        stack.delete()                                            

                        # Finally make all mini stacks with players from both teams
                        for (idx, home_player) in enumerate(build.projections.filter(slate_player__in=home_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')):
                            for away_player in build.projections.filter(slate_player__in=away_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos'):
                                stack = models.SlateBuildStack.objects.create(
                                    build=build,
                                    game=qb.game,
                                    mini_game=game,
                                    build_order=count,
                                    qb=qb,
                                    player_1=player,
                                    opp_player=opp_player,
                                    mini_player_1=home_player,
                                    mini_player_2=away_player,
                                    salary=sum(p.slate_player.salary for p in [qb, player, opp_player, home_player, away_player]),
                                    projection=sum(p.projection for p in [qb, player, opp_player, home_player, away_player])
                                )

                                if build.stack_construction is not None:
                                    if build.stack_construction.passes_rule(stack):
                                        stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)
                                        stack.save()
                                    else:
                                        stack.delete()                                            
                else:
                    stack = models.SlateBuildStack.objects.create(
                        build=build,
                        game=qb.game,
                        build_order=count,
                        qb=qb,
                        player_1=player,
                        opp_player=opp_player,
                        salary=sum(p.slate_player.salary for p in [qb, player, opp_player]),
                        projection=sum(p.projection for p in [qb, player, opp_player])
                    )

                    if build.stack_construction is not None:
                        if build.stack_construction.passes_rule(stack):
                            stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)
                            stack.save()
                        else:
                            stack.delete()                                            

            for player2 in team_players[index+1:]:
                count += 1

                # add mini stacks if configured
                if build.configuration.use_super_stacks:
                    for game in build.slate.games.all():
                        if game == qb.game:
                            continue
                    
                        home_players = game.get_home_players()
                        away_players = game.get_away_players()

                        # First make all mini stacks with 2 home team players
                        for (idx, home_player_1) in enumerate(build.projections.filter(slate_player__in=home_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')):
                            for home_player_2 in build.projections.filter(slate_player__in=home_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).exclude(slate_player=home_player_1.slate_player).order_by('-projection', 'slate_player__site_pos'):
                                stack = models.SlateBuildStack.objects.create(
                                    build=build,
                                    game=qb.game,
                                    mini_game=game,
                                    build_order=count,
                                    qb=qb,
                                    player_1=player,
                                    player_2=player2,
                                    mini_player_1=home_player_1,
                                    mini_player_2=home_player_2,
                                    salary=sum(p.slate_player.salary for p in [qb, player, opp_player, home_player_1, home_player_2]),
                                    projection=sum(p.projection for p in [qb, player, opp_player, home_player_1, home_player_2])
                                )

                                if build.stack_construction is not None:
                                    if build.stack_construction.passes_rule(stack):
                                        stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)
                                        stack.save()
                                    else:
                                        stack.delete()                                            

                        # Next make all mini stacks with 2 away team players
                        for (idx, away_player_1) in enumerate(build.projections.filter(slate_player__in=away_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')):
                            for away_player_2 in build.projections.filter(slate_player__in=away_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).exclude(slate_player=away_player_1.slate_player).order_by('-projection', 'slate_player__site_pos'):
                                stack = models.SlateBuildStack.objects.create(
                                    build=build,
                                    game=qb.game,
                                    mini_game=game,
                                    build_order=count,
                                    qb=qb,
                                    player_1=player,
                                    player_2=player2,
                                    mini_player_1=away_player_1,
                                    mini_player_2=away_player_2,
                                    salary=sum(p.slate_player.salary for p in [qb, player, opp_player, away_player_1, away_player_2]),
                                    projection=sum(p.projection for p in [qb, player, opp_player, away_player_1, away_player_2])
                                )

                                if build.stack_construction is not None:
                                    if build.stack_construction.passes_rule(stack):
                                        stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)
                                        stack.save()
                                    else:
                                        stack.delete()                                            

                        # Finally make all mini stacks with players from both teams
                        for (idx, home_player) in enumerate(build.projections.filter(slate_player__in=home_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')):
                            for away_player in build.projections.filter(slate_player__in=away_players, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos'):
                                stack = models.SlateBuildStack.objects.create(
                                    build=build,
                                    game=qb.game,
                                    mini_game=game,
                                    build_order=count,
                                    qb=qb,
                                    player_1=player,
                                    player_2=player2,
                                    mini_player_1=home_player,
                                    mini_player_2=away_player,
                                    salary=sum(p.slate_player.salary for p in [qb, player, opp_player, home_player, away_player]),
                                    projection=sum(p.projection for p in [qb, player, opp_player, home_player, away_player])
                                )

                                if build.stack_construction is not None:
                                    if build.stack_construction.passes_rule(stack):
                                        stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)
                                        stack.save()
                                    else:
                                        stack.delete()                                            
                else:
                    stack = models.SlateBuildStack.objects.create(
                        build=build,
                        game=qb.game,
                        build_order=count,
                        qb=qb,
                        player_1=player,
                        player_2=player2,
                        salary=sum(p.slate_player.salary for p in [qb, player, player2]),
                        projection=sum(p.projection for p in [qb, player, player2])
                    )

                    if build.stack_construction is not None:
                        if build.stack_construction.passes_rule(stack):
                            stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)
                            stack.save()
                        else:
                            stack.delete()                                            

    elif build.configuration.game_stack_size == 4:
        count = 0
        # For each player, loop over opposing player to make a group for each possible stack combination
        for (index, player) in enumerate(team_players):
            if team_has_all_stack_only or not player.stack_only:
                for (index2, player2) in enumerate(team_players[index+1:]):
                    if player2 != player:  # don't include the pivot player
                        for opp_player in opp_players:
                            if player.slate_player.site_pos == 'TE' and player2.slate_player.site_pos == 'TE' and opp_player.slate_player.site_pos == 'TE':  # You can't have stacks with 3 TEs
                                continue
                            else:
                                count += 1
                                mu = float(sum(p.projection for p in [qb, player, player2, opp_player]))
                                stack = models.SlateBuildStack.objects.create(
                                    build=build,
                                    game=qb.game,
                                    build_order=count,
                                    qb=qb,
                                    player_1=player,
                                    player_2=player2,
                                    opp_player=opp_player,
                                    salary=sum(p.slate_player.salary for p in [qb, player, player2, opp_player]),
                                    projection=sum(p.projection for p in [qb, player, player2, opp_player])
                                )

                                if build.stack_construction is not None:
                                    if build.stack_construction.passes_rule(stack):
                                        stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)
                                        stack.save()
                                    else:
                                        stack.delete()                                            

    total_stack_projection = models.SlateBuildStack.objects.filter(build=build, qb=qb).aggregate(total_projection=Sum('projection')).get('total_projection')
    for stack in models.SlateBuildStack.objects.filter(build=build, qb=qb):
        print(stack, stack.projection/total_stack_projection, round(stack.projection/total_stack_projection * qb_lineup_count, 0))
        stack.count = round(max(stack.projection/total_stack_projection * qb_lineup_count, 1), 0)
        # stack.count = 20
        stack.save()


@shared_task
def calc_zscores_for_stacks(stack_ids):
    stacks = models.SlateBuildStack.objects.filter(id__in=stack_ids).order_by('-projection')
    projections = list(stacks.values_list('projection', flat=True))
    zscores = scipy.stats.zscore(projections)

    for (index, stack) in enumerate(stacks):
        stack.projection_zscore = zscores[index]
        stack.save()
    
    return list(stacks.values_list('id', flat=True))


@shared_task
def rank_stacks(stack_ids):
    stacks = models.SlateBuildStack.objects.filter(id__in=stack_ids).order_by('-projection').iterator()

    for stack in stacks:
        rank = models.SlateBuildStack.objects.filter(
            build=stack.build,
            projection__gt=stack.projection    
        ).count() + 1

        stack.rank = rank
        stack.save()


@shared_task
def reallocate_stacks_for_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here

        build = models.SlateBuild.objects.get(id=build_id)
        build.reallocate_stacks()
        build.total_lineups = build.stacks.all().aggregate(total=Sum('count')).get('total') 
        build.save()

        task.status = 'success'
        task.content = f'Stacks reallocated for {build}'
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem reallocating: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def prepare_construction_complete(chained_result, build_id, task_id=None):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here

        build = models.SlateBuild.objects.get(id=build_id)
        rank_stacks(build.stacks.all().values_list('id', flat=True))
        build.clean_stacks()
        # build.total_lineups = build.stacks.all().aggregate(total=Sum('count')).get('total') 
        build.save()

        build.calc_construction_ready()

        task.status = 'success'
        task.content = f'Stacks and groups created for {build}'
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem creating groups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def run_backtest(backtest_id, user_id):
    try:
        backtest = models.Backtest.objects.get(id=backtest_id)
        user = User.objects.get(pk=user_id)
        backtest.execute(user)
    except Exception as exc:
        traceback.print_exc()

        backtest.status = 'error'
        backtest.error_message = str(exc)
        backtest.save()


@shared_task
def find_optimals_for_backtest(backtest_id):
    try:
        backtest = models.Backtest.objects.get(id=backtest_id)
        backtest.find_optimals()
    except Exception as exc:
        traceback.print_exc()

        backtest.status = 'error'
        backtest.error_message = str(exc)
        backtest.save()


@shared_task
def speed_test(build_id):
    try:
        build = models.SlateBuild.objects.get(id=build_id)
        build.speed_test()
    except Exception as exc:
        traceback.print_exc()

        build.status = 'error'
        build.error_message = str(exc)
        build.save()


@shared_task
def run_slate_for_backtest(backtest_slate_id, user_id):
    try:
        slate = models.BacktestSlate.objects.get(id=backtest_slate_id)
        user = User.objects.get(pk=user_id)
        slate.execute(user)
    except Exception as exc:
        traceback.print_exc()
        if slate is not None:
            slate.handle_exception(exc)        


@shared_task
def monitor_backtest(backtest_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        start = datetime.datetime.now()
        backtest = models.Backtest.objects.get(id=backtest_id)
        while backtest.status != 'complete':
            backtest.update_status(task.user)
            time.sleep(1)

        backtest.elapsed_time = (datetime.datetime.now() - start)
        backtest.save()

        task.status = 'success'
        task.content = '{} complete.'.format(str(backtest))
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem running your build: {e}'
            task.save()

        if backtest is not None:
            backtest.status = 'error'
            backtest.error_message = str(e)
            backtest.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def monitor_build(build_id):
    start = datetime.datetime.now()
    build = models.SlateBuild.objects.get(id=build_id)
    all_stacks = build.stacks.filter(count__gt=0)

    while all_stacks.filter(lineups_created=False).count() > 0:
        build.update_build_progress()
        time.sleep(1)

    build.pct_complete = 1.0
    build.elapsed_time = (datetime.datetime.now() - start)
    build.save()


@shared_task
def analyze_optimals(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)
        build.analyze_optimals()

        task.status = 'success'
        task.content = 'Optimals analyzed.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem analyzing lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def analyze_lineups_for_build(build_id, task_id, use_optimals=False):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)

        chord([
            analyze_lineup_outcomes.s(lineup_id) for lineup_id in list(build.lineups.all().values_list('id', flat=True))
        ], analyze_lineup_outcomes_complete.s(build_id, task.id))()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem analyzing lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def analyze_lineup_outcomes(lineup_id):
    lineup = models.SlateBuildLineup.objects.get(id=lineup_id)
    lineup.simulate()


@shared_task
def analyze_lineup_outcomes_complete(chained_results, build_id, task_id):
    try:
        task = BackgroundTask.objects.get(id=task_id)
    except BackgroundTask.DoesNotExist:
        time.sleep(0.2)
        task = BackgroundTask.objects.get(id=task_id)

    build = models.SlateBuild.objects.get(id=build_id)

    task.status = 'success'
    task.content = f'Lineups analyzed for {build}'
    task.save()


@shared_task
def combine_lineup_outcomes(partial_outcomes, build_id, lineup_ids, use_optimals=False):    
    build = models.SlateBuild.objects.get(id=build_id)
    if use_optimals:
        lineups = build.actuals.filter(id__in=lineup_ids)
    else:
        lineups = build.lineups.filter(id__in=lineup_ids)

    outcomes_df = pandas.concat([pandas.read_json(partial_outcome) for partial_outcome in partial_outcomes], axis=1)
    ev_result = (outcomes_df * (1/len(outcomes_df.columns))).sum(axis=1).to_list()
    std_result = outcomes_df.std(axis=1).to_list()

    with transaction.atomic():
        for index, lineup in enumerate(lineups):
            if index < lineups.count():
                lineup.ev = ev_result[index] if index < len(ev_result) else 0.0
                lineup.std = std_result[index] if index < len(std_result) else 0.0
                lineup.save()


@shared_task
def rate_lineups(build_id, task_id, use_optimals=False):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        build = models.SlateBuild.objects.get(id=build_id)
        
        if use_optimals:
            all_lineups = build.actuals.exclude(std=0).order_by('id')
        else:
            all_lineups = build.lineups.exclude(std=0).order_by('id')

        ev_zscores = scipy.stats.zscore([float(a) for a in list(all_lineups.values_list('ev', flat=True))])
        std_zscores = scipy.stats.zscore([float(a) for a in list(all_lineups.values_list('std', flat=True))])

        with transaction.atomic():
            for index, lineup in enumerate(all_lineups):
                if lineup.ev < 0:
                    lineup.sim_rating = -999.99
                else:
                    lineup.sim_rating = ev_zscores[index] - std_zscores[index]
                lineup.save()

        task.status = 'success'
        task.content = 'Lineups rated.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem rating lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def clean_lineups(build_id, task_id=None):
    task = None

    try:
        if task_id is not None:
            try:
                task = BackgroundTask.objects.get(id=task_id)
            except BackgroundTask.DoesNotExist:
                time.sleep(0.2)
                task = BackgroundTask.objects.get(id=task_id)

        build = models.SlateBuild.objects.get(id=build_id)
        build.clean_lineups()

        if task is not None:
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
def find_expected_lineup_order(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        build = models.SlateBuild.objects.get(id=build_id)
        build.find_expected_lineup_order()

        task.status = 'success'
        task.content = 'Lineups ordered.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem ordering lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def build_complete(build_id, task_id):
    try:
        task = BackgroundTask.objects.get(id=task_id)
    except BackgroundTask.DoesNotExist:
        time.sleep(0.2)
        task = BackgroundTask.objects.get(id=task_id)

    build = models.SlateBuild.objects.get(id=build_id)
    # build.clean_lineups()
    # build.find_expected_lineup_order()
    build.pct_complete = 1.0
    build.status = 'complete'
    build.save()

    if build.backtest is not None:
        # analyze build
        build.get_actual_scores()

    task.status = 'success'
    task.content = f'{build.lineups.all().count()} lineups built.'
    task.save()


@shared_task
def build_completed_with_error(request, exc, traceback):
    print('Task {0!r} raised error: {1!r}'.format(request.id, exc))


@shared_task
def build_optimals_for_stack(stack_id):
    try:
        max_optimals_per_stack = 100
        stack = models.SlateBuildStack.objects.get(id=stack_id)

        if stack.has_possible_optimals():
            stack.build_optimals(max_optimals_per_stack)
        
        stack.optimals_created = True
        stack.save()
    except:
        traceback.print_exc()


@shared_task
def monitor_build_optimals(build_id):
    build = models.SlateBuild.objects.get(id=build_id)
    stacks = build.stacks.filter(count__gt=0)

    while stacks.filter(optimals_created=False).count() > 0:
        build.optimals_pct_complete = stacks.filter(optimals_created=True).count() / stacks.count()
        build.total_optimals = stacks.aggregate(total_optimals=Count('actuals')).get('total_optimals')
        build.save()
        time.sleep(1)

    build.total_optimals = stacks.aggregate(total_optimals=Count('actuals')).get('total_optimals')
    build.optimals_pct_complete = 1.0
    build.save()


@shared_task
def monitor_backtest_optimals(backtest_id):
    backtest = models.Backtest.objects.get(id=backtest_id)
    stacks = models.SlateBuildStack.objects.filter(
        count__gt=0,
        build__backtest__backtest=backtest
    )

    while stacks.filter(optimals_created=False).count() > 0:
        backtest.optimals_pct_complete = stacks.filter(optimals_created=True).count() / stacks.count()
        backtest.total_optimals = backtest.slates.all().aggregate(total_optimals=Sum('build__total_optimals')).get('total_optimals')

        
        backtest.save()
        time.sleep(1)

    backtest.total_optimals = backtest.slates.all().aggregate(total_optimals=Sum('build__total_optimals')).get('total_optimals')
    backtest.optimals_pct_complete = 1.0
    backtest.save()


@shared_task
def find_top_lineups_for_build(build_id, players_outcome_index, num_lineups):
    build = models.SlateBuild.objects.get(id=build_id)

    return optimize.naked_simulate(
        build.slate.site, 
        build.projections.filter(in_play=True).iterator(), 
        build.configuration, 
        players_outcome_index,
        num_lineups
    )


@shared_task
def complete_top_lineups_for_build(results, build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        flat_list = [item for sublist in results for item in sublist]
        df = pandas.DataFrame(
            flat_list, 
            columns=[
                'qb',
                'rb',
                'rb',
                'wr',
                'wr',
                'wr',
                'te',
                'flex',
                'dst',
                'salary',
            ]
        )

        build = models.SlateBuild.objects.get(id=build_id)
        build.lineups.all().delete()

        for index, row in df.iterrows():
            lineup = models.SlateBuildLineup.objects.create(
                build=build,
                qb=models.BuildPlayerProjection.objects.get(build=build, slate_player__player_id=row[0]),
                rb1=models.BuildPlayerProjection.objects.get(build=build, slate_player__player_id=row[1]),
                rb2=models.BuildPlayerProjection.objects.get(build=build, slate_player__player_id=row[2]),
                wr1=models.BuildPlayerProjection.objects.get(build=build, slate_player__player_id=row[3]),
                wr2=models.BuildPlayerProjection.objects.get(build=build, slate_player__player_id=row[4]),
                wr3=models.BuildPlayerProjection.objects.get(build=build, slate_player__player_id=row[5]),
                te=models.BuildPlayerProjection.objects.get(build=build, slate_player__player_id=row[6]),
                flex=models.BuildPlayerProjection.objects.get(build=build, slate_player__player_id=row[7]),
                dst=models.BuildPlayerProjection.objects.get(build=build, slate_player__player_id=row[8]),
                salary=row[9],
                projection=0.0
            )
        #     player_ids = index.split(',')
        #     players = models.BuildPlayerProjection.objects.filter(
        #         build=build,
        #         slate_player__player_id__in=player_ids
        #     )
            
        #     qb = players.get(slate_player__site_pos='QB')
        #     team_players = players.exclude(id=qb.id).filter(slate_player__team=qb.team)
        #     opp_players = players.filter(slate_player__team=qb.get_opponent())
        #     total_salary = players.aggregate(total_salary=Sum('slate_player__salary')).get('total_salary')
        #     total_projection = players.aggregate(total_projection=Sum('projection')).get('total_projection')
        #     top_stack, _ = models.SlateBuildTopStack.objects.get_or_create(
        #         build=build,
        #         game=players[0].game,
        #         qb=qb,
        #         player_1=team_players[0],
        #         player_2=team_players[1] if team_players.count() > 1 else None,
        #         opp_player=opp_players[0] if opp_players.count() > 0 else None
        #     )

        #     top_stack.salary = total_salary
        #     top_stack.projection = total_projection
        #     top_stack.times_used += row
        #     top_stack.save()

        task.status = 'success'
        task.content = f'{build.lineups.all().count()} lineups identified.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error identifying the lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def simulate_player_outcomes_for_build(build_id, players_outcome_index):
    build = models.SlateBuild.objects.get(id=build_id)

    return optimize.simulate(
        build.slate.site, 
        build.slate.get_projections().iterator(), 
        build.slate.get_projections().filter(slate_player__site_pos='QB'), 
        build.configuration, 
        players_outcome_index,
        10
    )


@shared_task
def combine_build_sim_results(results, build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        flat_list = [item for sublist in results for item in sublist]
        df = pandas.DataFrame(
            flat_list, 
            columns=[
                'qb',
                'rb',
                'rb',
                'wr',
                'wr',
                'wr',
                'te',
                'flex',
                'dst',
                'salary',
                'stack'
            ]
        )

        top_stack_df = df['stack'].value_counts()

        build = models.SlateBuild.objects.get(id=build_id)
        build.top_stacks.all().delete()

        for index, row in top_stack_df.iteritems():
            player_ids = index.split(',')
            players = models.BuildPlayerProjection.objects.filter(
                build=build,
                slate_player__player_id__in=player_ids
            )
            
            qb = players.get(slate_player__site_pos='QB')
            team_players = players.exclude(id=qb.id).filter(slate_player__team=qb.team)
            opp_players = players.filter(slate_player__team=qb.get_opponent())
            total_salary = players.aggregate(total_salary=Sum('slate_player__salary')).get('total_salary')
            total_projection = players.aggregate(total_projection=Sum('projection')).get('total_projection')
            top_stack, _ = models.SlateBuildTopStack.objects.get_or_create(
                build=build,
                game=players[0].game,
                qb=qb,
                player_1=team_players[0],
                player_2=team_players[1] if team_players.count() > 1 else None,
                opp_player=opp_players[0] if opp_players.count() > 0 else None
            )

            top_stack.salary = total_salary
            top_stack.projection = total_projection
            top_stack.times_used += row
            top_stack.save()

        task.status = 'success'
        task.content = f'{models.SlateBuildTopStack.objects.filter(build=build).count()} top stacks identified.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error identifying the top stacks: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def export_game_sim(game_id, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        game = models.SlateGame.objects.get(id=game_id)
        
        data = json.loads(json.loads(game.game_sim))
        sim_df = pandas.DataFrame.from_dict(data, orient='columns')
        sim_df.to_csv(result_path)

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
            build_writer.writerow(['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DEF'])

            lineups = build.lineups.all().order_by('order_number')

            for lineup in lineups:
                rbs = lineup.get_rbs()
                wrs = lineup.get_wrs()
                tes = lineup.get_tes()
                
                if lineup.get_num_rbs() > 2:
                    flex = rbs[2]
                elif lineup.get_num_wrs() > 3:
                    flex = wrs[3]
                else:
                    flex = tes[1]
                
                if build.slate.site == 'fanduel':
                    row = [
                        '{}:{}'.format(lineup.qb.slate_player.player_id, lineup.qb.name),
                        '{}:{}'.format(rbs[0].slate_player.player_id, rbs[0].name),
                        '{}:{}'.format(rbs[1].slate_player.player_id, rbs[1].name),
                        '{}:{}'.format(wrs[0].slate_player.player_id, wrs[0].name),
                        '{}:{}'.format(wrs[1].slate_player.player_id, wrs[1].name),
                        '{}:{}'.format(wrs[2].slate_player.player_id, wrs[2].name),
                        '{}:{}'.format(tes[0].slate_player.player_id, tes[0].name),
                        '{}:{}'.format(flex.slate_player.player_id, flex.name),
                        '{}:{}'.format(lineup.dst.slate_player.player_id, lineup.dst.name)
                    ]
                elif build.slate.site == 'draftkings':
                    row = [
                        '{1} ({0})'.format(lineup.qb.slate_player.player_id, lineup.qb.name),
                        '{1} ({0})'.format(rbs[0].slate_player.player_id, rbs[0].name),
                        '{1} ({0})'.format(rbs[1].slate_player.player_id, rbs[1].name),
                        '{1} ({0})'.format(wrs[0].slate_player.player_id, wrs[0].name),
                        '{1} ({0})'.format(wrs[1].slate_player.player_id, wrs[1].name),
                        '{1} ({0})'.format(wrs[2].slate_player.player_id, wrs[2].name),
                        '{1} ({0})'.format(tes[0].slate_player.player_id, tes[0].name),
                        '{1} ({0})'.format(flex.slate_player.player_id, flex.name),
                        '{1} ({0})'.format(lineup.dst.slate_player.player_id, lineup.dst.name)
                    ]
                elif build.slate.site == 'yahoo':
                    row = [
                        '{0} - {1}'.format(lineup.qb.slate_player.player_id, lineup.qb.name),
                        '{0} - {1}'.format(rbs[0].slate_player.player_id, rbs[0].name),
                        '{0} - {1}'.format(rbs[1].slate_player.player_id, rbs[1].name),
                        '{0} - {1}'.format(wrs[0].slate_player.player_id, wrs[0].name),
                        '{0} - {1}'.format(wrs[1].slate_player.player_id, wrs[1].name),
                        '{0} - {1}'.format(wrs[2].slate_player.player_id, wrs[2].name),
                        '{0} - {1}'.format(tes[0].slate_player.player_id, tes[0].name),
                        '{0} - {1}'.format(flex.slate_player.player_id, flex.name),
                        '{0} - {1}'.format(lineup.dst.slate_player.player_id, lineup.dst.name)
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


@shared_task
def export_lineups_for_analysis(lineup_ids, result_path, result_url, task_id, use_optimals=False):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        if use_optimals:
            lineups = models.SlateBuildActualsLineup.objects.filter(id__in=lineup_ids).select_related('build__slate__week').annotate(week=F('build__slate__week__num'), year=F('build__slate__week__slate_year'))
        else:
            lineups = models.SlateBuildLineup.objects.filter(id__in=lineup_ids).select_related('build__slate__week').annotate(week=F('build__slate__week__num'), year=F('build__slate__week__slate_year'))

        lineups_df = pandas.DataFrame.from_records(lineups.values(
            'id', 
            'build_id', 
            'stack__qb__slate_player__name', 
            'stack__build_order', 
            'qb__slate_player__name', 
            'rb1__slate_player__name', 
            'rb2__slate_player__name', 
            'wr1__slate_player__name', 
            'wr2__slate_player__name', 
            'wr3__slate_player__name', 
            'te__slate_player__name', 
            'flex__slate_player__name', 
            'dst__slate_player__name', 
            'salary',
            'mean',
            'std',
            'actual'
        ), columns=[
            'id', 
            'build_id', 
            'stack', 
            'stack_build_order', 
            'qb', 
            'rb1', 
            'rb2', 
            'wr1', 
            'wr2', 
            'wr3', 
            'te', 
            'flex', 
            'dst', 
            'salary',
            'mean',
            'std',
            'actual'
        ])

        lineups_df.to_excel(result_path)

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


@shared_task
def export_slate_lineups(lineup_ids, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        lineups = models.SlateLineup.objects.filter(
            id__in=lineup_ids
        ).annotate(
            qb_name=F('qb__csv_name'),
            rb1_name=F('rb1__csv_name'),
            rb2_name=F('rb2__csv_name'),
            wr1_name=F('wr1__csv_name'),
            wr2_name=F('wr2__csv_name'),
            wr3_name=F('wr3__csv_name'),
            te_name=F('te__csv_name'),
            flex_name=F('flex__csv_name'),
            dst_name=F('dst__csv_name'),
        )

        lineups_df = pandas.DataFrame.from_records(lineups.values(
            'qb_name', 
            'rb1_name', 
            'rb2_name', 
            'wr1_name', 
            'wr2_name', 
            'wr3_name', 
            'te_name', 
            'flex_name', 
            'dst_name', 
            'total_salary'
        ))

        lineups_df.to_csv(result_path)

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


@shared_task
def export_stacks(stack_ids, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        stacks = models.SlateBuildStack.objects.filter(id__in=stack_ids)
        logger.info(stacks[0].game)

        stacks_df = pandas.DataFrame.from_records(stacks.values(
            'id',
            'build_id',
            'game__game__home_team',
            'game__game__away_team',
            'build_order',
            'rank',
            'qb__slate_player__name',
            'player_1__slate_player__name',
            'player_2__slate_player__name',
            'opp_player__slate_player__name',
            'mini_player_1__slate_player__name',
            'mini_player_2__slate_player__name',
            'contains_top_pc',
            'salary',
            'projection',
            'count',
            'times_used',
            'qb__slate_player__slate_game__zscore',
            'actual',
        ), columns=[
            'build_id',
            'home_team',
            'away_team',
            'build_order',
            'rank',
            'qb',
            'player_1',
            'player_2',
            'opp_player',
            'mini_player_1',
            'mini_player_2',
            'contains_top_pc',
            'salary',
            'projection',
            'count',
            'times_used',
            'game_zscore',
            'actual',
        ])
        logger.info(stacks_df)

        stacks_df.to_excel(result_path)

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


@shared_task
def export_projections(proj_ids, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        projections = models.SlatePlayerProjection.objects.filter(id__in=proj_ids)

        with open(result_path, 'w') as temp_csv:
            build_writer = csv.writer(temp_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            build_writer.writerow([
                'player', 
                'slate', 
                'salary', 
                'position', 
                'team', 
                'projection', 
                'ownership_projection',
                'zscore',
                'adjusted_opportunity',
                'value', 
                'game_zscore',
                'game_total', 
                'team_total', 
                'spread',
                'sim_median',
                'sim_75',
                'sim_ceil',
                'actual'
            ])

            limit = 100
            pages = math.ceil(projections.count()/limit)

            offset = 0
            count = 0
            for page in range(0, pages):
                offset = page * limit

                for proj in projections[offset:offset+limit]:
                    count += 1
                    try:
                        build_writer.writerow([
                            proj.name, 
                            proj.slate_player.slate, 
                            proj.salary, 
                            proj.position, 
                            proj.team, 
                            proj.projection, 
                            proj.ownership_projection,
                            proj.zscore,
                            proj.adjusted_opportunity,
                            proj.value, 
                            proj.game.zscore,
                            proj.game_total, 
                            proj.team_total, 
                            proj.spread,
                            numpy.median(proj.sim_scores),
                            proj.get_percentile_sim_score(75),
                            proj.get_percentile_sim_score(90),
                            proj.slate_player.fantasy_points
                        ])
                    except:
                        pass

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


@shared_task
def export_player_outcomes(proj_ids, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        projections = models.SlatePlayerProjection.objects.filter(id__in=proj_ids, sim_scores__isnull=False)
        outcomes = list(projections.values_list('sim_scores', flat=True))
        player_names = list(projections.values_list('slate_player__name', flat=True))
        ownerships = list(projections.values_list('slate_player__ownership', flat=True))
        df_outcomes = pandas.DataFrame(outcomes)
        df_outcomes.insert(0, 'player', player_names)
        df_outcomes.insert(1, 'ownership', ownerships)
        df_outcomes.to_csv(result_path)

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


@shared_task
def export_field_outcomes(slate_id, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)  

        slate = models.Slate.objects.get(id=slate_id)
        field_lineups = slate.field_lineups.all().select_related(
            'qb__slate_player',
            'rb1__slate_player',
            'rb2__slate_player',
            'wr1__slate_player',
            'wr2__slate_player',
            'wr3__slate_player',
            'te__slate_player',
            'flex__slate_player',
            'dst__slate_player',
        )
        field_outcomes = list(field_lineups.values_list('sim_scores', flat=True))
        
        df_lineups = pandas.DataFrame.from_records(field_lineups.values('username', 'qb__slate_player__name', 'rb1__slate_player__name', 'rb2__slate_player__name', 'wr1__slate_player__name', 'wr2__slate_player__name', 'wr3__slate_player__name', 'te__slate_player__name', 'flex__slate_player__name', 'dst__slate_player__name'))
        df_outcomes = pandas.DataFrame(field_outcomes)
        df_outcomes = pandas.concat([df_lineups, df_outcomes], axis=1)
        df_outcomes.to_csv(result_path)
        
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
            if slate.salaries_sheet_type == 'site':
                if slate.site == 'fanduel' or slate.site == 'yahoo':
                    csv_reader = csv.DictReader(salaries_file)
                else:
                    csv_reader = csv.reader(salaries_file, delimiter=',')
            else:
                csv_reader = csv.DictReader(salaries_file)

            success_count = 0
            missing_players = []

            for row in csv_reader:
                if slate.salaries_sheet_type == 'site':
                    site = slate.site
                    if slate.site == 'fanduel':
                        player_id = row['Id']
                        site_pos = row['Position']
                        roster_pos = row['Position']
                        player_name = row['Nickname'].replace('Oakland Raiders', 'Las Vegas Raiders').replace('Washington Redskins', 'Washington Football Team')
                        csv_name = f'{player_id}:{player_name}'
                        salary = int(row['Salary'])
                        game = row['Game'].replace('@', '_').replace('JAX', 'JAC')
                        team = row['Team']
                    elif slate.site == 'draftkings':
                        if success_count < 8:
                            success_count += 1
                            continue
                        
                        start_col = 7 if slate.is_showdown else 10

                        player_id = row[start_col + 3]
                        site_pos = row[start_col]
                        roster_pos = row[start_col + 4] if slate.is_showdown else site_pos
                        player_name = row[start_col + 2].strip()
                        csv_name = f'{player_name} ({player_id})'
                        salary = row[start_col + 5]
                        game = row[start_col + 6].replace('@', '_').replace('JAX', 'JAC')
                        game = game[:game.find(' ')]
                        team = 'JAC' if row[start_col + 7] == 'JAX' else row[start_col + 7]
                    elif slate.site == 'yahoo':
                        if success_count < 6:
                            success_count += 1
                            continue
                        
                        if row['ID'] is None or row['ID'] == '': 
                            continue
                        
                        player_id = row['ID']
                        site_pos = row['Position']
                        roster_pos = row['Position']
                        player_name = f'{row["First Name"]} {row["Last Name"]}'.replace('Oakland Raiders', 'Las Vegas Raiders').replace('Washington Redskins', 'Washington Football Team').strip()
                        csv_name = f'{player_id} - ({player_name})'
                        salary = int(row["Salary"])
                        game = row['Game'].replace('@', '_').replace('JAX', 'JAC')
                        team = 'JAC' if row['Team'] == 'JAX' else row['Team']
                elif slate.salaries_sheet_type == 'fantasycruncher':
                    site = 'fc'
                    player_id = uuid.uuid4()
                    player_name = row['Player'].replace('Oakland Raiders', 'Las Vegas Raiders').replace('Washington Redskins', 'Washington Football Team')
                    if slate.site == 'fanduel' and row['Pos'] == 'DST':
                        site_pos = 'D'
                        csv_name = f'{player_id}:{player_name}'
                    elif slate.site == 'yahoo' and row['Pos'] == 'DST':
                        site_pos = 'DEF'
                        csv_name = f'{player_id} - ({player_name})'
                    else:
                        site_pos = row['Pos']
                        csv_name = f'{player_name} ({player_id})'

                    roster_pos = site_pos
                    salary = int(row['Salary'])                    
                    team = row['Team']
                    opp = row['Opp']
                    if '@' in opp:
                        game = f'{team}{opp}'.replace('@ ', '_').replace('JAX', 'JAC')
                    else:
                        game = f'{opp}_{team}'.replace('vs ', '').replace('JAX', 'JAC')
                elif slate.salaries_sheet_type == 'sabersim':
                    site = 'sabersim'
                    player_id = row['DFS ID']
                    if slate.site == 'fanduel' and row['Pos'] == 'DST':
                        site_pos = 'D'
                    elif slate.site == 'yahoo' and row['Pos'] == 'DST':
                        site_pos = 'DEF'
                    else:
                        site_pos = row['Pos'].split(',')[0]
                    roster_pos = site_pos
                    player_name = row['Name'].replace('Oakland Raiders', 'Las Vegas Raiders').replace('Washington Redskins', 'Washington Football Team')
                    salary = int(row['Salary'])                    
                    team = row['Team'].replace('JAX', 'JAC')
                    # opp = row['Opp']
                    # if '@' in opp:
                    #     game = f'{team}{opp}'.replace('@ ', '_').replace('JAX', 'JAC')
                    # else:
                    #     game = f'{opp}_{team}'.replace('vs ', '').replace('JAX', 'JAC')

                alias = models.Alias.find_alias(player_name, site)
                
                if alias is not None:
                    try:
                        slate_player = models.SlatePlayer.objects.get(
                            slate=slate,
                            name=alias.get_alias(slate.site),
                            team=team,
                            roster_position=roster_pos,
                            site_pos=site_pos
                        )
                    except models.SlatePlayer.DoesNotExist:
                        slate_player = models.SlatePlayer(
                            slate=slate,
                            team=team,
                            name=alias.get_alias(slate.site),
                            roster_position=roster_pos,
                            site_pos=site_pos
                        )

                    slate_player.player_id = player_id
                    slate_player.salary = salary
                    slate_player.csv_name = csv_name
                    slate_player.slate_game = slate_player.get_slate_game()
                    slate_player.save()

                    success_count += 1
                else:
                    missing_players.append(player_name)


        task.status = 'success'
        task.content = '{} players have been successfully added to {}.'.format(success_count, str(slate)) if len(missing_players) == 0 else '{} players have been successfully added to {}. {} players could not be identified.'.format(success_count, str(slate), len(missing_players))
        task.link = '/admin/nfl/missingalias/' if len(missing_players) > 0 else None
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing slate players: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def create_slate_lineups(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)

        start = time.time()
        slate.possible_lineups.all().delete()
        logger.info(f'Deleting existing lineups took {time.time() - start}s')
        dst_label = slate.dst_label

        start = time.time()
        slate_players = slate.players.filter(projection__in_play=True).order_by('-salary')
        salaries = {}
        for p in slate_players:
            salaries[p.id] = p.salary
        logger.info(f'Finding players and salaries took {time.time() - start}s. There are {slate_players.count()} players in the player pool.')

        start = time.time()
        qbs = list(slate.get_projections().filter(
            slate_player__site_pos='QB',
            in_play=True
        ).order_by('-projection').values_list('slate_player_id', flat=True))
        rbs = list(slate.get_projections().filter(
            slate_player__site_pos='RB',
            in_play=True
        ).order_by('-projection').values_list('slate_player_id', flat=True))
        wrs = list(slate.get_projections().filter(
            slate_player__site_pos='WR',
            in_play=True
        ).order_by('-projection').values_list('slate_player_id', flat=True))
        tes = list(slate.get_projections().filter(
            slate_player__site_pos='TE',
            in_play=True
        ).order_by('-projection').values_list('slate_player_id', flat=True))
        dsts = list(slate.get_projections().filter(
            slate_player__site_pos=dst_label,
            in_play=True
        ).order_by('-projection').values_list('slate_player_id', flat=True))
        logger.info(f'Filtering player positions took {time.time() - start}s')

        start = time.time()
        rb_combos = list(itertools.combinations(rbs, 2))
        logger.info(f'RB combos took {time.time() - start}s. There are {len(rb_combos)} combinations.')

        start = time.time()
        wr_combos = list(itertools.combinations(wrs, 3))
        logger.info(f'WR combos took {time.time() - start}s. There are {len(wr_combos)} combinations.')

        start = time.time()
        projections = slate.get_projections().filter(in_play=True).order_by('-slate_player__salary')
        player_outcomes = {}
        for p in projections:
            player_outcomes[p.slate_player.id] = p.sim_scores
        logger.info(f'Getting player outcomes took {time.time() - start}s')

        cycles = slate.num_cycles
        jobs = []

        for _ in range(0, cycles):
            jobs = jobs + [create_lineup_combos_for_qb.si(slate.id, qb, rb_combos, wr_combos, tes, rbs + wrs, dsts, player_outcomes, slate.lineups_per_cycle) for qb in qbs]

        chord(jobs, complete_slate_lineups.si(task_id))()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem creating lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def create_lineup_combos_for_qb(slate_id, qb_id, rb_combos, wr_combos, te_ids, flexes, dst_ids, player_outcomes, num_combos):
    def get_random_lineup(slate, qb_id, rb_combos, wr_combos, tes, flexes, dsts):
        random_rbs = rb_combos[random.randrange(0, len(rb_combos))]
        random_wrs = wr_combos[random.randrange(0, len(wr_combos))]
        random_te = tes[random.randrange(0, len(tes))]
        random_flex = flexes[random.randrange(0, len(flexes))]
        random_dst = dsts[random.randrange(0, len(dsts))]

        l = [qb_id, random_rbs[0], random_rbs[1], random_wrs[0], random_wrs[1], random_wrs[2], random_te, random_flex, random_dst]
        total_salary = slate.get_projections().filter(
            slate_player_id__in=l
        ).aggregate(total_salary=Sum('slate_player__salary')).get('total_salary')

        return (l, total_salary)

    def is_lineup_valid(slate, l):
        players = slate.get_projections().filter(
            slate_player_id__in=l
        )
        
        num_qbs = players.aggregate(num_qbs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='QB'))).get('num_qbs')
        if num_qbs > 1:
            return False
        
        num_wrs = players.aggregate(num_wrs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='WR'))).get('num_wrs')
        if num_wrs > 4:
            return False
        
        num_rbs = players.aggregate(num_rbs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='RB'))).get('num_rbs')
        if num_rbs > 3:
            return False
        
        num_tes = players.aggregate(num_tes=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='TE'))).get('num_tes')
        if num_tes > 2:
            return False

        # prevent duplicate players
        visited = set()
        dup = [x for x in l if x in visited or (visited.add(x) or False)]
        if len(dup) > 0:
            return False

        return True

    logger.info(f'qb = {qb_id}')
    slate = models.Slate.objects.get(id=slate_id)
    salary_thresholds = slate.salary_thresholds
    lineups = []

    start = time.time()
    for _ in range(0, num_combos):
        l, total_salary = get_random_lineup(slate, qb_id, rb_combos, wr_combos, te_ids, flexes, dst_ids)

        '''
        TODO: Add additional constraints
            - No duplicate lineups
        '''
        while (total_salary < salary_thresholds[0] or total_salary > salary_thresholds[1] or not is_lineup_valid(slate, l)):
            l, total_salary = get_random_lineup(slate, qb_id, rb_combos, wr_combos, te_ids, flexes, dst_ids)

        l.append(total_salary)  ## append total salary to end of lineup array so we can make a dataframe
        lineups.append(l)
    logger.info(f'  Lineup selection took {time.time() - start}s')

    start = time.time()
    df_lineups = pandas.DataFrame(lineups, columns=[
        'qb_id',
        'rb1_id',
        'rb2_id',
        'wr1_id',
        'wr2_id',
        'wr3_id',
        'te_id',
        'flex_id',
        'dst_id',
        'total_salary',
    ])
    df_lineups['slate_id'] = slate_id
    logger.info(f'  Dataframe took {time.time() - start}s')

    start = time.time()
    df_lineups['sim_scores'] = df_lineups.apply(lambda x: list(numpy.array(player_outcomes.get(str(x['qb_id'])), numpy.float64) + numpy.array(player_outcomes.get(str(x['rb1_id'])), numpy.float64) + numpy.array(player_outcomes.get(str(x['rb2_id'])), numpy.float64) + numpy.array(player_outcomes.get(str(x['wr1_id'])), numpy.float64) + numpy.array(player_outcomes.get(str(x['wr2_id'])), numpy.float64) + numpy.array(player_outcomes.get(str(x['wr3_id'])), numpy.float64) + numpy.array(player_outcomes.get(str(x['te_id'])), numpy.float64) + numpy.array(player_outcomes.get(str(x['flex_id'])), numpy.float64) + numpy.array(player_outcomes.get(str(x['dst_id'])), numpy.float64)), axis=1)
    logger.info(f'  Sim scores took {time.time() - start}s')

    start = time.time()
    # user = settings.DATABASES['default']['USER']
    # password = settings.DATABASES['default']['PASSWORD']
    # database_name = settings.DATABASES['default']['NAME']
    # database_url = 'postgresql://{user}:{password}@db:5432/{database_name}'.format(
    #     user=user,
    #     password=password,
    #     database_name=database_name,
    # )

    # engine = sqlalchemy.create_engine(database_url, echo=False)
    df_lineups.to_sql('nfl_slatelineup', engine, if_exists='append', index=False, chunksize=1000)
    
    logger.info(f'  Storage took {time.time() - start}s')


@shared_task
def complete_slate_lineups(task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        task.status = 'success'
        task.content = f'All possible lineups created.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem creating slate lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


def process_dk_classic_field_lineups(build, player_sim_scores):
    if build.field_lineup_upload:
        build.field_lineups_to_beat.all().delete()

        with open(build.field_lineup_upload.path, mode='r') as lineups_file:
            csv_reader = csv.reader(lineups_file)

            for index, row in enumerate(csv_reader):
                if index > 0:  # skip header
                    handle = row[0]
                    qb = re.findall(r'\([0-9]*\)', row[1])[0].replace('(', '').replace(')', '')
                    rb1 = re.findall(r'\([0-9]*\)', row[2])[0].replace('(', '').replace(')', '')
                    rb2 = re.findall(r'\([0-9]*\)', row[3])[0].replace('(', '').replace(')', '')
                    wr1 = re.findall(r'\([0-9]*\)', row[4])[0].replace('(', '').replace(')', '')
                    wr2 = re.findall(r'\([0-9]*\)', row[5])[0].replace('(', '').replace(')', '')
                    wr3 = re.findall(r'\([0-9]*\)', row[6])[0].replace('(', '').replace(')', '')
                    te = re.findall(r'\([0-9]*\)', row[7])[0].replace('(', '').replace(')', '')
                    flex = re.findall(r'\([0-9]*\)', row[8])[0].replace('(', '').replace(')', '')
                    dst = re.findall(r'\([0-9]*\)', row[9])[0].replace('(', '').replace(')', '')

                    # score the lineup
                    sim_scores = numpy.array(player_sim_scores[qb], dtype=numpy.float64) + numpy.array(player_sim_scores[rb1], dtype=numpy.float64) + numpy.array(player_sim_scores[rb2], dtype=numpy.float64) + numpy.array(player_sim_scores[wr1], dtype=numpy.float64) + numpy.array(player_sim_scores[wr2], dtype=numpy.float64) + numpy.array(player_sim_scores[wr3], dtype=numpy.float64) + numpy.array(player_sim_scores[te], dtype=numpy.float64) + numpy.array(player_sim_scores[flex], dtype=numpy.float64) + numpy.array(player_sim_scores[dst], dtype=numpy.float64)

                    # find this lineup in all possible lineups
                    slate_lineup = build.slate.possible_lineups.filter(
                        qb__player_id=qb,
                        rb1__player_id__in=[rb1, rb2, flex],
                        rb2__player_id__in=[rb1, rb2, flex],
                        wr1__player_id__in=[wr1, wr2, wr3, flex],
                        wr2__player_id__in=[wr1, wr2, wr3, flex],
                        wr3__player_id__in=[wr1, wr2, wr3, flex],
                        te__player_id__in=[te, flex],
                        flex__player_id__in=[rb1, rb2, wr1, wr2, wr3, te, flex],
                        dst__player_id=dst
                    )

                    if slate_lineup.count() == 0:
                        slate_lineup = models.SlateLineup.objects.create(
                            slate=build.slate,
                            qb=models.SlatePlayer.objects.get(slate=build.slate, player_id=qb),
                            rb1=models.SlatePlayer.objects.get(slate=build.slate, player_id=rb1),
                            rb2=models.SlatePlayer.objects.get(slate=build.slate, player_id=rb2),
                            wr1=models.SlatePlayer.objects.get(slate=build.slate, player_id=wr1),
                            wr2=models.SlatePlayer.objects.get(slate=build.slate, player_id=wr2),
                            wr3=models.SlatePlayer.objects.get(slate=build.slate, player_id=wr3),
                            te=models.SlatePlayer.objects.get(slate=build.slate, player_id=te),
                            flex=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex),
                            dst=models.SlatePlayer.objects.get(slate=build.slate, player_id=dst)
                        )
                        slate_lineup.simulate()

                        if slate_lineup.total_salary > build.slate.salary_thresholds[1]:
                            raise Exception(f'Lineup for {handle} exceeds salary cap.')
                        
                        slate_lineup.sim_scores = sim_scores.tolist()
                        slate_lineup.save()

                        slate_lineup = [slate_lineup]
                    elif slate_lineup.count() > 1:
                        raise Exception(f'There were {slate_lineup.count()} duplicate lineups found for {handle} among all possible lineups.')

                    lineup = models.FieldLineupToBeat.objects.create(
                        build=build,
                        opponent_handle=handle,
                        slate_lineup=slate_lineup[0]
                    )

                    lineup.median = numpy.median(sim_scores)
                    lineup.s75 = numpy.percentile(sim_scores, 75)
                    lineup.s90 = numpy.percentile(sim_scores, 90)
                    lineup.save()


def process_dk_showdown_field_lineups(build, player_sim_scores):
    if build.field_lineup_upload:
        build.field_sd_lineups_to_beat.all().delete()

        with open(build.field_lineup_upload.path, mode='r') as lineups_file:
            csv_reader = csv.reader(lineups_file)

            for index, row in enumerate(csv_reader):
                if index > 0:  # skip header
                    handle = row[0]
                    cpt = re.findall(r'\([0-9]*\)', row[1])[0].replace('(', '').replace(')', '')
                    flex1 = re.findall(r'\([0-9]*\)', row[2])[0].replace('(', '').replace(')', '')
                    flex2 = re.findall(r'\([0-9]*\)', row[3])[0].replace('(', '').replace(')', '')
                    flex3 = re.findall(r'\([0-9]*\)', row[4])[0].replace('(', '').replace(')', '')
                    flex4 = re.findall(r'\([0-9]*\)', row[5])[0].replace('(', '').replace(')', '')
                    flex5 = re.findall(r'\([0-9]*\)', row[6])[0].replace('(', '').replace(')', '')

                    # score the lineup
                    sim_scores = numpy.array(player_sim_scores[cpt], dtype=numpy.float64) + numpy.array(player_sim_scores[flex1], dtype=numpy.float64) + numpy.array(player_sim_scores[flex2], dtype=numpy.float64) + numpy.array(player_sim_scores[flex3], dtype=numpy.float64) + numpy.array(player_sim_scores[flex4], dtype=numpy.float64) + numpy.array(player_sim_scores[flex5], dtype=numpy.float64)

                    # find this lineup in all possible lineups
                    slate_lineup = build.slate.possible_sd_lineups.filter(
                        cpt__player_id=cpt,
                        flex1__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                        flex2__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                        flex3__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                        flex4__player_id__in=[flex1, flex2, flex3, flex4, flex5],
                        flex5__player_id__in=[flex1, flex2, flex3, flex4, flex5]
                    )

                    if slate_lineup.count() == 0:
                        slate_lineup = models.SlateSDLineup.objects.create(
                            slate=build.slate,
                            cpt=models.SlatePlayer.objects.get(slate=build.slate, player_id=cpt),
                            flex1=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex1),
                            flex2=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex2),
                            flex3=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex3),
                            flex4=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex4),
                            flex5=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex5)
                        )
                        slate_lineup.simulate()

                        if slate_lineup.total_salary > build.slate.salary_thresholds[1]:
                            raise Exception(f'Lineup for {handle} exceeds salary cap.')
                        
                        slate_lineup.sim_scores = sim_scores.tolist()
                        slate_lineup.save()

                        slate_lineup = [slate_lineup]
                    elif slate_lineup.count() > 1:
                        raise Exception(f'There were {slate_lineup.count()} duplicate lineups found for {handle} among all possible lineups.')

                    lineup = models.FieldSDLineupToBeat.objects.create(
                        build=build,
                        opponent_handle=handle,
                        slate_lineup=slate_lineup[0]
                    )

                    lineup.median = numpy.median(sim_scores)
                    lineup.s75 = numpy.percentile(sim_scores, 75)
                    lineup.s90 = numpy.percentile(sim_scores, 90)
                    lineup.save()


def process_fd_classic_field_lineups(build, player_sim_scores):
    if build.field_lineup_upload:
        build.field_lineups_to_beat.all().delete()

        with open(build.field_lineup_upload.path, mode='r') as lineups_file:
            csv_reader = csv.reader(lineups_file)

            for index, row in enumerate(csv_reader):
                if index > 0:  # skip header
                    handle = row[0]
                    qb = re.findall(r'[0-9-]*', row[1])[0].replace('(', '').replace(')', '')
                    rb1 = re.findall(r'[0-9-]*', row[2])[0].replace('(', '').replace(')', '')
                    rb2 = re.findall(r'[0-9-]*', row[3])[0].replace('(', '').replace(')', '')
                    wr1 = re.findall(r'[0-9-]*', row[4])[0].replace('(', '').replace(')', '')
                    wr2 = re.findall(r'[0-9-]*', row[5])[0].replace('(', '').replace(')', '')
                    wr3 = re.findall(r'[0-9-]*', row[6])[0].replace('(', '').replace(')', '')
                    te = re.findall(r'[0-9-]*', row[7])[0].replace('(', '').replace(')', '')
                    flex = re.findall(r'[0-9-]*', row[8])[0].replace('(', '').replace(')', '')
                    dst = re.findall(r'[0-9-]*', row[9])[0].replace('(', '').replace(')', '')

                    # score the lineup
                    sim_scores = numpy.array(player_sim_scores[qb], dtype=numpy.float64) + numpy.array(player_sim_scores[rb1], dtype=numpy.float64) + numpy.array(player_sim_scores[rb2], dtype=numpy.float64) + numpy.array(player_sim_scores[wr1], dtype=numpy.float64) + numpy.array(player_sim_scores[wr2], dtype=numpy.float64) + numpy.array(player_sim_scores[wr3], dtype=numpy.float64) + numpy.array(player_sim_scores[te], dtype=numpy.float64) + numpy.array(player_sim_scores[flex], dtype=numpy.float64) + numpy.array(player_sim_scores[dst], dtype=numpy.float64)

                    # find this lineup in all possible lineups
                    slate_lineup = build.slate.possible_lineups.filter(
                        qb__player_id=qb,
                        rb1__player_id__in=[rb1, rb2, flex],
                        rb2__player_id__in=[rb1, rb2, flex],
                        wr1__player_id__in=[wr1, wr2, wr3, flex],
                        wr2__player_id__in=[wr1, wr2, wr3, flex],
                        wr3__player_id__in=[wr1, wr2, wr3, flex],
                        te__player_id__in=[te, flex],
                        flex__player_id__in=[rb1, rb2, wr1, wr2, wr3, te, flex],
                        dst__player_id=dst
                    )

                    if slate_lineup.count() == 0:
                        slate_lineup = models.SlateLineup.objects.create(
                            slate=build.slate,
                            qb=models.SlatePlayer.objects.get(slate=build.slate, player_id=qb),
                            rb1=models.SlatePlayer.objects.get(slate=build.slate, player_id=rb1),
                            rb2=models.SlatePlayer.objects.get(slate=build.slate, player_id=rb2),
                            wr1=models.SlatePlayer.objects.get(slate=build.slate, player_id=wr1),
                            wr2=models.SlatePlayer.objects.get(slate=build.slate, player_id=wr2),
                            wr3=models.SlatePlayer.objects.get(slate=build.slate, player_id=wr3),
                            te=models.SlatePlayer.objects.get(slate=build.slate, player_id=te),
                            flex=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex),
                            dst=models.SlatePlayer.objects.get(slate=build.slate, player_id=dst)
                        )
                        slate_lineup.simulate()

                        if slate_lineup.total_salary > build.slate.salary_thresholds[1]:
                            raise Exception(f'Lineup for {handle} exceeds salary cap.')
                        
                        slate_lineup.sim_scores = sim_scores.tolist()
                        slate_lineup.save()

                        slate_lineup = [slate_lineup]
                    elif slate_lineup.count() > 1:
                        raise Exception(f'There were {slate_lineup.count()} duplicate lineups found for {handle} among all possible lineups.')

                    lineup = models.FieldLineupToBeat.objects.create(
                        build=build,
                        opponent_handle=handle,
                        slate_lineup=slate_lineup[0]
                    )

                    lineup.median = numpy.median(sim_scores)
                    lineup.s75 = numpy.percentile(sim_scores, 75)
                    lineup.s90 = numpy.percentile(sim_scores, 90)
                    lineup.save()


def process_fd_showdown_field_lineups(build, player_sim_scores):
    if build.field_lineup_upload:
        build.field_sd_lineups_to_beat.all().delete()

        with open(build.field_lineup_upload.path, mode='r') as lineups_file:
            csv_reader = csv.reader(lineups_file)

            for index, row in enumerate(csv_reader):
                if index > 0:  # skip header
                    handle = row[0]
                    cpt = re.findall(r'[0-9-]*', row[1])[0].replace('(', '').replace(')', '')
                    flex1 = re.findall(r'[0-9-]*', row[2])[0].replace('(', '').replace(')', '')
                    flex2 = re.findall(r'[0-9-]*', row[3])[0].replace('(', '').replace(')', '')
                    flex3 = re.findall(r'[0-9-]*', row[4])[0].replace('(', '').replace(')', '')
                    flex4 = re.findall(r'[0-9-]*', row[5])[0].replace('(', '').replace(')', '')

                    # score the lineup
                    sim_scores = numpy.array(player_sim_scores[cpt], dtype=numpy.float64) + numpy.array(player_sim_scores[flex1], dtype=numpy.float64) + numpy.array(player_sim_scores[flex2], dtype=numpy.float64) + numpy.array(player_sim_scores[flex3], dtype=numpy.float64) + numpy.array(player_sim_scores[flex4], dtype=numpy.float64)

                    # find this lineup in all possible lineups
                    slate_lineup = build.slate.possible_sd_lineups.filter(
                        cpt__player_id=cpt,
                        flex1__player_id__in=[flex1, flex2, flex3, flex4],
                        flex2__player_id__in=[flex1, flex2, flex3, flex4],
                        flex3__player_id__in=[flex1, flex2, flex3, flex4],
                        flex4__player_id__in=[flex1, flex2, flex3, flex4]
                    )

                    if slate_lineup.count() == 0:
                        slate_lineup = models.SlateSDLineup.objects.create(
                            slate=build.slate,
                            cpt=models.SlatePlayer.objects.get(slate=build.slate, player_id=cpt),
                            flex1=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex1),
                            flex2=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex2),
                            flex3=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex3),
                            flex4=models.SlatePlayer.objects.get(slate=build.slate, player_id=flex4)
                        )
                        slate_lineup.simulate()

                        if slate_lineup.total_salary > build.slate.salary_thresholds[1]:
                            raise Exception(f'Lineup for {handle} exceeds salary cap.')
                        
                        slate_lineup.sim_scores = sim_scores.tolist()
                        slate_lineup.save()

                        slate_lineup = [slate_lineup]
                    elif slate_lineup.count() > 1:
                        raise Exception(f'There were {slate_lineup.count()} duplicate lineups found for {handle} among all possible lineups.')

                    lineup = models.FieldSDLineupToBeat.objects.create(
                        build=build,
                        opponent_handle=handle,
                        slate_lineup=slate_lineup[0]
                    )

                    lineup.median = numpy.median(sim_scores)
                    lineup.s75 = numpy.percentile(sim_scores, 75)
                    lineup.s90 = numpy.percentile(sim_scores, 90)
                    lineup.save()


@shared_task
def process_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        build = models.FindWinnerBuild.objects.get(id=build_id)
        player_sim_scores = {}

        # get the player outcomes
        for p in build.slate.get_projections():
            player_sim_scores[p.slate_player.player_id] = p.sim_scores

        if build.slate.site == 'draftkings':
            if build.slate.is_showdown:
                process_dk_showdown_field_lineups(build, player_sim_scores)
            else:
                process_dk_classic_field_lineups(build, player_sim_scores)
        elif build.slate.site == 'fanduel':
            if build.slate.is_showdown:
                process_fd_showdown_field_lineups(build, player_sim_scores)
            else:
                process_fd_classic_field_lineups(build, player_sim_scores)

        task.status = 'success'
        task.content = f'{build} processed.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error processing your build: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def handle_projection_import(import_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        projection_import = models.SlateProjectionImport.objects.get(id=import_id)

        # delete previous raw projections
        models.SlatePlayerRawProjection.objects.filter(
            projection_site=projection_import.projection_site,
            slate_player__slate=projection_import.slate
        ).delete()

        success_count = 0
        missing_players = []

        if projection_import.url is not None:
            resp = None

            column_headers = models.SheetColumnHeaders.objects.get(
                projection_site=projection_import.projection_site,
                site=projection_import.slate.site,
                use_for_data_feed=True
            )

            with requests.Session() as s:
                headers = []
                if projection_import.headers is not None:
                    headers = json.loads(projection_import.headers)

                req = requests.Request('GET', projection_import.url, headers=headers)
                prepped = s.prepare_request(req)
                resp = s.send(prepped)

                logger.info(projection_import.url)
                logger.info(resp.status_code)

            if resp is not None and resp.status_code < 300:
                if projection_import.content_type == 'csv':
                    csvString = StringIO(resp.text)
                    df = pandas.read_csv(csvString, sep=',')
                elif projection_import.content_type == 'json':
                    if resp.json() is list:
                        df = pandas.read_json(resp.json())
                        logger.info(df)
                    elif projection_import.projection_site == 'rg':
                        data = resp.json().get('data').get('source')
                        df = pandas.DataFrame(list(data.values()))
            else:
                df = None
        else:
            df = pandas.read_csv(projection_import.projection_sheet)

            column_headers = models.SheetColumnHeaders.objects.get(
                projection_site=projection_import.projection_site,
                site=projection_import.slate.site,
                use_for_data_feed=False
            )

            if projection_import.projection_site == 'etr':
                column_headers.column_player_name = df.columns[0]
                column_headers.save()

        if df is not None:
            for index, row in df.iterrows():
                player_name = row[column_headers.column_player_name].strip()

                if player_name is None:
                    continue

                if row[column_headers.column_team] is None or row[column_headers.column_team] == '':
                    continue
                
                try:
                    if row[column_headers.column_team] == 'JAX':
                        team = 'JAC'
                    elif row[column_headers.column_team] == 'LA':
                        team = 'LAR'
                    else:
                        team = row[column_headers.column_team].strip()
                except:
                    continue

                median_projection = row[column_headers.column_median_projection] if column_headers.column_median_projection is not None and row[column_headers.column_median_projection] != '' and not math.isnan(row[column_headers.column_median_projection]) else 0.0
                floor_projection = row[column_headers.column_floor_projection] if column_headers.column_floor_projection is not None and row[column_headers.column_floor_projection] != '' and not math.isnan(row[column_headers.column_floor_projection]) else 0.0
                ceiling_projection = row[column_headers.column_ceiling_projection] if column_headers.column_ceiling_projection is not None and row[column_headers.column_ceiling_projection] != '' and not math.isnan(row[column_headers.column_ceiling_projection]) else 0.0
                rush_att_projection = row[column_headers.column_rush_att_projection] if column_headers.column_rush_att_projection is not None and row[column_headers.column_rush_att_projection] != '' and not math.isnan(row[column_headers.column_rush_att_projection]) else 0.0
                rec_projection = row[column_headers.column_rec_projection] if column_headers.column_rec_projection is not None and row[column_headers.column_rec_projection] != '' and not math.isnan(row[column_headers.column_rec_projection]) else 0.0
                ownership_projection = float(row[column_headers.column_own_projection]) if column_headers.column_own_projection is not None and row[column_headers.column_own_projection] != '' and row[column_headers.column_own_projection] != '-' and not math.isnan(float(row[column_headers.column_own_projection])) else 0.0

                if projection_import.projection_site == 'etr':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, projection_import.slate.site)
                elif projection_import.projection_site == 'etr_sd':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, projection_import.slate.site)
                elif projection_import.projection_site == 'etr_sg':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, projection_import.slate.site)
                elif projection_import.projection_site == 'rg':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, projection_import.slate.site)
                elif projection_import.projection_site == 'awesemo_own':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, projection_import.projection_site)
                elif projection_import.projection_site == 'sabersim':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, projection_import.projection_site)
                else:
                    alias = models.Alias.find_alias(player_name, projection_import.projection_site)
                
                if alias is not None:
                    try:
                        slate_player = models.SlatePlayer.objects.get(
                            slate=projection_import.slate,
                            name=alias.get_alias(projection_import.slate.site),
                            team=team,
                            roster_position__in=['QB', 'RB', 'WR', 'TE', 'DST', 'D', 'DEF', 'FLEX', 'UTIL']
                        )

                        mu = 0.0
                        ceil = 0.0
                        flr = 0.0
                        stdev = 0.0

                        if median_projection is not None and median_projection != '' and median_projection > 0.0:
                            mu = float(median_projection)

                            if floor_projection is not None and ceiling_projection is not None:
                                ceil = float(ceiling_projection)
                                flr = float(floor_projection)

                                stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
                        
                        if projection_import.slate.site == 'yahoo':
                            val = mu / slate_player.salary
                        else:
                            val = mu / (slate_player.salary / 1000)

                        try:
                            models.SlatePlayerRawProjection.objects.create(
                                slate_player=slate_player,
                                projection_site=projection_import.projection_site,
                                projection=mu,
                                value=val,
                                floor=flr,
                                ceiling=ceil,
                                stdev=stdev,
                                ownership_projection=float(ownership_projection) if float(ownership_projection) < 1.0 else float(ownership_projection)/100.0,
                                adjusted_opportunity=float(rec_projection) * 2.75 + float(rush_att_projection) if projection_import.slate.site == 'draftkings' else float(rec_projection) * 2.0 + float(rush_att_projection)
                            )

                            # create captain/mvp version if necessary
                            try:
                                cpt_slate_player = models.SlatePlayer.objects.get(
                                    slate=projection_import.slate,
                                    name=alias.get_alias(projection_import.slate.site),
                                    team=team,
                                    roster_position__in=['CPT', 'MVP']
                                )

                                mu = 0.0
                                ceil = 0.0
                                flr = 0.0
                                stdev = 0.0

                                if median_projection is not None and median_projection != '' and median_projection > 0.0:
                                    mu = float(median_projection) * 1.5

                                    if floor_projection is not None and ceiling_projection is not None:
                                        ceil = float(ceiling_projection) * 1.5
                                        flr = float(floor_projection) * 1.5

                                        stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
                                
                                if projection_import.slate.site == 'yahoo':
                                    val = mu / cpt_slate_player.salary
                                else:
                                    val = mu / (cpt_slate_player.salary / 1000)

                                models.SlatePlayerRawProjection.objects.create(
                                    slate_player=cpt_slate_player,
                                    projection_site=projection_import.projection_site,
                                    projection=mu,
                                    value=val,
                                    floor=flr,
                                    ceiling=ceil,
                                    stdev=stdev,
                                    ownership_projection=float(ownership_projection) if float(ownership_projection) < 1.0 else float(ownership_projection)/100.0,
                                    adjusted_opportunity=float(rec_projection) * 2.75 + float(rush_att_projection) if projection_import.slate.site == 'draftkings' else float(rec_projection) * 2.0 + float(rush_att_projection)
                                )
                            except models.SlatePlayer.DoesNotExist:
                                pass
                                
                            success_count += 1
                        except:
                            logger.info(f'Could not create projection for {slate_player.name} with {projection_import.projection_site}')
                    except models.SlatePlayer.DoesNotExist:
                        pass
                else:
                    missing_players.append(player_name)

        task.status = 'success'
        task.content = '{} projections have been successfully added to {} for {}.'.format(success_count, str(projection_import.slate), projection_import.projection_site) if len(missing_players) == 0 else '{} players have been successfully added to {} for {}. {} players could not be identified.'.format(success_count, str(projection_import.slate), projection_import.projection_site, len(missing_players))
        task.link = '/admin/nfl/missingalias/' if len(missing_players) > 0 else None
        task.save()        

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = 'There was a importing your {} projections: {}'.format(projection_import.projection_site, str(e))
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_projection_sheet(chained_result, sheet_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        sheet = models.SlateProjectionSheet.objects.get(id=sheet_id)
        
        # delete previous base projections (if this is primary projection sheet)
        if sheet.is_primary:
            models.SlatePlayerProjection.objects.filter(
                slate_player__slate=sheet.slate
            ).delete()

        # delete previous raw projections
        models.SlatePlayerRawProjection.objects.filter(
            projection_site=sheet.projection_site,
            slate_player__slate=sheet.slate
        ).delete()

        with open(sheet.projection_sheet.path, mode='r') as projection_file:
            csv_reader = csv.DictReader(projection_file)
            success_count = 0
            missing_players = []

            headers = models.SheetColumnHeaders.objects.get(
                projection_site=sheet.projection_site,
                site=sheet.slate.site
            )

            if sheet.projection_site == 'rts':
                headers.column_player_name = csv_reader.fieldnames[0]
                headers.save()
            elif sheet.projection_site == 'etr':
                headers.column_player_name = csv_reader.fieldnames[0]
                headers.save()

            for row in csv_reader:
                player_name = row[headers.column_player_name].strip()

                if player_name is None:
                    continue

                if row[headers.column_team] == 'JAX':
                    team = 'JAC'
                elif row[headers.column_team] == 'LA':
                    team = 'LAR'
                else:
                    team = row[headers.column_team].strip()

                median_projection = row[headers.column_median_projection] if row[headers.column_median_projection] is not None else 0.0
                floor_projection = row[headers.column_floor_projection] if headers.column_floor_projection is not None and row[headers.column_floor_projection] != '' else 0.0
                ceiling_projection = row[headers.column_ceiling_projection] if headers.column_ceiling_projection is not None and row[headers.column_ceiling_projection] != '' else 0.0
                rush_att_projection = row[headers.column_rush_att_projection] if headers.column_rush_att_projection is not None and row[headers.column_rush_att_projection] != '' else 0.0
                rec_projection = row[headers.column_rec_projection] if headers.column_rec_projection is not None and row[headers.column_rec_projection] != '' else 0.0
                ownership_projection = float(row[headers.column_own_projection]) if headers.column_own_projection is not None and row[headers.column_own_projection] != '' and row[headers.column_own_projection] != '-' else 0.0

                if sheet.projection_site == 'etr':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, sheet.slate.site)
                elif sheet.projection_site == 'rg':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, sheet.slate.site)
                elif sheet.projection_site == 'sabersim':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, sheet.projection_site)
                else:
                    alias = models.Alias.find_alias(player_name, sheet.projection_site)
                
                if alias is not None:
                    try:
                        slate_player = models.SlatePlayer.objects.get(
                            slate=sheet.slate,
                            name=alias.get_alias(sheet.slate.site),
                            team=team
                        )

                        if median_projection != '':
                            mu = float(median_projection)

                            if floor_projection is not None and ceiling_projection is not None:
                                ceil = float(ceiling_projection)
                                flr = float(floor_projection)

                                stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
                            else:
                                ceil = None
                                flr = None
                                stdev = None

                            models.SlatePlayerRawProjection.objects.create(
                                slate_player=slate_player,
                                projection_site=sheet.projection_site,
                                projection=mu,
                                floor=flr,
                                ceiling=ceil,
                                stdev=stdev,
                                ownership_projection=float(ownership_projection) if float(ownership_projection) < 1.0 else float(ownership_projection)/100.0,
                                adjusted_opportunity=float(rec_projection) * 2.75 + float(rush_att_projection) if sheet.slate.site == 'draftkings' else float(rec_projection) * 2.0 + float(rush_att_projection)
                            )
                            
                            success_count += 1
                    except models.SlatePlayer.DoesNotExist:
                        pass
                else:
                    missing_players.append(player_name)

        task.status = 'success'
        task.content = '{} projections have been successfully added to {} for {}.'.format(success_count, str(sheet.slate), sheet.projection_site) if len(missing_players) == 0 else '{} players have been successfully added to {} for {}. {} players could not be identified.'.format(success_count, str(sheet.slate), sheet.projection_site, len(missing_players))
        task.link = '/admin/nfl/missingalias/' if len(missing_players) > 0 else None
        task.save()        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = 'There was a importing your {} projections: {}'.format(sheet.projection_site, str(e))
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def handle_base_projections(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        slate = models.Slate.objects.get(id=slate_id)

        # raw_projections = models.SlatePlayerRawProjection.objects.filter(
        #     slate_player__slate=slate
        # )
        ao_projections = models.SlatePlayerRawProjection.objects.filter(
            slate_player__slate=slate,
            projection_site='4for4'
        )

        # primary_sheet = slate.projections.get(is_primary=True)
        # primary_projections = models.SlatePlayerRawProjection.objects.filter(
        #     slate_player__slate=slate,
        #     projection_site=primary_sheet.projection_site
        # )
        # ao_projections = models.SlatePlayerRawProjection.objects.filter(
        #     slate_player__slate=slate,
        #     projection_site='4for4'
        # )
        
        for slate_player in slate.players.all():
            (projection, _) = models.SlatePlayerProjection.objects.get_or_create(
                slate_player=slate_player
            )

            try:
                raw_projections = slate_player.raw_projections.all()

                try:
                    # primary_projection = primary_projections.get(slate_player=slate_player)
                    ao_projection = ao_projections.get(slate_player=slate_player)
                except models.SlatePlayerRawProjection.DoesNotExist:
                    rg_projections = models.SlatePlayerRawProjection.objects.filter(
                        slate_player=slate_player,
                        projection_site='rg'
                    )
                    if rg_projections.count() > 0:
                        ao_projection = rg_projections[0]
                    else:
                        ao_projection = None

                agg_projs = []
                agg_floors = []
                agg_ceils = []
                agg_stds = []
                agg_owns = []
                
                for proj_import in slate.projection_imports.filter(projection_weight__gt=0.0):
                    s = proj_import.projection_site

                    try:
                        raw_proj = raw_projections.get(projection_site=s)

                        for _ in range(0, int(proj_import.projection_weight * 100)):
                            agg_projs.append(raw_proj.projection)

                        if raw_proj.floor is not None and raw_proj.floor != '':
                            for _ in range(0, int(proj_import.projection_weight * 100)):
                                agg_floors.append(raw_proj.floor)

                        if raw_proj.ceiling is not None and raw_proj.ceiling != '':
                            for _ in range(0, int(proj_import.projection_weight * 100)):
                                agg_ceils.append(raw_proj.ceiling)

                        if raw_proj.stdev is not None and raw_proj.stdev != '':
                            for _ in range(0, int(proj_import.projection_weight * 100)):
                                agg_stds.append(raw_proj.stdev)

                        if raw_proj.ownership_projection is not None and raw_proj.ownership_projection != '':
                            for _ in range(0, int(proj_import.ownership_weight * 100)):
                                agg_owns.append(raw_proj.ownership_projection)
                    except:
                        pass
                    
                    agg_proj = numpy.mean(agg_projs) if len(agg_projs) > 0 else 0.0
                    agg_floor = numpy.mean(agg_floors) if len(agg_floors) > 0 else 0.0
                    agg_ceil = numpy.mean(agg_ceils) if len(agg_ceils) > 0 else 0.0
                    agg_std = numpy.mean(agg_stds) if len(agg_stds) > 0 else 0.0
                    agg_own = numpy.mean(agg_owns) if len(agg_owns) > 0 else 0.0
                
                projection.projection = agg_proj
                projection.balanced_projection = agg_proj
                projection.floor = agg_floor
                projection.ceiling = agg_ceil
                projection.stdev = agg_std
                projection.ownership_projection = agg_own
                projection.adjusted_opportunity=ao_projection.adjusted_opportunity if ao_projection is not None else 0.0
                projection.save()
            except models.SlatePlayerRawProjection.DoesNotExist:
                projection.in_play = False
                projection.save()

        task.status = 'success'
        task.content = 'Base Projections processed.'
        task.save()        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error creating or updated your base projections: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_ownership_sheet(chained_results, sheet_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        sheet = models.SlatePlayerOwnershipProjectionSheet.objects.get(id=sheet_id)
        with open(sheet.sheet.path, mode='r') as projection_file:
            csv_reader = csv.DictReader(projection_file)
            success_count = 0
            missing_players = []

            headers = models.SheetColumnHeaders.objects.get(
                projection_site=sheet.projection_site,
                site=sheet.slate.site
            )

            for row in csv_reader:
                player_name = row[headers.column_player_name].strip()
                if row[headers.column_team] == 'JAX':
                    team = 'JAC'
                elif row[headers.column_team] == 'LA':
                    team = 'LAR'
                else:
                    team = row[headers.column_team].strip()
                ownership_projection = row[headers.column_own_projection] if headers.column_own_projection is not None and row[headers.column_own_projection] != '' else 0.0

                alias = models.Alias.find_alias(player_name, sheet.projection_site)
                
                if alias is not None:
                    try:
                        slate_player = models.SlatePlayer.objects.get(
                            slate=sheet.slate,
                            name=alias.get_alias(sheet.slate.site),
                            team=team
                        )

                        if ownership_projection is not None and ownership_projection != '':
                            (projection, _) = models.SlatePlayerRawProjection.objects.get_or_create(
                                slate_player=slate_player,
                                projection_site=sheet.slate.site
                            )

                            ownership_projection = float(ownership_projection) / 100.0

                            projection.ownership_projection = ownership_projection
                            try:
                                projection.save()
                            except:
                                traceback.print_exc()

                            success_count += 1

                    except models.SlatePlayer.DoesNotExist:
                        pass
                else:
                    missing_players.append(player_name)

        task.status = 'success'
        task.content = '{} ownership projections have been successfully added to {} for {}.'.format(success_count, str(sheet.slate), sheet.projection_site) if len(missing_players) == 0 else '{} ownership projections have been successfully added to {} for {}. {} players could not be identified.'.format(success_count, str(sheet.slate), sheet.projection_site, len(missing_players))
        task.link = '/admin/nfl/missingalias/' if len(missing_players) > 0 else None
        task.save()        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error importing your ownership projections: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_actuals_sheet(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        
        with open(slate.fc_actuals_sheet.path, mode='r') as f:
            csv_reader = csv.DictReader(f)
            success_count = 0
            missing_players = []

            headers = models.SheetColumnHeaders.objects.get(
                projection_site='fc',
                site=slate.site,
                use_for_data_feed=False
            )

            for row in csv_reader:
                player_name = row[headers.column_player_name].strip()
                team = 'JAC' if row[headers.column_team] == 'JAX' else row[headers.column_team].strip()
                actual_ownership = row[headers.column_ownership] if headers.column_ownership is not None and row[headers.column_ownership] != '' else 0.0
                actual_score = row[headers.column_score] if headers.column_score is not None and row[headers.column_score] != '' else 0.0

                alias = models.Alias.find_alias(player_name, 'fc')
                
                if alias is not None:
                    try:
                        slate_player = models.SlatePlayer.objects.get(
                            slate=slate,
                            name=alias.get_alias(slate.site),
                            team=team,
                            roster_position__in=['QB', 'RB', 'WR', 'TE', 'D', 'DST', 'UTIL', 'FLEX']
                        )
                        slate_player.fantasy_points = actual_score
                        slate_player.ownership = actual_ownership
                        slate_player.save()

                        success_count += 1

                        # captain, if necessary
                        slate_player = models.SlatePlayer.objects.get(
                            slate=slate,
                            name=alias.get_alias(slate.site),
                            team=team,
                            roster_position__in=['CPT', 'MVP']
                        )
                        slate_player.fantasy_points = float(actual_score) * 1.5
                        slate_player.save()
                        
                    except models.SlatePlayer.DoesNotExist:
                        pass
                else:
                    missing_players.append(player_name)


        task.status = 'success'
        task.content = '{} player scores have been updated for {}.'.format(success_count, str(slate)) if len(missing_players) == 0 else '{} player scores have been updated for {}. {} players could not be identified.'.format(success_count, str(slate), len(missing_players))
        task.link = '/admin/nfl/missingalias/' if len(missing_players) > 0 else None
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing actuals: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_actual_ownership(slate_id, contest_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        if slate.site == 'fanduel':
            contest = fanduel_models.Contest.objects.get(id=contest_id)
            dst_label = 'D'
        elif slate.site == 'yahoo':
            contest = yahoo_models.Contest.objects.get(id=contest_id)
            dst_label = 'DEF'
        else:
            raise Exception(f'{slate.site} is not supported for processing ownership')

        df_lineups = pandas.DataFrame(contest.get_lineups_as_json())

        df_m = df_lineups.filter(items=['QB', 'RB', 'RB2', 'WR', 'WR2', 'WR3', 'TE', 'FLEX', dst_label]).melt(var_name='columns', value_name='index')
        df_own = pandas.crosstab(index=df_m['index'], columns=df_m['columns']).sum(axis=1)

        for player, player_count in df_own.items():
            player_name = player.split(', ')[0]
            player_team = player.split(', ')[1]
            models.SlatePlayer.objects.filter(
                slate=slate,
                name=player_name,
                team=player_team
            ).update(ownership=numpy.round(player_count/contest.num_entries, 4))

        task.status = 'success'
        task.content = 'Ownership processed'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing ownership: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_field_lineups(slate_id, contest_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        slate.field_lineups.all().delete()

        if slate.site == 'fanduel':
            contest = fanduel_models.Contest.objects.get(id=contest_id)
            dst_label = 'D'
        elif slate.site == 'yahoo':
            contest = yahoo_models.Contest.objects.get(id=contest_id)
            dst_label = 'DEF'
        else:
            raise Exception(f'{slate.site} is not supported for processing lineups')

        df_lineups = contest.get_lineups_as_dataframe()
        for lineup in df_lineups.values:
            try:
                l = models.SlateFieldLineup.objects.create(
                    slate=slate,
                    username=lineup[0],
                    qb=models.SlatePlayerProjection.objects.get(slate_player__slate=slate, slate_player__name=lineup[1]),
                    rb1=models.SlatePlayerProjection.objects.get(slate_player__slate=slate, slate_player__name=lineup[2]),
                    rb2=models.SlatePlayerProjection.objects.get(slate_player__slate=slate, slate_player__name=lineup[3]),
                    wr1=models.SlatePlayerProjection.objects.get(slate_player__slate=slate, slate_player__name=lineup[4]),
                    wr2=models.SlatePlayerProjection.objects.get(slate_player__slate=slate, slate_player__name=lineup[5]),
                    wr3=models.SlatePlayerProjection.objects.get(slate_player__slate=slate, slate_player__name=lineup[6]),
                    te=models.SlatePlayerProjection.objects.get(slate_player__slate=slate, slate_player__name=lineup[7]),
                    flex=models.SlatePlayerProjection.objects.get(slate_player__slate=slate, slate_player__name=lineup[8]),
                    dst=models.SlatePlayerProjection.objects.get(slate_player__slate=slate, slate_player__name=lineup[9]),
                )
                l.simulate()
            except:
                pass

        task.status = 'success'
        task.content = 'Lineups processed'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_sim_datasheets(chained_results, slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        
        if slate.player_outcomes is not None:
            with open(slate.player_outcomes.path, mode='r') as f:
                csv_reader = csv.DictReader(f)
                success_count = 0
                missing_players = []

                for row in csv_reader:
                    player_name = row['X1'].strip()
                    player_salary = int(row['X2'])
                    outcomes = [float(row['X{}'.format(i)]) for i in range(3, 10003)]

                    alias = models.Alias.find_alias(player_name, slate.site)
                    
                    if alias is not None:
                        try:
                            projection = models.SlatePlayerProjection.objects.get(
                                slate_player__slate=slate,
                                slate_player__name=alias.get_alias(slate.site),
                                slate_player__salary=player_salary
                            )

                            projection.sim_scores = outcomes
                            projection.save()

                            success_count += 1
                        except models.SlatePlayerProjection.DoesNotExist:
                            pass
                    else:
                        missing_players.append(player_name)


            task.status = 'success'
            task.content = '{} player simulated outcomes have been updated for {}.'.format(success_count, str(slate)) if len(missing_players) == 0 else '{} player simulated outcomes have been updated for {}. {} players could not be identified.'.format(success_count, str(slate), len(missing_players))
            task.link = '/admin/nfl/missingalias/' if len(missing_players) > 0 else None
            task.save()
        else:
            task.status = 'error'
            task.content = 'There is no sim datasheet for this slate'
            task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing sim datasheets: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def find_slate_games(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        slate = models.Slate.objects.get(id=slate_id)
        slate.find_games()

        task.status = 'success'
        task.content = '{} games found for {}'.format(slate.num_games(), str(slate))
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem finding games for this slate: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def assign_zscores_to_players(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        slate = models.Slate.objects.get(id=slate_id)
        slate.calc_player_zscores('QB')
        slate.calc_player_zscores('RB')
        slate.calc_player_zscores('WR')
        slate.calc_player_zscores('TE')
        if slate.site == 'fanduel':
            slate.calc_player_zscores('D')
        elif slate.site == 'yahoo':
            slate.calc_player_zscores('DEF')
        else:
            slate.calc_player_zscores('DST')

        task.status = 'success'
        task.content = 'Z-Scores calculated.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem assigning z-scores to players for this slate: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def assign_actual_scores_to_stacks(stack_ids, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        stacks = models.SlateBuildStack.objects.filter(id__in=stack_ids)
        limit = 100
        pages = math.ceil(stacks.count()/limit)

        offset = 0

        count = 0
        for page in range(0, pages):
            offset = page * limit

            for stack in stacks[offset:offset+limit]:
                count += 1
                stack.calc_actual_score()
        
        task.status = 'success'
        task.content = 'Actuals assigned for stacks.'
        task.save()        

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem assigning actual scores to stacks: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def sim_outcomes_for_stacks(stack_ids, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        stacks = models.SlateBuildStack.objects.filter(id__in=stack_ids)
        limit = 20
        pages = math.ceil(stacks.count()/limit)

        offset = 0

        count = 0
        for page in range(0, pages):
            offset = page * limit

            for stack in stacks[offset:offset+limit]:
                try:
                    stack.calc_sim_scores()
                    count += 1
                except:
                    traceback.print_exc()
        
        task.status = 'success'
        task.content = 'Calculated simulated outcomes for {} out of {} stacks.'.format(count, len(stack_ids))
        task.save()        

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem simulating outcomes: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def sim_outcomes_for_players(proj_ids, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        projections = models.SlatePlayerProjection.objects.filter(id__in=proj_ids)
        limit = 100
        pages = math.ceil(projections.count()/limit)

        offset = 0
        count = 0
        for page in range(0, pages):
            offset = page * limit

            for proj in projections[offset:offset+limit]:
                try:
                    proj.calc_sim_scores()
                    count += 1
                except:
                    pass
        
        task.status = 'success'
        task.content = 'Calculated simulated outcomes for {} out of {} players.'.format(count, len(proj_ids))
        task.save()        

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem simulating outcomes: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_group_import_sheet(sheet_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        sheet = models.GroupImportSheet.objects.get(id=sheet_id)
        df = pandas.read_csv(sheet.sheet.path, header=None, sep='\n')
        df = df[0].str.split(',', expand=True)

        l = df.values.tolist()
        # create a group for each row
        for row in l[1:]:
            group_type = row[0]
            count = int(row[1])
            name = row[2]
            players = []

            for index, p in enumerate(row):
                if p is None or p == '':
                    break
                if index >= 3:
                    players.append(p)
            
            group = models.SlateBuildGroup.objects.create(
                build=sheet.build,
                name=f'{group_type}{count} - {name}',
                max_from_group=int(count) if group_type == 'AM' else len(players),
                min_from_group=int(count) if group_type == 'AL' else 0
            )

            slate_players = models.SlatePlayer.objects.filter(
                name__in=players,
                slate=sheet.build.slate
            )

            for slate_player in slate_players:
                _ = models.SlateBuildGroupPlayer.objects.create(
                    group=group,
                    slate_player=slate_player
                )

        task.status = 'success'
        task.content = 'Groups imported.'
        task.save()        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error importing your groups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def get_field_lineup_outcomes(lineup, slate_id):
    slate = models.Slate.objects.get(id=slate_id)
    players = models.SlatePlayerProjection.objects.filter(
        slate_player__slate=slate, 
        slate_player__name__in=lineup[1:]
    )
    try:
        outcomes = list([float(sum([p.sim_scores[i] for p in players])) for i in range(0, 10000)])
    except:
        outcomes = list([0.0 for i in range(0, 10000)])
    
    dst_label = 'DST'
    if slate.site == 'fanduel':
        dst_label = 'D'
    elif slate.site == 'yahoo':
        dst_label = 'DEF'

    rbs = players.filter(slate_player__site_pos='RB')
    wrs = players.filter(slate_player__site_pos='WR')
    tes = players.filter(slate_player__site_pos='TE')

    if rbs.count() > 2:
        flex = rbs[2]
    elif wrs.count() > 3:
        flex = wrs[3]
    else:
        flex = tes[1]

    models.SlateFieldLineup.objects.create(
        slate=slate,
        username=lineup[0],
        qb=players.get(slate_player__site_pos='QB'),
        rb1=rbs[0],
        rb2=rbs[1],
        wr1=wrs[0],
        wr2=wrs[1],
        wr3=wrs[2],
        te=tes[0],
        flex=flex,
        dst=players.get(slate_player__site_pos=dst_label),
        sim_scores=outcomes
    )


@shared_task
def get_field_lineup_outcomes_complete(task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
    
        task.status = 'success'
        task.content = 'Field lineup outcomes complete.'
        task.save()      
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error generating field lineup outcomes: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def race_lineups_in_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        build = models.SlateBuild.objects.get(id=build_id)

        if build.slate.site == 'yahoo':
            contests = yahoo_models.Contest.objects.filter(slate_week=build.slate.week.num, slate_year=build.slate.week.slate_year)
            if contests.count() == 0:
                raise Exception('Cannot race. No contests found for this slate.')
            
            contest = contests[0]
            chord(
                [get_lineup_roi.si(lineup.id, build.slate.id, contest.id) for lineup in build.lineups.all()[:1]],
                race_lineups_in_build_complete.si(task_id)
            )()            
        else:
            raise Exception(f'{build.slate.site} is not yet supported for races')  
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error racing lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def race_lineups_in_build_complete(task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
    
        task.status = 'success'
        task.content = 'Slate lineup race complete.'
        task.save()      
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error racing lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def get_lineup_roi(lineup_id, slate_id, contest_id):
    slate = models.Slate.objects.get(id=slate_id)
    lineup = models.SlateBuildLineup.objects.get(id=lineup_id)

    if slate.site == 'yahoo':
        contest = yahoo_models.Contest.objects.get(id=contest_id)
    else:
        raise Exception(f'{slate.site} is not yet supported for races')  

    num_field_lineups = contest.entries.all().count()
    outcomes = list(slate.field_outcomes.all().values_list('sim_scores', flat=True))
    prize_bins = list(contest.prizes.filter(max_rank__lte=num_field_lineups).values_list('max_rank', flat=True))
    prizes = list(contest.prizes.filter(max_rank__lte=num_field_lineups).values_list('prize', flat=True))

    np_outcomes = numpy.array(outcomes)
    np_outcomes.sort(axis=0)
    np_outcomes = np_outcomes[::-1]
    df_field_outcomes = pandas.DataFrame(np_outcomes)
    # df_field_outcomes.to_csv('/opt/lottery/data/df_field_outcomes.csv')
    df_bins = df_field_outcomes.iloc[prize_bins]

    def find_payout(x):
        if x > len(prizes):
            return 0.0
        return float(prizes[int(x)-1])

    df_lineup_outcomes = pandas.DataFrame([lineup.sim_scores])
    # df_lineup_outcomes.to_csv('/opt/lottery/data/df_lineup_outcomes.csv')
    df_ranks = pandas.concat([df_lineup_outcomes, df_bins]).rank(method='min', ascending=False)
    df_payouts = df_ranks.applymap(find_payout)
    df_payouts["sum"] = df_payouts.sum(axis=1, numeric_only=True)

    # now = datetime.datetime.now()
    # timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
    # result_file = f'roi export {timestamp}.csv'
    # result_path = '/opt/lottery/data/'
    # os.makedirs(result_path, exist_ok=True)
    # result_path = os.path.join(result_path, result_file)
    # df_payouts.to_csv(result_path)

    # print(df_payouts)
    roi = (df_payouts.loc[0, "sum"]  - (float(contest.cost * 10000))) / (float(contest.cost * 10000))
    lineup.roi = roi
    lineup.save()
    print(f'ROI = {roi*100}%')
