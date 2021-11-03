import csv
import datetime
from functools import partial
import logging
import math
from django.db.models.expressions import Case, When
import numpy
import pandas
import pandasql
from pydfs_lineup_optimizer import player
import scipy
import sys
import time
import traceback

from celery import shared_task, chord, group
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages.api import success
from django.db.models.aggregates import Count, Sum
from django.db.models import Q, F
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
        contest = build.slate.contests.get(use_for_actuals=True)

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

        # Task implementation goes here

        build = models.SlateBuild.objects.get(id=build_id)

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

        task.status = 'success'
        task.content = 'Groups created.'
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
                            elif player.at_most_one_in_stack and player2.at_most_one_in_stack:
                                continue  # You can't have stacks with 2 same team bobos
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
        # print(stack, stack.projection/total_stack_projection, round(stack.projection/total_stack_projection * qb_lineup_count, 0))
        stack.count = round(max(stack.projection/total_stack_projection * qb_lineup_count, 1), 0)
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
        build.total_lineups = build.stacks.all().aggregate(total=Sum('count')).get('total') 
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

        if settings.DEBUG:
            num_outcomes = 100
        else:
            num_outcomes = 10000

        lineup_limit = 500
        col_limit = 50  # sim columns per call
        pages = math.ceil(num_outcomes/col_limit)  # number of calls to make

        chord([
            chord([analyze_lineup_outcomes.s(
                build.id,
                build.slate.contests.get(use_for_sims=True).id,
                list(build.lineups.all().order_by('id').values_list('id', flat=True))[lineup_page * lineup_limit:(lineup_page * lineup_limit) + lineup_limit],
                col_count * col_limit + 3,  # index min
                (col_count * col_limit + 3) + col_limit,  # index max
                use_optimals
            ) for col_count in range(0, pages)], 
            combine_lineup_outcomes.s(build.id, list(build.lineups.all().order_by('id').values_list('id', flat=True))[lineup_page * lineup_limit:(lineup_page * lineup_limit) + lineup_limit], use_optimals)) for lineup_page in range(0, math.ceil(build.lineups.all().count()/lineup_limit))
        ], analyze_lineup_outcomes_complete.s(build.id, task.id))()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem analyzing lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def analyze_lineup_outcomes(build_id, contest_id, lineup_ids, col_min, col_max, use_optimals=False):
    build = models.SlateBuild.objects.get(id=build_id)
    contest = models.Contest.objects.get(id=contest_id)
    limit = col_max - col_min
    
    if use_optimals:
        all_lineups = build.actuals.filter(id__in=lineup_ids)
    else:
        all_lineups = build.lineups.filter(id__in=lineup_ids)

    lineup_values = pandas.DataFrame(list(all_lineups.values_list(
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

    sim_scores = pandas.read_csv(build.slate.player_outcomes.path, index_col='X1', usecols=['X1'] + ['X{}'.format(i) for i in range(col_min, col_max)])
    sim_scores['X1'] = sim_scores.index
    contest_scores = pandas.read_csv(contest.outcomes_sheet.path, index_col='X2', usecols=['X2'] + ['X{}'.format(i) for i in range(col_min+1, col_max+1)])
    contest_scores['X1'] = contest_scores.index
    contest_scores.columns = ['X{}'.format(i) for i in range(col_min, col_max)] + ['X1']
    sim_scores = sim_scores.append(contest_scores, sort=False, ignore_index=True)

    contest_payouts = pandas.read_csv(contest.outcomes_sheet.path, usecols=['X2', 'X3']).sort_index(ascending=True)

    top_payout_rank = contest_payouts.iloc[0]['X2']
    top_payout = float(contest_payouts.iloc[0]['X3'])
    sql = 'SELECT CASE WHEN SUM(B.x{0}+C.x{0}+D.x{0}+E.x{0}+F.x{0}+G.x{0}+H.x{0}+I.x{0}+J.x{0}) >= T{1}.x{0} THEN {2}'.format(col_min, top_payout_rank, top_payout)
    for payout in contest_payouts.itertuples():
        if payout.X2 == top_payout_rank:
            continue
        sql += ' WHEN SUM(B.x{0}+C.x{0}+D.x{0}+E.x{0}+F.x{0}+G.x{0}+H.x{0}+I.x{0}+J.x{0}) >= T{1}.x{0} THEN {2}'.format(col_min, payout.X2, float(payout.X3))
    sql += ' ELSE 0 END as payout_{}'.format(col_min)
    
    for i in range(1, limit):
        sql += ', CASE WHEN SUM(B.x{0}+C.x{0}+D.x{0}+E.x{0}+F.x{0}+G.x{0}+H.x{0}+I.x{0}+J.x{0}) >= T{1}.x{0} THEN {2}'.format(i+col_min, top_payout_rank, top_payout)
        for payout in contest_payouts.itertuples():
            if payout.X2 == top_payout_rank:
                continue
            sql += ' WHEN SUM(B.x{0}+C.x{0}+D.x{0}+E.x{0}+F.x{0}+G.x{0}+H.x{0}+I.x{0}+J.x{0}) >= T{1}.x{0} THEN {2}'.format(i+col_min, payout.X2, float(payout.X3))
        sql += ' ELSE 0 END as payout_{}'.format(col_min + i)

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
    
    for payout in contest_payouts.itertuples():
        sql += f' LEFT JOIN sim_scores T{payout.X2} ON T{payout.X2}.X1 = \'{payout.X2}\''

    sql += ' GROUP BY A.p1, A.p2, A.p3, A.p4, A.p5, A.p6, A.p7, A.p8, A.p9'
    
    for i in range(0, limit):
        for payout in contest_payouts.itertuples():
            sql += f', T{payout.X2}.x{i+col_min}'

    return pandasql.sqldf(sql, locals()).to_json()


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
def clean_lineups(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        build = models.SlateBuild.objects.get(id=build_id)
        build.clean_lineups()
        # stacks = build.stacks.filter(times_used__gt=0)

        # for stack in stacks:
        #     stack_lineups = stack.lineups.all().order_by('-sim_rating')
        #     for lineup in stack_lineups[stack.count:]:
        #         lineup.delete()        

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

            if build.configuration.use_simulation:
                lineups = build.lineups.all().order_by('-rating')
            else:
                lineups = build.lineups.all().order_by('order_number', '-qb__projection')

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

        lineups_df = pandas.DataFrame.from_records(lineups.values())

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

        lineups_df = pandas.DataFrame.from_records(stacks.values())

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
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing slate players: {e}'
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
                print(f'{sheet.projection_site} -- {row[headers.column_own_projection] if headers.column_own_projection is not None else 0.0}')
                player_name = row[headers.column_player_name].strip()
                team = 'JAC' if row[headers.column_team] == 'JAX' else row[headers.column_team].strip()
                median_projection = row[headers.column_median_projection] if row[headers.column_median_projection] != '' else 0.0
                floor_projection = row[headers.column_floor_projection] if headers.column_floor_projection is not None and row[headers.column_floor_projection] != '' else 0.0
                ceiling_projection = row[headers.column_ceiling_projection] if headers.column_ceiling_projection is not None and row[headers.column_ceiling_projection] != '' else 0.0
                rush_att_projection = row[headers.column_rush_att_projection] if headers.column_rush_att_projection is not None and row[headers.column_rush_att_projection] != '' else 0.0
                rec_projection = row[headers.column_rec_projection] if headers.column_rec_projection is not None and row[headers.column_rec_projection] != '' else 0.0
                ownership_projection = row[headers.column_own_projection] if headers.column_own_projection is not None and row[headers.column_own_projection] != '' else 0.0

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
                                ownership_projection=ownership_projection,
                                adjusted_opportunity=float(rec_projection) * 2.0 + float(rush_att_projection)
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
                    pass

                projection.projection = raw_projection.projection
                projection.balanced_projection = raw_projection.projection
                projection.floor = raw_projection.floor
                projection.ceiling = raw_projection.ceiling
                projection.stdev = raw_projection.stdev
                projection.adjusted_opportunity=ao_projection.adjusted_opportunity if ao_projection is not None else 0.0
                projection.save()
            except models.SlatePlayerRawProjection.DoesNotExist:
                pass

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
