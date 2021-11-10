import logging
import math
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

        # Task implementation goes here

        contest = models.Contest.objects.get(id=contest_id)
        contest.entries.all().delete()

        response = requests.get(contest.url, headers=models.GET_CONTEST_HEADERS)
        
        if response.status_code < 300:
            data = response.json()
            cost = float(data.get('contests')[0].get('entry_fee'))
            name = data.get('contests')[0].get('name')
            contest_id = data.get('contests')[0].get('id')
            entries_url = data.get('contests')[0].get('entries').get('_url')
            num_entries = int(data.get('contests')[0].get('entries').get('count'))

            contest.cost = cost
            contest.name = name
            contest.contest_id = contest_id
            contest.entries_url = entries_url
            contest.num_entries = num_entries
            contest.save()

            seconds_to_wait = random.randint(1, 20)
            print('Waiting {}s...'.format(seconds_to_wait))
            time.sleep(seconds_to_wait)

            task.status = 'success'
            task.content = f'Data for {contest.name} retrieved and saved.'
            task.save()

            return contest.id
        else:
            task.status = 'error'
            task.content = f'HTTP Status {response.status_code}.'
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
    
    if page == 0:
        params = (
            ('include_projections', 'false'),
            ('page_size', '10'),
        )
    else:
        params = (
            ('include_projections', 'false'),
            ('page', str(page)),
            ('page_size', '10'),
        )
        
    print(f'Page -- {page+1} out of {num_pages}')
    response = requests.get(contest.entries_url, headers=models.GET_ENTRIES_HEADERS, params=params)
    
    if response.status_code < 300:
        data = response.json()

        # process entries from page 
        for entry in data.get('entries'):
            entry_id = entry.get('id')
            entry_url = entry.get('_url')

            _ = models.ContestEntry.objects.create(
                entry_id=entry_id,
                contest=contest,
                entry_url=entry_url
            )

    seconds_to_wait = random.randint(1, 20)
    print('Waiting {}s...'.format(seconds_to_wait))
    time.sleep(seconds_to_wait)
