import csv
import datetime
import logging
import math
import numpy
import pandas
import pandasql
import scipy
import sys
import time
import traceback

from celery import shared_task
from contextlib import contextmanager

from django.contrib.auth.models import User
from django.contrib.messages.api import success
from django.db.models.aggregates import Count, Sum
from django.db.models import Q
from django.db import transaction
from django.urls import reverse_lazy

from configuration.models import BackgroundTask

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


@shared_task
def prepare_projections_for_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        start = datetime.datetime.now()
        build = models.SlateBuild.objects.get(id=build_id)
        build.prepare_projections()

        qbs = build.num_in_play('QB')
        rbs = build.num_in_play('RB')
        wrs = build.num_in_play('WR')
        tes = build.num_in_play('TE')
        dsts = build.num_in_play('D') if build.slate.site == 'fanduel' else build.num_in_play('DST')
        
        task.status = 'success'
        task.content = 'Projections ready for {}: {} qbs in play, {} rbs in play, {} wrs in play, {} tes in play, {} dsts in play'.format(str(build), qbs, rbs, wrs, tes, dsts)
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem preparing projections: {e}'
            task.save()

        if build is not None:
            build.status = 'error'
            build.error_message = str(e)
            build.save()

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
        start = datetime.datetime.now()
        build = models.SlateBuild.objects.get(id=build_id)
        build.prepare_construction()

        task.status = 'success'
        task.content = 'Stacks and groups are ready for {}'.format(str(build))
        task.save()
        
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


@shared_task
def calculate_actuals_for_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here

        build = models.SlateBuild.objects.get(id=build_id)
        contest = build.slate.contests.get(outcomes_sheet__isnull=False)

        top_score = 0
        total_cashes = 0
        total_one_pct = 0
        total_half_pct = 0
        binked = False
        great_build = False

        for stack in build.stacks.all():
            stack.calc_actual_score()

        for lineup in build.lineups.all():
            score = lineup.calc_actual_score()
            top_score = max(top_score, score)
            if score >= contest.mincash_score:
                total_cashes += 1
            if score >= contest.one_pct_score:
                total_one_pct += 1
            if score >= contest.half_pct_score:
                total_half_pct += 1
            if score >= contest.winning_score:
                binked = True
            if score >= contest.great_score:
                great_build = True

        build.top_score = top_score
        build.total_cashes = total_cashes
        build.total_one_pct = total_one_pct
        build.total_half_pct = total_half_pct
        build.great_build = great_build
        build.binked = binked
        build.save()

        task.status = 'success'
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating actuals: {e}'
            task.save()

        if build is not None:
            build.status = 'error'
            build.error_message = str(e)
            build.save()

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
def create_stacks_for_qb(build_id, qb_id, total_qb_projection):
    build = models.SlateBuild.objects.get(pk=build_id)
    qb = models.BuildPlayerProjection.objects.get(pk=qb_id)

    qb_lineup_count = round(qb.projection/total_qb_projection * build.total_lineups)
    d_label = 'D' if build.slate.site == 'fanduel' else 'DST'

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
        Q(Q(stack_only=True) | Q(at_most_one_in_stack=True))
    )
    team_has_all_stack_only = (am1_players.count() == team_players.count())

    if build.configuration.game_stack_size == 3:
        # For each player, loop over opposing player to make a group for each possible stack combination
        count = 0
        for (index, player) in enumerate(team_players):
            if len(build.configuration.opp_qb_stack_positions) > 0:
                for opp_player in opp_players:
                    count += 1

                    # add mini stacks if configured
                    if build.configuration.use_super_stacks:
                        for team in build.slate.teams:
                            if team == qb.slate_player.team or team == qb.slate_player.get_opponent():
                                continue
                        
                            for (idx, mini_player_1) in enumerate(build.projections.filter(slate_player__slate_game__zscore__gte=0.0, slate_player__team=team, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')):
                                for mini_player_2 in build.projections.filter(slate_player__slate_game__zscore__gte=0.0, slate_player__team=team, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')[idx+1:]:
                                    stack = models.SlateBuildStack(
                                        build=build,
                                        game=qb.game,
                                        mini_game=mini_player_1.game,
                                        build_order=count,
                                        qb=qb,
                                        player_1=player,
                                        opp_player=opp_player,
                                        mini_player_1=mini_player_1,
                                        mini_player_2=mini_player_2,
                                        salary=sum(p.slate_player.salary for p in [qb, player, opp_player, mini_player_1, mini_player_2]),
                                        projection=sum(p.projection for p in [qb, player, opp_player, mini_player_1, mini_player_2])
                                    )

                                    if build.stack_construction is not None:
                                        stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)

                                    # check stack construction rules; if not all are satisfied, do not save this stack
                                    if build.stack_construction is None or build.stack_construction.passes_rule(stack):
                                        stack.save()
                    else:
                        stack = models.SlateBuildStack(
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
                            stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)

                        # check stack construction rules; if not all are satisfied, do not save this stack
                        if build.stack_construction is None or build.stack_construction.passes_rule(stack):
                            stack.save()
            else:
                for player2 in team_players[index+1:]:
                    count += 1

                    # add mini stacks if configured
                    if build.configuration.use_super_stacks:
                        for team in build.slate.teams:
                            if team == qb.slate_player.team:
                                continue
                        
                            for (idx, mini_player_1) in enumerate(build.projections.filter(slate_player__slate_game__zscore__gte=0.0, slate_player__team=team, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')):
                                for mini_player_2 in build.projections.filter(slate_player__slate_game__zscore__gte=0.0, slate_player__team=team, in_play=True, slate_player__site_pos__in=['RB', 'WR', 'TE']).order_by('-projection', 'slate_player__site_pos')[idx+1:]:
                                    stack = models.SlateBuildStack(
                                        build=build,
                                        game=qb.game,
                                        mini_game=mini_player_1.game,
                                        build_order=count,
                                        qb=qb,
                                        player_1=player,
                                        player_2=player2,
                                        mini_player_1=mini_player_1,
                                        mini_player_2=mini_player_2,
                                        salary=sum(p.slate_player.salary for p in [qb, player, player2, mini_player_1, mini_player_2]),
                                        projection=sum(p.projection for p in [qb, player, player2, mini_player_1, mini_player_2])
                                    )

                                    if build.stack_construction is not None:
                                        stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)

                                    # check stack construction rules; if not all are satisfied, do not save this stack
                                    if build.stack_construction is None or build.stack_construction.passes_rule(stack):
                                        stack.save()
                    else:
                        stack = models.SlateBuildStack(
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
                            stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)

                        # check stack construction rules; if not all are satisfied, do not save this stack
                        if build.stack_construction is None or build.stack_construction.passes_rule(stack):
                            stack.save()

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
                            elif player.at_most_one_in_stack and player2.at_most_one_in_stack:
                                continue  # You can't have stacks with 2 same team bobos
                            else:
                                count += 1
                                mu = float(sum(p.projection for p in [qb, player, player2, opp_player]))
                                stack = models.SlateBuildStack(
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
                                    stack.contains_top_pc = stack.contains_top_projected_pass_catcher(build.stack_construction.top_pc_margin)

                                # check stack construction rules; if not all are satisfied, do not save this stack
                                if build.stack_construction is None or build.stack_construction.passes_rule(stack):
                                    stack.save()                        

    total_stack_projection = models.SlateBuildStack.objects.filter(build=build, qb=qb).aggregate(total_projection=Sum('projection')).get('total_projection')
    for stack in models.SlateBuildStack.objects.filter(build=build, qb=qb):
        print(stack, stack.projection/total_stack_projection, round(stack.projection/total_stack_projection * qb_lineup_count, 0))
        stack.count = round(max(stack.projection/total_stack_projection * qb_lineup_count, 1), 0)
        stack.save()

        
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
def monitor_build(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        start = datetime.datetime.now()
        build = models.SlateBuild.objects.get(id=build_id)
        while build.status != 'complete':
            build.update_build_progress()
            time.sleep(1)

        # build.analyze_lineups()
        build.elapsed_time = (datetime.datetime.now() - start)
        build.save()

        task.status = 'success'
        task.content = '{} lineups ready from {} unique stacks. Download with Export button.'.format(build.num_lineups_created(), build.stacks.filter(count__gt=0).count())
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem running your build: {e}'
            task.save()

        if build is not None:
            build.status = 'error'
            build.error_message = str(e)
            build.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def analyze_lineups(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)
        build.analyze_lineups()

        task.status = 'success'
        task.content = 'Lineups analyzed.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem analyzing lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


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
def analyze_lineups_page(build_id, contest_id, lineup_ids, use_optimals=False):
    build = models.SlateBuild.objects.get(id=build_id)
    contest = models.Contest.objects.get(id=contest_id)
    prizes = contest.prizes.all().order_by('prize')
    
    if use_optimals:
        lineups = build.actuals.filter(id__in=lineup_ids)
    else:
        lineups = build.lineups.filter(id__in=lineup_ids)

    lineup_values = pandas.DataFrame(list(lineups.values_list(
        'qb__slate_player__name',
        'rb1__slate_player__name',
        'rb2__slate_player__name',
        'wr1__slate_player__name',
        'wr2__slate_player__name',
        'wr3__slate_player__name',
        'te__slate_player__name',
        'flex__slate_player__name',
        'dst__slate_player__name')), 
        columns=[
            'p1',
            'p2',
            'p3',
            'p4',
            'p5',
            'p6',
            'p7',
            'p8',
            'p9',
        ]
    )

    limit = 50
    pages = math.ceil(10000/limit)
    result = None

    for col_count in range(0, pages):
        col_min = col_count * limit + 3
        col_max = col_min + limit

        sim_scores = pandas.read_csv(build.slate.player_outcomes.path, index_col='X1', usecols=['X1'] + ['X{}'.format(i) for i in range(col_min, col_max)])
        sim_scores['X1'] = sim_scores.index
        contest_scores = pandas.read_csv(contest.outcomes_sheet.path, index_col='X2', usecols=['X2'] + ['X{}'.format(i) for i in range(col_min, col_max)])
        contest_scores['X1'] = contest_scores.index
        sim_scores = sim_scores.append(contest_scores, sort=False, ignore_index=True)

        sql = 'SELECT CASE WHEN SUM(B.x{0}+C.x{0}+D.x{0}+E.x{0}+F.x{0}+G.x{0}+H.x{0}+I.x{0}+J.x{0}) <= T{1}.x{0} THEN {2}'.format(col_min, prizes[0].max_rank + 1, -float(contest.cost))
        for prize in prizes:
            sql += ' WHEN SUM(B.x{0}+C.x{0}+D.x{0}+E.x{0}+F.x{0}+G.x{0}+H.x{0}+I.x{0}+J.x{0}) <= T{1}.x{0} THEN {2}'.format(col_min, prize.min_rank, (float(prize.prize)-float(contest.cost)))
        sql += ' END as payout_{}'.format(0)

        for i in range(1, limit):
            sql += ', CASE WHEN SUM(B.x{0}+C.x{0}+D.x{0}+E.x{0}+F.x{0}+G.x{0}+H.x{0}+I.x{0}+J.x{0}) <= T{1}.x{0} THEN {2}'.format(i+col_min, prizes[0].max_rank + 1, -float(contest.cost))
            for prize in prizes:
                sql += ' WHEN SUM(B.x{0}+C.x{0}+D.x{0}+E.x{0}+F.x{0}+G.x{0}+H.x{0}+I.x{0}+J.x{0}) <= T{1}.x{0} THEN {2}'.format(i+col_min, prize.min_rank, (float(prize.prize)-float(contest.cost)))
            sql += ' END as payout_{}'.format(i)

        sql += ' FROM lineup_values A'
        sql += ' LEFT JOIN sim_scores B ON B.X1 = A.p1'
        sql += ' LEFT JOIN sim_scores C ON C.X1 = A.p2'
        sql += ' LEFT JOIN sim_scores D ON D.X1 = A.p3'
        sql += ' LEFT JOIN sim_scores E ON E.X1 = A.p4'
        sql += ' LEFT JOIN sim_scores F ON F.X1 = A.p5'
        sql += ' LEFT JOIN sim_scores G ON G.X1 = A.p6'
        sql += ' LEFT JOIN sim_scores H ON H.X1 = A.p7'
        sql += ' LEFT JOIN sim_scores I ON I.X1 = A.p8'
        sql += ' LEFT JOIN sim_scores J ON J.X1 = A.p9'
        
        for prize in prizes:
            sql += ' LEFT JOIN sim_scores T{0} ON T{0}.X1 = \'{0}\''.format(prize.max_rank + 1)
        sql += ' LEFT JOIN sim_scores T1 ON T1.X1 = \'1\''

        sql += ' GROUP BY A.p1, A.p2, A.p3, A.p4, A.p5, A.p6, A.p7, A.p8, A.p9'
        
        for i in range(0, limit):
            for prize in prizes:
                sql += ', T{0}.x{1}'.format(prize.max_rank + 1, i+col_min)
        
            sql += ', T1.x{}'.format(i+col_min)

        if result is None:
            result = pandasql.sqldf(sql, locals())
        else:
            result = pandas.concat([result, pandasql.sqldf(sql, locals())], axis=1)

    ev_result = (result * (1/10000)).sum(axis=1)
    std_result = result.std(axis=1)

    with transaction.atomic():
        for index, lineup in enumerate(lineups):
            lineup.ev = ev_result[index]
            lineup.std = std_result[index]
            lineup.save()

    # return [ev_result.tolist(), var_result.tolist(), mean_result.tolist()]


@shared_task
def build_optimals_for_stack(stack_id):
    try:
        max_optimals_per_stack = 50
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
def simulate_slate(slate_id):
    slate = models.Slate.objects.get(pk=slate_id)
    slate.simulate()


@shared_task
def simulate_contest(contest_id):
    contest = models.Contest.objects.get(pk=contest_id)
    contest.simulate()


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

            for lineup in build.lineups.all().order_by('order_number', '-qb__projection'):
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
def export_optimal_lineups(lineup_ids, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        lineups = models.SlateBuildActualsLineup.objects.filter(id__in=lineup_ids)

        with open(result_path, 'w') as temp_csv:
            lineup_writer = csv.writer(temp_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            lineup_writer.writerow([
                'slate', 
                'week',
                'qb', 
                'rb', 
                'rb', 
                'wr', 
                'wr',
                'wr', 
                'te', 
                'flex', 
                'dst', 
                'score',
                'salary',
                'flex_pos',
                'qb_game', 
                'rb_game', 
                'rb_game', 
                'wr_game', 
                'wr_game',
                'wr_game', 
                'te_game', 
                'flex_game', 
                'dst_game', 
                'qb_game_zscore', 
                'rb_game_zscore', 
                'rb_game_zscore', 
                'wr_game_zscore', 
                'wr_game_zscore',
                'wr_game_zscore', 
                'te_game_zscore', 
                'flex_game_zscore', 
                'dst_game_zscore', 
                'qb_team', 
                'rb_team', 
                'rb_team', 
                'wr_team', 
                'wr_team',
                'wr_team', 
                'te_team', 
                'flex_team', 
                'dst_team', 
                'qb_opponent', 
                'rb_opponent', 
                'rb_opponent', 
                'wr_opponent', 
                'wr_opponent',
                'wr_opponent', 
                'te_opponent', 
                'flex_opponent', 
                'dst_opponent', 
                'qb_salary', 
                'rb_salary', 
                'rb_salary', 
                'wr_salary', 
                'wr_salary',
                'wr_salary', 
                'te_salary', 
                'flex_salary', 
                'dst_salary', 
                'qb_projection', 
                'rb_projection', 
                'rb_projection', 
                'wr_projection', 
                'wr_projection',
                'wr_projection', 
                'te_projection', 
                'flex_projection', 
                'dst_projection', 
                'qb_z', 
                'rb_z', 
                'rb_z', 
                'wr_z', 
                'wr_z',
                'wr_z', 
                'te_z', 
                'flex_z', 
                'dst_z', 
                'rb_ao_z', 
                'rb_ao_z', 
                'flex_ao_z', 
                'qb_actual', 
                'rb_actual', 
                'rb_actual', 
                'wr_actual', 
                'wr_actual',
                'wr_actual', 
                'te_actual', 
                'flex_actual', 
                'dst_actual', 
                'qb_rank', 
                'rb_rank', 
                'rb_rank', 
                'wr_rank', 
                'wr_rank',
                'wr_rank', 
                'te_rank', 
                'flex_rank', 
                'dst_rank',
                'qb_game_total',
                'qb_team_total',
                'rb_game_total',
                'rb_team_total',
                'rb_game_total',
                'rb_team_total',
                'wr_game_total',
                'wr_team_total',
                'wr_game_total',
                'wr_team_total',
                'wr_game_total',
                'wr_team_total',
                'te_game_total',
                'te_team_total',
                'flex_game_total',
                'flex_team_total',
                'dst_game_total',
                'dst_team_total',
                'dst_spread',
                'top_pass_catcher_for_qb',
                'top_opp_pass_catchers_for_qb',
                'main_stack',
                'main_stack_game',
                'main_stack_game_zscore',
                'main_stack_projection_rank',
                'main_stack_projection_zscore',
                'mini_stack_game',
                'mini_stack_game_zscore',
            ])

            limit = 500
            pages = math.ceil(lineups.count()/limit)

            offset = 0

            count = 0
            for page in range(0, pages):
                offset = page * limit

                for lineup in lineups[offset:offset+limit]:
                    count += 1
                    lineup_writer.writerow([
                        lineup.build.slate.name,
                        lineup.build.slate.week,
                        lineup.qb.name,
                        lineup.rb1.name,
                        lineup.rb2.name,
                        lineup.wr1.name,
                        lineup.wr2.name,
                        lineup.wr3.name,
                        lineup.te.name,
                        lineup.flex.name,
                        lineup.dst.name,
                        lineup.actual,
                        lineup.salary,
                        lineup.flex.slate_player.site_pos,
                        lineup.qb.game,
                        lineup.rb1.game,
                        lineup.rb2.game,
                        lineup.wr1.game,
                        lineup.wr2.game,
                        lineup.wr3.game,
                        lineup.te.game,
                        lineup.flex.game,
                        lineup.dst.game,
                        lineup.qb.game.zscore,
                        lineup.rb1.game.zscore,
                        lineup.rb2.game.zscore,
                        lineup.wr1.game.zscore,
                        lineup.wr2.game.zscore,
                        lineup.wr3.game.zscore,
                        lineup.te.game.zscore,
                        lineup.flex.game.zscore,
                        lineup.dst.game.zscore,
                        lineup.qb.team,
                        lineup.rb1.team,
                        lineup.rb2.team,
                        lineup.wr1.team,
                        lineup.wr2.team,
                        lineup.wr3.team,
                        lineup.te.team,
                        lineup.flex.team,
                        lineup.dst.team,
                        lineup.qb.get_opponent(),
                        lineup.rb1.get_opponent(),
                        lineup.rb2.get_opponent(),
                        lineup.wr1.get_opponent(),
                        lineup.wr2.get_opponent(),
                        lineup.wr3.get_opponent(),
                        lineup.te.get_opponent(),
                        lineup.flex.get_opponent(),
                        lineup.dst.get_opponent(),
                        lineup.qb.salary,
                        lineup.rb1.salary,
                        lineup.rb2.salary,
                        lineup.wr1.salary,
                        lineup.wr2.salary,
                        lineup.wr3.salary,
                        lineup.te.salary,
                        lineup.flex.salary,
                        lineup.dst.salary,
                        lineup.qb.projection,
                        lineup.rb1.projection,
                        lineup.rb2.projection,
                        lineup.wr1.projection,
                        lineup.wr2.projection,
                        lineup.wr3.projection,
                        lineup.te.projection,
                        lineup.flex.projection,
                        lineup.dst.projection,
                        lineup.qb.zscore,
                        lineup.rb1.zscore,
                        lineup.rb2.zscore,
                        lineup.wr1.zscore,
                        lineup.wr2.zscore,
                        lineup.wr3.zscore,
                        lineup.te.zscore,
                        lineup.flex.zscore,
                        lineup.dst.zscore,
                        lineup.rb1.ao_zscore,
                        lineup.rb2.ao_zscore,
                        lineup.flex.ao_zscore,
                        lineup.qb.slate_player.fantasy_points,
                        lineup.rb1.slate_player.fantasy_points,
                        lineup.rb2.slate_player.fantasy_points,
                        lineup.wr1.slate_player.fantasy_points,
                        lineup.wr2.slate_player.fantasy_points,
                        lineup.wr3.slate_player.fantasy_points,
                        lineup.te.slate_player.fantasy_points,
                        lineup.flex.slate_player.fantasy_points,
                        lineup.dst.slate_player.fantasy_points,
                        lineup.qb.position_rank,
                        lineup.rb1.position_rank,
                        lineup.rb2.position_rank,
                        lineup.wr1.position_rank,
                        lineup.wr2.position_rank,
                        lineup.wr3.position_rank,
                        lineup.te.position_rank,
                        lineup.flex.position_rank,
                        lineup.dst.position_rank,
                        lineup.qb.game_total,
                        lineup.qb.team_total,
                        lineup.rb1.game_total,
                        lineup.rb1.team_total,
                        lineup.rb2.game_total,
                        lineup.rb2.team_total,
                        lineup.wr1.game_total,
                        lineup.wr1.team_total,
                        lineup.wr2.game_total,
                        lineup.wr2.team_total,
                        lineup.wr3.game_total,
                        lineup.wr3.team_total,
                        lineup.te.game_total,
                        lineup.te.team_total,
                        lineup.flex.game_total,
                        lineup.flex.team_total,
                        lineup.dst.game_total,
                        lineup.dst.team_total,
                        lineup.dst.spread,
                        lineup.contains_top_projected_pass_catcher(),
                        lineup.contains_opp_top_projected_pass_catcher(),
                        str(lineup.stack),
                        lineup.stack.game.game if lineup.stack.game is not None else None,
                        lineup.stack.game.zscore if lineup.stack.game is not None else None,
                        lineup.stack.rank,
                        lineup.stack.projection_zscore,
                        lineup.stack.mini_game.game if lineup.stack.mini_game is not None else None,
                        lineup.stack.mini_game.zscore if lineup.stack.mini_game is not None else None,
                    ])

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

        with open(result_path, 'w') as temp_csv:
            lineup_writer = csv.writer(temp_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            lineup_writer.writerow([
                'id',
                'qb', 
                'p1',
                'p2', 
                'opp_p1', 
                'sal', 
                'proj', 
                'actual'
            ])

            limit = 100
            pages = math.ceil(stacks.count()/limit)

            offset = 0

            count = 0
            for page in range(0, pages):
                offset = page * limit

                for stack in stacks[offset:offset+limit]:
                    count += 1
                    lineup_writer.writerow([
                        stack.id,
                        stack.qb.name,
                        stack.player_1.name,
                        stack.player_2.name,
                        stack.opp_player.name,
                        stack.salary,
                        stack.projection,
                        stack.actual
                    ])

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
            if slate.site == 'fanduel':
                csv_reader = csv.DictReader(salaries_file)
            else:
                csv_reader = csv.reader(salaries_file, delimiter=',')
            success_count = 0
            missing_players = []

            for row in csv_reader:
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

                alias = models.Alias.find_alias(player_name, slate.site)
                
                if alias is not None:
                    try:
                        slate_player = models.SlatePlayer.objects.get(
                            player_id=player_id,
                            slate=slate,
                            name=alias.get_alias(slate.site),
                            team=team
                        )
                    except models.SlatePlayer.DoesNotExist:
                        slate_player = models.SlatePlayer(
                            player_id=player_id,
                            slate=slate,
                            team=team,
                            name=alias.get_alias(slate.site)
                        )

                    slate_player.salary = salary
                    slate_player.site_pos = site_pos
                    slate_player.game = game
                    slate_player.slate_game = slate_player.get_slate_game()
                    slate_player.save()

                    success_count += 1
                else:
                    missing_players.append(player_name)


        task.status = 'success'
        task.content = '{} players have been successfully added to {}.'.format(success_count, str(slate)) if len(missing_players) == 0 else '{} players have been successfully added to {}. {} players could not be identified.'.format(success_count, str(slate), len(missing_players))
        task.link = '/admin/nfl/missingalias/' if len(missing_players) > 0 else None
        task.save()

        for projection_sheet in slate.projections.all():
            task_proj = BackgroundTask()
            task_proj.name = 'Processing Projections'
            task_proj.user = task.user
            task_proj.save()

            process_projection_sheet.delay(projection_sheet.id, task_proj.id)
        
        if hasattr(slate, 'ownership_projections_sheets'):
            task_own_proj = BackgroundTask()
            task_own_proj.name = 'Processing Ownership Projections'
            task_own_proj.user = task.user
            task_own_proj.save()

            process_ownership_sheet.delay(slate.ownership_projections_sheets.id, task_own_proj.id)

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing slate players: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_projection_sheet(sheet_id, task_id):
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
                team = 'JAC' if row[headers.column_team] == 'JAX' else row[headers.column_team].strip()
                median_projection = row[headers.column_median_projection] if row[headers.column_median_projection] != '' else 0.0
                floor_projection = row[headers.column_floor_projection] if headers.column_floor_projection is not None and row[headers.column_floor_projection] != '' else 0.0
                ceiling_projection = row[headers.column_ceiling_projection] if headers.column_ceiling_projection is not None and row[headers.column_ceiling_projection] != '' else 0.0
                rush_att_projection = row[headers.column_rush_att_projection] if headers.column_rush_att_projection is not None and row[headers.column_rush_att_projection] != '' else 0.0
                rec_projection = row[headers.column_rec_projection] if headers.column_rec_projection is not None and row[headers.column_rec_projection] != '' else 0.0

                if sheet.projection_site == 'etr':
                    alias = models.Alias.find_alias(player_name, sheet.slate.site)
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
                                adjusted_opportunity=float(rec_projection) * 2.0 + float(rush_att_projection)                            
                            )
                            
                            success_count += 1

                            # if this sheet is primary (4for4, likely) then duplicate the projection data to SlatePlayerProjection model instance
                            if sheet.is_primary or sheet.projection_site == '4for4':
                                (projection, _) = models.SlatePlayerProjection.objects.get_or_create(
                                    slate_player=slate_player
                                )

                                if sheet.is_primary:
                                    projection.projection = mu
                                    projection.balanced_projection = mu
                                    projection.floor = flr
                                    projection.ceiling = ceil
                                    projection.stdev = stdev
                                
                                # 4for4 is only site with adjusted opportunity components, so must use even if not primary
                                if sheet.projection_site == '4for4':
                                    projection.adjusted_opportunity=float(rec_projection) * 2.0 + float(rush_att_projection)

                                projection.save()

                    except models.SlatePlayer.DoesNotExist:
                        pass
                else:
                    missing_players.append(player_name)

        task.status = 'success'
        task.content = '{} projections have been successfully added to {} for {}.'.format(success_count, str(sheet.slate), sheet.projection_site) if len(missing_players) == 0 else '{} players have been successfully added to {} for {}. {} players could not be identified.'.format(success_count, str(sheet.slate), sheet.projection_site, len(missing_players))
        task.link = '/admin/nfl/missingalias/' if len(missing_players) > 0 else None
        task.save()        

        if sheet.is_primary:
            task2 = BackgroundTask()
            task2.name = 'Find Z-Scores for Players'
            task2.user = task.user
            task2.save()

            assign_zscores_to_players.delay(sheet.slate.id, task2.id)

            task3 = BackgroundTask()
            task3.name = 'Process Sim Data Sheets'
            task3.user = task.user
            task3.save()

            process_sim_datasheets.delay(sheet.slate.id, task3.id)
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = 'There was a importing your {} projections: {}'.format(sheet.projection_site, str(e))
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_ownership_sheet(sheet_id, task_id):
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
                player_name = row[headers.column_player_name]
                team = 'JAC' if row[headers.column_team] == 'JAX' else row[headers.column_team]
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
                            (projection, _) = models.SlatePlayerProjection.objects.get_or_create(
                                slate_player=slate_player,
                            )

                            ownership_projection = float(ownership_projection) / 100.0

                            projection.ownership_projection = ownership_projection
                            projection.save()

                            success_count += 1

                    except models.SlatePlayer.DoesNotExist:
                        pass
                else:
                    missing_players.append(player_name)

        for game in sheet.slate.games.all():
            game.calc_ownership()

        own_totals = list(sheet.slate.games.all().values_list('ownership', flat=True))
        game_own_zscores = scipy.stats.zscore(own_totals)
        for (index, game) in enumerate(sheet.slate.games.all()):
            game.ownership_zscore = game_own_zscores[index]
            game.save()

            # game.calc_rating()

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
def process_sim_datasheets(slate_id, task_id):
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
            task.content = f'There is no sim datasheet for this slate: {e}'
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

        task2 = BackgroundTask()
        task2.name = 'Process Slate Players'
        task2.user = task.user
        task2.save()

        process_slate_players.delay(slate_id, task2.id)

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
