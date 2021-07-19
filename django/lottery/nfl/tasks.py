import datetime
import time
import traceback

from celery import shared_task
from celery.utils.log import get_task_logger

from . import models


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
        time.sleep(5)

    backtest.elapsed_time = (datetime.datetime.now() - start)
    backtest.save()


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
