import csv
import datetime
import itertools
import json
import logging
import math
import numpy
import os
import pandas
import pandasql
import random
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


def get_corr_matrix(site):
    if site == 'fanduel' or site == 'yahoo':
        r_df = pandas.read_csv('data/r.csv', index_col=0)
    elif site == 'draftkings':
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

        N = 10000
        if game.slate.site == 'fanduel':
            dst_label = 'D' 
        elif game.slate.site == 'yahoo':
            dst_label = 'DEF' 
        else:
            dst_label = 'DST' 

        r_df = get_corr_matrix(game.slate.site)
        c_target = r_df.to_numpy()
        r0 = [0] * c_target.shape[0]
        mv_norm = scipy.stats.multivariate_normal(mean=r0, cov=c_target)
        rand_Nmv = mv_norm.rvs(N) 
        rand_U = scipy.stats.norm.cdf(rand_Nmv)

        home_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_home_players().values_list('id', flat=True))
        away_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_away_players().values_list('id', flat=True))

        home_qb = home_players.filter(slate_player__site_pos='QB').order_by('-projection', '-slate_player__salary')[0]
        home_rb1 = home_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[0]
        home_rb2 = home_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[1]
        home_rb3 = home_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[2]
        home_wr1 = home_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[0]
        home_wr2 = home_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[1]
        home_wr3 = home_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[2]
        home_wr4 = home_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[3]
        home_wr5 = home_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[4]
        home_te1 = home_players.filter(slate_player__site_pos='TE').order_by('-projection', '-slate_player__salary')[0]
        home_te2 = home_players.filter(slate_player__site_pos='TE').order_by('-projection', '-slate_player__salary')[1]
        home_dst = home_players.filter(slate_player__site_pos=dst_label).order_by('-projection', '-slate_player__salary')[0]

        away_qb = away_players.filter(slate_player__site_pos='QB').order_by('-projection', '-slate_player__salary')[0]
        away_rb1 = away_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[0]
        away_rb2 = away_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[1]
        away_rb3 = away_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[2]
        away_wr1 = away_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[0]
        away_wr2 = away_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[1]
        away_wr3 = away_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[2]
        away_wr4 = away_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[3]
        away_wr5 = away_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[4]
        away_te1 = away_players.filter(slate_player__site_pos='TE').order_by('-projection', '-slate_player__salary')[0]
        away_te2 = away_players.filter(slate_player__site_pos='TE').order_by('-projection', '-slate_player__salary')[1]
        away_dst = away_players.filter(slate_player__site_pos=dst_label).order_by('-projection', '-slate_player__salary')[0]

        home_qb_rv = scipy.stats.gamma((float(home_qb.projection)/float(home_qb.stdev))**2, scale=(float(home_qb.stdev)**2)/float(home_qb.projection))
        home_rb1_rv = scipy.stats.gamma((float(home_rb1.projection)/float(home_rb1.stdev))**2, scale=(float(home_rb1.stdev)**2)/float(home_rb1.projection))
        home_rb2_rv = scipy.stats.gamma((float(home_rb2.projection)/float(home_rb2.stdev))**2, scale=(float(home_rb2.stdev)**2)/float(home_rb2.projection))
        home_rb3_rv = scipy.stats.gamma((float(home_rb3.projection)/float(home_rb3.stdev))**2, scale=(float(home_rb3.stdev)**2)/float(home_rb3.projection))
        home_wr1_rv = scipy.stats.gamma((float(home_wr1.projection)/float(home_wr1.stdev))**2, scale=(float(home_wr1.stdev)**2)/float(home_wr1.projection))
        home_wr2_rv = scipy.stats.gamma((float(home_wr2.projection)/float(home_wr2.stdev))**2, scale=(float(home_wr2.stdev)**2)/float(home_wr2.projection))
        home_wr3_rv = scipy.stats.gamma((float(home_wr3.projection)/float(home_wr3.stdev))**2, scale=(float(home_wr3.stdev)**2)/float(home_wr3.projection))
        home_wr4_rv = scipy.stats.gamma((float(home_wr4.projection)/float(home_wr4.stdev))**2, scale=(float(home_wr4.stdev)**2)/float(home_wr4.projection))
        home_wr5_rv = scipy.stats.gamma((float(home_wr5.projection)/float(home_wr5.stdev))**2, scale=(float(home_wr5.stdev)**2)/float(home_wr5.projection))
        home_te1_rv = scipy.stats.gamma((float(home_te1.projection)/float(home_te1.stdev))**2, scale=(float(home_te1.stdev)**2)/float(home_te1.projection))
        home_te2_rv = scipy.stats.gamma((float(home_te2.projection)/float(home_te2.stdev))**2, scale=(float(home_te2.stdev)**2)/float(home_te2.projection))
        home_dst_rv = scipy.stats.gamma((float(home_dst.projection)/float(home_dst.stdev))**2, scale=(float(home_dst.stdev)**2)/float(home_dst.projection))
        away_qb_rv = scipy.stats.gamma((float(away_qb.projection)/float(away_qb.stdev))**2, scale=(float(away_qb.stdev)**2)/float(away_qb.projection))
        away_rb1_rv = scipy.stats.gamma((float(away_rb1.projection)/float(away_rb1.stdev))**2, scale=(float(away_rb1.stdev)**2)/float(away_rb1.projection))
        away_rb2_rv = scipy.stats.gamma((float(away_rb2.projection)/float(away_rb2.stdev))**2, scale=(float(away_rb2.stdev)**2)/float(away_rb2.projection))
        away_rb3_rv = scipy.stats.gamma((float(away_rb3.projection)/float(away_rb3.stdev))**2, scale=(float(away_rb3.stdev)**2)/float(away_rb3.projection))
        away_wr1_rv = scipy.stats.gamma((float(away_wr1.projection)/float(away_wr1.stdev))**2, scale=(float(away_wr1.stdev)**2)/float(away_wr1.projection))
        away_wr2_rv = scipy.stats.gamma((float(away_wr2.projection)/float(away_wr2.stdev))**2, scale=(float(away_wr2.stdev)**2)/float(away_wr2.projection))
        away_wr3_rv = scipy.stats.gamma((float(away_wr3.projection)/float(away_wr3.stdev))**2, scale=(float(away_wr3.stdev)**2)/float(away_wr3.projection))
        away_wr4_rv = scipy.stats.gamma((float(away_wr4.projection)/float(away_wr4.stdev))**2, scale=(float(away_wr4.stdev)**2)/float(away_wr4.projection))
        away_wr5_rv = scipy.stats.gamma((float(away_wr5.projection)/float(away_wr5.stdev))**2, scale=(float(away_wr5.stdev)**2)/float(away_wr5.projection))
        away_te1_rv = scipy.stats.gamma((float(away_te1.projection)/float(away_te1.stdev))**2, scale=(float(away_te1.stdev)**2)/float(away_te1.projection))
        away_te2_rv = scipy.stats.gamma((float(away_te2.projection)/float(away_te2.stdev))**2, scale=(float(away_te2.stdev)**2)/float(away_te2.projection))
        away_dst_rv = scipy.stats.gamma((float(away_dst.projection)/float(away_dst.stdev))**2, scale=(float(away_dst.stdev)**2)/float(away_dst.projection))

        rand_home_qb = home_qb_rv.ppf(rand_U[:, 0])
        rand_home_rb1 = home_rb1_rv.ppf(rand_U[:, 1])
        rand_home_rb2 = home_rb2_rv.ppf(rand_U[:, 2])
        rand_home_rb3 = home_rb3_rv.ppf(rand_U[:, 3])
        rand_home_wr1 = home_wr1_rv.ppf(rand_U[:, 4])
        rand_home_wr2 = home_wr2_rv.ppf(rand_U[:, 5])
        rand_home_wr3 = home_wr3_rv.ppf(rand_U[:, 6])
        rand_home_wr4 = home_wr4_rv.ppf(rand_U[:, 7])
        rand_home_wr5 = home_wr5_rv.ppf(rand_U[:, 8])
        rand_home_te1 = home_te1_rv.ppf(rand_U[:, 9])
        rand_home_te2 = home_te2_rv.ppf(rand_U[:, 10])
        rand_home_dst = home_dst_rv.ppf(rand_U[:, 11])
        rand_away_qb = away_qb_rv.ppf(rand_U[:, 12])
        rand_away_rb1 = away_rb1_rv.ppf(rand_U[:, 13])
        rand_away_rb2 = away_rb2_rv.ppf(rand_U[:, 14])
        rand_away_rb3 = away_rb3_rv.ppf(rand_U[:, 15])
        rand_away_wr1 = away_wr1_rv.ppf(rand_U[:, 16])
        rand_away_wr2 = away_wr2_rv.ppf(rand_U[:, 17])
        rand_away_wr3 = away_wr3_rv.ppf(rand_U[:, 18])
        rand_away_wr4 = away_wr4_rv.ppf(rand_U[:, 19])
        rand_away_wr5 = away_wr5_rv.ppf(rand_U[:, 20])
        rand_away_te1 = away_te1_rv.ppf(rand_U[:, 21])
        rand_away_te2 = away_te2_rv.ppf(rand_U[:, 22])
        rand_away_dst = away_dst_rv.ppf(rand_U[:, 23])

        df_scores = pandas.DataFrame([
            rand_home_qb,
            rand_home_rb1,
            rand_home_rb2,
            rand_home_rb3,
            rand_home_wr1,
            rand_home_wr2,
            rand_home_wr3,
            rand_home_wr4,
            rand_home_wr5,
            rand_home_te1,
            rand_home_te2,
            rand_home_dst,
            rand_away_qb,
            rand_away_rb1,
            rand_away_rb2,
            rand_away_rb3,
            rand_away_wr1,
            rand_away_wr2,
            rand_away_wr3,
            rand_away_wr4,
            rand_away_wr5,
            rand_away_te1,
            rand_away_te2,
            rand_away_dst,
        ])
        print(game)
        print(df_scores)

        game.game_sim = json.dumps(df_scores.to_json())
        game.save()
        
        # assign outcomes to players
        home_qb.sim_scores = numpy.round(rand_home_qb, 2).tolist()
        home_qb.save()
        home_rb1.sim_scores = numpy.round(rand_home_rb1, 2).tolist()
        home_rb1.save()
        home_rb2.sim_scores = numpy.round(rand_home_rb2, 2).tolist()
        home_rb2.save()
        home_rb3.sim_scores = numpy.round(rand_home_rb3, 2).tolist()
        home_rb3.save()
        home_wr1.sim_scores = numpy.round(rand_home_wr1, 2).tolist()
        home_wr1.save()
        home_wr2.sim_scores = numpy.round(rand_home_wr2, 2).tolist()
        home_wr2.save()
        home_wr3.sim_scores = numpy.round(rand_home_wr3, 2).tolist()
        home_wr3.save()
        home_wr4.sim_scores = numpy.round(rand_home_wr4, 2).tolist()
        home_wr4.save()
        home_wr5.sim_scores = numpy.round(rand_home_wr5, 2).tolist()
        home_wr5.save()
        home_te1.sim_scores = numpy.round(rand_home_te1, 2).tolist()
        home_te1.save()
        home_te2.sim_scores = numpy.round(rand_home_te2, 2).tolist()
        home_te2.save()
        home_dst.sim_scores = numpy.round(rand_home_dst, 2).tolist()
        home_dst.save()
        away_qb.sim_scores = numpy.round(rand_away_qb, 2).tolist()
        away_qb.save()
        away_rb1.sim_scores = numpy.round(rand_away_rb1, 2).tolist()
        away_rb1.save()
        away_rb2.sim_scores = numpy.round(rand_away_rb2, 2).tolist()
        away_rb2.save()
        away_rb3.sim_scores = numpy.round(rand_away_rb3, 2).tolist()
        away_rb3.save()
        away_wr1.sim_scores = numpy.round(rand_away_wr1, 2).tolist()
        away_wr1.save()
        away_wr2.sim_scores = numpy.round(rand_away_wr2, 2).tolist()
        away_wr2.save()
        away_wr3.sim_scores = numpy.round(rand_away_wr3, 2).tolist()
        away_wr3.save()
        away_wr4.sim_scores = numpy.round(rand_away_wr4, 2).tolist()
        away_wr4.save()
        away_wr5.sim_scores = numpy.round(rand_away_wr5, 2).tolist()
        away_wr5.save()
        away_te1.sim_scores = numpy.round(rand_away_te1, 2).tolist()
        away_te1.save()
        away_te2.sim_scores = numpy.round(rand_away_te2, 2).tolist()
        away_te2.save()
        away_dst.sim_scores = numpy.round(rand_away_dst, 2).tolist()
        away_dst.save()

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

    if build.configuration.game_stack_size == 3:
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
def process_slate_players(chained_result, slate_id, task_id):
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
                        player_name = row['Nickname'].replace('Oakland Raiders', 'Las Vegas Raiders').replace('Washington Redskins', 'Washington Football Team')
                        salary = int(row['Salary'])
                        game = row['Game'].replace('@', '_').replace('JAX', 'JAC')
                        team = row['Team']
                    elif slate.site == 'draftkings':
                        if success_count < 8:
                            success_count += 1
                            continue

                        player_id = row[13]
                        site_pos = row[10]
                        player_name = row[12].strip()
                        salary = row[15]
                        game = row[16].replace('@', '_').replace('JAX', 'JAC')
                        game = game[:game.find(' ')]
                        team = 'JAC' if row[17] == 'JAX' else row[17]
                    elif slate.site == 'yahoo':
                        if success_count < 8:
                            success_count += 1
                            continue
                        
                        player_id = row['ID']
                        site_pos = row['Position']
                        player_name = f'{row["First Name"]} {row["Last Name"]}'.replace('Oakland Raiders', 'Las Vegas Raiders').replace('Washington Redskins', 'Washington Football Team').strip()
                        salary = int(row["Salary"])
                        game = row['Game'].replace('@', '_').replace('JAX', 'JAC')
                        team = 'JAC' if row['Team'] == 'JAX' else row['Team']
                elif slate.salaries_sheet_type == 'fantasycruncher':
                    site = 'fc'
                    player_id = uuid.uuid4()
                    if slate.site == 'fanduel' and row['Pos'] == 'DST':
                        site_pos = 'D'
                    elif slate.site == 'yahoo' and row['Pos'] == 'DST':
                        site_pos = 'DEF'
                    else:
                        site_pos = row['Pos']
                    player_name = row['Player'].replace('Oakland Raiders', 'Las Vegas Raiders').replace('Washington Redskins', 'Washington Football Team')
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
                            team=team
                        )
                    except models.SlatePlayer.DoesNotExist:
                        slate_player = models.SlatePlayer(
                            slate=slate,
                            team=team,
                            name=alias.get_alias(slate.site)
                        )

                    slate_player.player_id = player_id
                    slate_player.salary = salary
                    slate_player.site_pos = site_pos
                    # slate_player.game = game
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
        dst_label = slate.dst_label

        start = time.time()
        slate.possible_lineups.all().delete()
        logger.info(f'Deleting lineups took {time.time() - start}s')
        
        start = time.time()
        slate_players = slate.players.filter(projection__in_play=True).order_by('-salary')
        salaries = {}
        for p in slate_players:
            salaries[p.player_id] = p.salary
        logger.info(f'Finding players and salaries took {time.time() - start}s. There are {slate_players.count()} players in the player pool.')

        start = time.time()
        qbs = list(slate.get_projections().filter(
            slate_player__site_pos='QB',
            in_play=True
        ).order_by('-projection').values_list('slate_player__id', flat=True))
        rbs = list(slate.get_projections().filter(
            slate_player__site_pos='RB',
            in_play=True
        ).order_by('-projection').values_list('slate_player__id', flat=True))
        wrs = list(slate.get_projections().filter(
            slate_player__site_pos='WR',
            in_play=True
        ).order_by('-projection').values_list('slate_player__id', flat=True))
        tes = list(slate.get_projections().filter(
            slate_player__site_pos='TE',
            in_play=True
        ).order_by('-projection').values_list('slate_player__id', flat=True))
        dsts = list(slate.get_projections().filter(
            slate_player__site_pos=dst_label,
            in_play=True
        ).order_by('-projection').values_list('slate_player__id', flat=True))
        logger.info(f'Filtering player positions took {time.time() - start}s')

        chord([
            create_lineup_combos_for_qb.si(slate.id, qb, rbs, wrs, tes, dsts, 1000) for qb in qbs
        ], complete_slate_lineups.si(task_id))()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem creating lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def create_lineup_combos_for_qb(slate_id, qb_id, rb_ids, wr_ids, te_ids, dst_ids, num_combos):
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
        
        num_wrs = players.aggregate(num_wrs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='WR'))).get('num_wrs')
        if num_wrs > 4:
            return False
        
        num_rbs = players.aggregate(num_rbs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='RB'))).get('num_rbs')
        if num_rbs > 5:
            return False

        visited = set()
        dup = [x for x in l if x in visited or (visited.add(x) or False)]
        if len(dup) > 0:
            return False

        return True

    slate = models.Slate.objects.get(id=slate_id)
    salary_thresholds = slate.salary_thresholds
    lineups = []

    start = time.time()
    rb_combos = list(itertools.combinations(rb_ids, 2))
    logger.info(f'RB combos took {time.time() - start}s. There are {len(rb_combos)} combinations.')

    start = time.time()
    wr_combos = list(itertools.combinations(wr_ids, 3))
    logger.info(f'WR combos took {time.time() - start}s. There are {len(wr_combos)} combinations.')

    start = time.time()
    for _ in range(0, num_combos):
        l, total_salary = get_random_lineup(slate, qb_id, rb_combos, wr_combos, te_ids, list(rb_ids) + list(wr_ids), dst_ids)

        '''
        TODO: Add additional constraints
            - No duplicate lineups
        '''
        while (total_salary < salary_thresholds[0] or total_salary > salary_thresholds[1] or not is_lineup_valid(slate, l)):
            l, total_salary = get_random_lineup(slate, qb_id, rb_combos, wr_combos, te_ids, list(rb_ids) + list(wr_ids), dst_ids)

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
    logger.info(f'Dataframe took {time.time() - start}s')
    logger.info(df_lineups)

    start = time.time()
    user = settings.DATABASES['default']['USER']
    password = settings.DATABASES['default']['PASSWORD']
    database_name = settings.DATABASES['default']['NAME']
    database_url = 'postgresql://{user}:{password}@db:5432/{database_name}'.format(
        user=user,
        password=password,
        database_name=database_name,
    )

    engine = sqlalchemy.create_engine(database_url, echo=False)
    df_lineups.to_sql('nfl_slatelineup', engine, if_exists='append', index=False)
    logger.info(f'Storage took {time.time() - start}s')


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

                median_projection = row[headers.column_median_projection] if row[headers.column_median_projection] != '' else 0.0
                floor_projection = row[headers.column_floor_projection] if headers.column_floor_projection is not None and row[headers.column_floor_projection] != '' else 0.0
                ceiling_projection = row[headers.column_ceiling_projection] if headers.column_ceiling_projection is not None and row[headers.column_ceiling_projection] != '' else 0.0
                rush_att_projection = row[headers.column_rush_att_projection] if headers.column_rush_att_projection is not None and row[headers.column_rush_att_projection] != '' else 0.0
                rec_projection = row[headers.column_rec_projection] if headers.column_rec_projection is not None and row[headers.column_rec_projection] != '' else 0.0
                ownership_projection = float(row[headers.column_own_projection]) if headers.column_own_projection is not None and row[headers.column_own_projection] != '' else 0.0

                if sheet.projection_site == 'etr':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, sheet.slate.site)
                elif sheet.projection_site == 'rg':
                    ownership_projection /= 100.0
                    alias = models.Alias.find_alias(player_name, sheet.projection_site)
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
                                ownership_projection=float(ownership_projection),
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
def handle_base_projections(chained_results, slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        slate = models.Slate.objects.get(id=slate_id)
        primary_sheet = slate.projections.get(is_primary=True)
        raw_projections = models.SlatePlayerRawProjection.objects.filter(
            slate_player__slate=slate,
            projection_site=primary_sheet.projection_site
        )
        ao_projections = models.SlatePlayerRawProjection.objects.filter(
            slate_player__slate=slate,
            projection_site='4for4'
        )
        
        for slate_player in slate.players.all():
            (projection, _) = models.SlatePlayerProjection.objects.get_or_create(
                slate_player=slate_player
            )

            try:
                raw_projection = raw_projections.get(slate_player=slate_player)

                try:
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

                projection.projection = raw_projection.projection
                projection.balanced_projection = raw_projection.projection
                projection.floor = ao_projection.floor if ao_projection is not None else 0.0
                projection.ceiling = ao_projection.ceiling if ao_projection is not None else 0.0
                projection.stdev = ao_projection.stdev if ao_projection is not None else 0.0
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
                            (projection, created) = models.SlatePlayerProjection.objects.get_or_create(
                                slate_player=slate_player,
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
                site=slate.site
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
                            team=team
                        )
                        slate_player.fantasy_points = actual_score
                        slate_player.ownership = actual_ownership
                        slate_player.save()

                        success_count += 1
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
def assign_zscores_to_players(chained_results, slate_id, task_id):
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
