import json
import logging
import pandas
import random
import requests
import sys
import time

from celery import shared_task, chord, group
from configuration.models import BackgroundTask
from contextlib import contextmanager

from . import models

from lottery.celery import app

logger = logging.getLogger(__name__)


def index_in_cool_down_range(index):
    cool_down_ranges = [
        {'start': 150, 'end': 155},
        {'start': 250, 'end': 255},
        {'start': 350, 'end': 355},
        {'start': 450, 'end': 455},
        {'start': 550, 'end': 555},
        {'start': 650, 'end': 655},
        {'start': 750, 'end': 755},
        {'start': 850, 'end': 855},
        {'start': 950, 'end': 955},
        {'start': 1050, 'end': 1055},
        {'start': 1150, 'end': 1155},
        {'start': 1250, 'end': 1255},
        {'start': 1350, 'end': 1355},
        {'start': 1450, 'end': 1455},
        {'start': 1550, 'end': 1555},
        {'start': 1650, 'end': 1655},
        {'start': 1750, 'end': 1755},
        {'start': 1850, 'end': 1855},
        {'start': 1950, 'end': 1955},
        {'start': 2050, 'end': 1055},
        {'start': 2150, 'end': 2155},
        {'start': 2250, 'end': 2255},
        {'start': 2350, 'end': 2355},
        {'start': 2450, 'end': 2455},
        {'start': 2550, 'end': 2555},
        {'start': 2650, 'end': 2655},
        {'start': 2750, 'end': 2755},
        {'start': 2850, 'end': 2855},
        {'start': 2950, 'end': 2955},
        {'start': 3050, 'end': 21055},
    ]

    return any(d['start'] <= index and d['end'] > index for d in cool_down_ranges)

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
def get_contest_data(contest_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        contest = models.Contest.objects.get(id=contest_id)
        contest.entries.all().delete()

        response = requests.get(contest.url, headers=models.GET_CONTEST_HEADERS)
        
        data = None
        if response.status_code < 300:
            data = response.json()

            task.status = 'success'
            task.content = f'Data for {contest.name} retrieved and saved.'
        elif contest.contest_json is not None:
            print(f'HTTP Status {response.status_code}.')
            if contest.contest_json is not None:
                data = json.loads(contest.contest_json)

            task.status = 'success'
            task.content = f'HTTP Status {response.status_code}. Using cached data.'

        if data is not None:
            cost = float(data.get('contests').get('result')[0].get('entryFee'))
            name = data.get('contests').get('result')[0].get('title')
            num_entries = int(data.get('contests').get('result')[0].get('entryLimit'))

            contest.cost = cost
            contest.name = name
            contest.num_entries = num_entries
            contest.contest_json = json.dumps(data)
            contest.save()

            contest.prizes.all().delete()
            for prize_group in data.get('contests').get('result')[0].get('payouts'):
                _ = models.ContestPrize.objects.create(
                    contest=contest,
                    min_rank=prize_group.get('pos')[0],
                    max_rank=prize_group.get('pos')[1],
                    prize=prize_group.get('amount')
                )

            task.save()

            return contest.id
        else:
            task.status = 'error'
            task.content = f'HTTP Status {response.status_code}. No cache available.'
            task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem getting contest data: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def get_entries_page_for_contest(contest_id, page, num_pages):
    contest = models.Contest.objects.get(id=contest_id)

    if index_in_cool_down_range(page):
        seconds_to_wait = random.randint(60, 120)
        print('Waiting {}s...'.format(seconds_to_wait))
        time.sleep(seconds_to_wait)
    elif page > 0:
        seconds_to_wait = random.randint(1, 2)
        # print('Waiting {}s...'.format(seconds_to_wait))
        time.sleep(seconds_to_wait)
        
    print(f'Page -- {page+1} out of {num_pages}')
    response = requests.get(contest.entries_url(page), headers=models.GET_ENTRIES_HEADERS)
    
    if response.status_code < 300:
        data = response.json()

        if 'error' in data:
            print(f'{data.get("error").get("description")}')
            print("Waiting 3m to resume.")
            time.sleep(3*60)
            get_entries_page_for_contest(contest_id, page, num_pages)
        
        # process entries from page 
        for entry in data.get('entries').get('result'):
            entry_id = entry.get('id')
            username = entry.get('user').get('nickname')

            models.ContestEntry.objects.get_or_create(
                entry_id=entry_id,
                contest=contest,
                username=username
            )

            get_lineup_for_entry(entry_id)

        contest.last_page_processed = page + 1
        contest.save()
    else:
        print(f'get_entries_page_for_contest: HTTP Status {response.status_code}')


@shared_task
def get_lineup_for_entry(entry_id):
    # seconds_to_wait = random.randint(1, 2)
    # print('Waiting {}s...'.format(seconds_to_wait))
    # time.sleep(seconds_to_wait)

    print(f'Getting entry {entry_id}')
    entry = models.ContestEntry.objects.get(entry_id=entry_id)

    response = requests.get(entry.entry_url, headers=models.GET_LINEUP_HEADERS)
    
    if response.status_code < 300:
        data = response.json()

        if 'error' in data:
            print(f'{data.get("error").get("description")}')
            print("Waiting 3m to resume.")
            time.sleep(3*60)
            get_lineup_for_entry(entry_id)

        entry.entry_json = json.dumps(data.get('entries').get('result')[0].get('lineupSlotList'))
        entry.save()
    else:
        print(f'get_lineup_for_entry: HTTP Status {response.status_code}.')


@shared_task
def export_contest_data(contest_ids, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)  

        df = pandas.DataFrame.from_records(models.Contest.objects.filter(id__in=contest_ids).values())
        df.to_csv(result_path)
        
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
def export_contest_prize_data(contest_ids, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)  

        df = pandas.DataFrame.from_records(models.ContestPrize.objects.filter(contest_id__in=contest_ids).values())
        df.to_csv(result_path)
        
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
def export_contest_entries_data(contest_ids, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)  

        df = pandas.DataFrame.from_records(models.ContestEntry.objects.filter(contest_id__in=contest_ids).values())
        df.to_csv(result_path)
        
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
