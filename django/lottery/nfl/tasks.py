import datetime
import time
import traceback

from celery import shared_task
from celery.contrib.abortable import AbortableTask
from celery.utils.log import get_task_logger

from . import models
from . import optimize


@shared_task(bind=True, base=AbortableTask)
def optimize_for_stack(self, site, build_id, stack_id, lineup_number, num_qb_stacks):
    try:
        build = models.SlateBuild.objects.get(id=build_id)
        stack = models.SlateBuildStack.objects.get(id=stack_id)

        lineups = optimize.optimize_for_stack(
            site,
            stack,
            build.projections.all(),
            build.slate.teams,
            build.configuration,
            stack.count,
            groups=build.groups.filter(active=True)
        )

        for (index, lineup) in enumerate(lineups):
            print(lineup)
            models.SlateBuildLineup.objects.create(
                build=build,
                stack=stack,
                order_number=lineup_number + (num_qb_stacks * index),
                qb=models.BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[0].id, build=build),
                rb1=models.BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[1].id, build=build),
                rb2=models.BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[2].id, build=build),
                wr1=models.BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[3].id, build=build),
                wr2=models.BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[4].id, build=build),
                wr3=models.BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[5].id, build=build),
                te=models.BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[6].id, build=build),
                flex=models.BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[7].id, build=build),
                dst=models.BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[8].id, build=build),
                salary=lineup.salary_costs,
                projection=lineup.fantasy_points_projection
            )

        stack.times_used = len(lineups)
        stack.save()
    except Exception as exc:
        traceback.print_exc()


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
def run_build(build_id):
    try:
        build = models.SlateBuild.objects.get(id=build_id)
        build.build()
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
def monitor_build(build_id):
    start = datetime.datetime.now()
    build = models.SlateBuild.objects.get(id=build_id)
    while build.status != 'complete':
        build.update_build_progress()
        time.sleep(1)

    build.elapsed_time = (datetime.datetime.now() - start)
    build.save()


@shared_task
def build_optimals(build_id):
    try:
        max_optimals_per_stack = 50

        build = models.SlateBuild.objects.get(id=build_id)
        stacks_with_optimals = build.get_optimal_stacks()

        build.total_optimals = len(stacks_with_optimals) * max_optimals_per_stack
        build.optimals_pct_complete = 0.0
        build.save()

        build.build_optimals(stacks_with_optimals, max_optimals_per_stack)
    except Exception as exc:
        traceback.print_exc()

        build.status = 'error'
        build.error_message = str(exc)
        build.save()
