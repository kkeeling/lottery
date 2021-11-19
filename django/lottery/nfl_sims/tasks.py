import json
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

