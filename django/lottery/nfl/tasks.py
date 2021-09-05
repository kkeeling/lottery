import csv
import datetime
import logging
import sys
import time
import traceback

from celery import shared_task
from celery.contrib.abortable import AbortableTask
from celery.utils.log import get_task_logger
from contextlib import contextmanager

from django.db.models.aggregates import Count, Sum

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
def build_lineups_for_stack(stack_id, lineup_number, num_qb_stacks):
    stack = models.SlateBuildStack.objects.get(id=stack_id)
    stack.build_lineups_for_stack(lineup_number, num_qb_stacks)


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
def run_backtest(backtest_id):
    try:
        backtest = models.Backtest.objects.get(id=backtest_id)
        backtest.execute()
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
def run_slate_for_backtest(backtest_slate_id):
    try:
        slate = models.BacktestSlate.objects.get(id=backtest_slate_id)
        slate.execute()
    except Exception as exc:
        traceback.print_exc()
        if slate is not None:
            slate.handle_exception(exc)        


@shared_task
def monitor_backtest(backtest_id):
    start = datetime.datetime.now()
    backtest = models.Backtest.objects.get(id=backtest_id)
    while backtest.status != 'complete':
        backtest.update_status()
        time.sleep(1)

    backtest.elapsed_time = (datetime.datetime.now() - start)
    backtest.save()


@shared_task
def monitor_build(build_id, task_id):
    task = None

    try:
        task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        start = datetime.datetime.now()
        build = models.SlateBuild.objects.get(id=build_id)
        while build.status != 'complete':
            build.update_build_progress()
            time.sleep(1)

        build.analyze_lineups()
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
                'stack_rank',
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
                'top_opp_pass_catchers_for_qb'
            ])

            for lineup in lineups:
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
                    lineup.stack.rank,
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
                    lineup.qb.get_game_total(),
                    lineup.qb.get_team_total(),
                    lineup.rb1.get_game_total(),
                    lineup.rb1.get_team_total(),
                    lineup.rb2.get_game_total(),
                    lineup.rb2.get_team_total(),
                    lineup.wr1.get_game_total(),
                    lineup.wr1.get_team_total(),
                    lineup.wr2.get_game_total(),
                    lineup.wr2.get_team_total(),
                    lineup.wr3.get_game_total(),
                    lineup.wr3.get_team_total(),
                    lineup.te.get_game_total(),
                    lineup.te.get_team_total(),
                    lineup.flex.get_game_total(),
                    lineup.flex.get_team_total(),
                    lineup.dst.get_game_total(),
                    lineup.dst.get_team_total(),
                    lineup.dst.get_spread(),
                    lineup.contains_top_projected_pass_catcher(),
                    lineup.contains_opp_top_projected_pass_catcher()
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