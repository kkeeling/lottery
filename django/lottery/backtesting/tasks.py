from ast import alias
import csv
import logging
import numpy
import pandas
import re
import sys
import time

from celery import shared_task, chord
from contextlib import contextmanager


from configuration.models import BackgroundTask
from . import models

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
def process_contest_entry(entry_id, entry_name, lineup_str, lineup, contest_id):
    contest = models.Contest.objects.get(id=contest_id)

    alias1 = lineup[0].strip().replace('á', 'a')
    player1 = models.ContestEntryPlayer.objects.get(
        contest=contest,
        name__startswith=alias1
    )

    # lineup list has emptry string as first elemenet
    if len(lineup) > 1:
        alias2 = lineup[1].strip().replace('á', 'a')
        player2 = models.ContestEntryPlayer.objects.get(
            contest=contest,
            name__startswith=alias2
        )
    if len(lineup) > 2:
        alias3 = lineup[2].strip().replace('á', 'a')
        player3 = models.ContestEntryPlayer.objects.get(
            contest=contest,
            name__startswith=alias3
        )
    if len(lineup) > 3:
        alias4 = lineup[3].strip().replace('á', 'a')
        player4 = models.ContestEntryPlayer.objects.get(
            contest=contest,
            name__startswith=alias4
        )
    if len(lineup) > 4:
        alias5 = lineup[4].strip().replace('á', 'a')
        player5 = models.ContestEntryPlayer.objects.get(
            contest=contest,
            name__startswith=alias5
        )
    if len(lineup) > 5:
        alias6 = lineup[5].strip().replace('á', 'a')
        player6 = models.ContestEntryPlayer.objects.get(
            contest=contest,
            name__startswith=alias6
        )

    entry = models.ContestEntry.objects.create(
        contest=contest,
        entry_id=entry_id,
        entry_name=entry_name,
        lineup_str=lineup_str,
        player_1=player1,
        player_2=player2,
        player_3=player3,
        player_4=player4,
        player_5=player5,
        player_6=player6
    )
    entry.simulate()


@shared_task
def process_contest(contest_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        contest = models.Contest.objects.get(id=contest_id)

        # Process players from sim
        if contest.sim_file:
            models.ContestEntryPlayer.objects.filter(contest=contest).delete()

            df_sim = pandas.read_excel(contest.sim_file.path, sheet_name='DK Raw', index_col=0).transpose()

            contest.num_iterations = len(df_sim.columns)
            contest.save()

            for _, row in df_sim.iterrows():
                models.ContestEntryPlayer.objects.create(
                    contest=contest,
                    name=row.name,
                    scores=row.to_list()
                )   

            # Process entries from contest file
            if contest.entries_file:
                models.ContestEntry.objects.filter(contest=contest).delete()
                try:
                    with open(contest.entries_file.path, mode='r') as entries_file:
                        csv_reader = csv.DictReader(entries_file)
                        
                        jobs = []
                        for row in csv_reader:
                            lineup = []
                            for item in re.finditer(r"((D)|(CPT)|(CNSTR)) [A-z]+ [A-z]*( Jr)?", row['Lineup']):
                                lineup.append(item[0])

                            if len(lineup) > 0:
                                jobs.append(
                                    process_contest_entry.si(
                                        row['EntryId'],
                                        row['EntryName'],
                                        row['Lineup'],
                                        lineup,
                                        contest.id
                                    )
                                )

                        chord(jobs,
                            process_contest_complete.si(contest.id, task.id)
                        )()
                except ValueError:
                    pass            
            
            if contest.prizes_file:
                models.ContestPrize.objects.filter(contest=contest).delete()

                df_prizes = pandas.read_csv(contest.prizes_file.path)
                df_prizes['contest_id'] = contest.id
                logger.info(df_prizes)


                models.ContestPrize.objects.bulk_create(
                    models.ContestPrize(**vals) for vals in df_prizes.to_dict('records')
                )   

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing contest: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_contest_complete(contest_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        contest = models.Contest.objects.get(id=contest_id)

        task.status = 'success'
        task.content = f'{contest} processed.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing contest: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def start_contest_simulation(backtest_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        backtest = models.ContestBacktest.objects.get(id=backtest_id)
        backtest.entry_outcomes.all().delete()

        prizes = backtest.contest.prizes.all()
        prize_lookup = {}
        for prize in prizes:
            for rank in range(prize.min_rank, prize.max_rank+1):
                prize_lookup[float(rank)] = float(prize.prize)

        a = [[l.id] + l.sim_scores for l in backtest.contest.entries.all().order_by('entry_id').iterator()]
        df_lineups = pandas.DataFrame(a, columns=['id'] + [i for i in range(0, backtest.contest.num_iterations)])
        df_lineups = df_lineups.set_index('id')

        chunk_size = int(backtest.contest.num_iterations / 10)

        # combining workflow combines the results from each iteration workflow
        chord([
            # iteration workflow simulates contest N times, where N = chunk_size, returning the results to combine_contest_sim_results
            chord([
                simulate_contest_by_iteration.si(prize_lookup, backtest.id, df_lineups[i + j].to_json(orient='index')) for i in range(0, chunk_size)
            ], combine_contest_sim_results.s()) for j in range(0, backtest.contest.num_iterations, chunk_size)
        ], contest_simulation_complete.s(
            backtest.id, 
            task.id
        ))()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error simulating contest ROIs for {backtest}: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def simulate_contest_by_iteration(prize_lookup, backtest_id, lineups, exclude_lineups_with_username=None):
    backtest = models.ContestBacktest.objects.get(id=backtest_id)
    entries = backtest.contest.entries.all().order_by('entry_id')

    if exclude_lineups_with_username is not None:
        entries = entries.exclude(entry_name__istartswith=exclude_lineups_with_username)

    # start = time.time()
    # a = [[l.id, l.sim_scores[iteration]] for l in entries.iterator()]
    # logger.info(f'creating lineup arrays took {time.time() - start}s')
    # start = time.time()
    # df_lineups = pandas.DataFrame(a, columns=['entry_id', 'score'])
    df_lineups = pandas.read_json(lineups, orient='index')
    # df_lineups['backtest_id'] = backtest.id
    # df_lineups['iteration'] = iteration
    # df_lineups['id'] = df_lineups['entry_id']
    # logger.info(f'loading lineups dataframe took {time.time() - start}s')
    # start = time.time()
    # df_lineups = df_lineups.set_index('id')
    # logger.info(f'setting lineups dataframe index took {time.time() - start}s')
    # start = time.time()
    df_lineups['rank'] = df_lineups[0].rank(method='min', ascending=False)
    # logger.info(f'ranking lineups took {time.time() - start}s')
    # start = time.time()
    df_lineups['rank_count'] = df_lineups['rank'].map(df_lineups['rank'].value_counts())
    rank_counts = df_lineups['rank'].value_counts()
    df_lineups['prize'] = df_lineups['rank'].map(lambda x: numpy.mean([prize_lookup.get(str(float(r)), 0.0) for r in range(int(x),int(x)+rank_counts[x])]))
    # logger.info(f'payouts took {time.time() - start}s')

    return df_lineups['prize'].to_list()


@shared_task
def combine_contest_sim_results(results):        
    total_result = None
    for result in results:
        if total_result is None:
            total_result = numpy.array(result)
        else:
            total_result += numpy.array(result)
    
    return total_result.tolist()


@shared_task
def contest_simulation_complete(results, backtest_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        backtest = models.ContestBacktest.objects.get(id=backtest_id)
        
        total_result = None
        for result in results:
            if total_result is None:
                total_result = numpy.array(result)
            else:
                total_result += numpy.array(result)
        
        entries = backtest.contest.entries.all().order_by('entry_id')
        df_result = pandas.DataFrame.from_records(entries.values('id'))
        df_result['entry_id'] = df_result['id']
        df_result['backtest_id'] = backtest.id
        df_result['amount_won'] = total_result
        df_result['roi'] = (total_result - (float(backtest.contest.cost) * backtest.contest.num_iterations)) / (float(backtest.contest.cost) * backtest.contest.num_iterations)
        df_result.set_index('id')
        # logger.info(df_result)
        # logger.info(results)
        # entries = backtest.contest.entries.all().annotate(
        #     amount_won=Sum('backtest_iteration_outcomes__prize')
        # )
        # df_entries = pandas.DataFrame.from_records(entries.values('id', 'amount_won'))
        # df_entries['roi'] = (df_entries['amount_won'] - (float(backtest.contest.cost) * 3))/ (float(backtest.contest.cost) * backtest.contest.num_iterations)
        # df_entries['entry_id'] = df_entries['id']
        # df_entries['backtest_id'] = backtest.id
        # df_entries.set_index('id')

        models.ContestBacktestEntry.objects.bulk_create(
            models.ContestBacktestEntry(**vals) for vals in df_result.to_dict('records')
        )   

        task.status = 'success'
        task.content = f'{backtest} complete.'
        task.save()

    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was an error simulating contest ROIs for {backtest}: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))
