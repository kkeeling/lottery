import csv
import datetime
import logging
import json
import math
from re import A
import numpy
import os
import pandas
import pandasql
import requests
import scipy
import sys
import time
import traceback
import uuid

from random import random, uniform, randrange

from celery import shared_task, chord, group, chain
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages.api import success
from django.db.models.aggregates import Count, Sum, Avg
from django.db.models import Q, F, ExpressionWrapper, FloatField
from django.db import transaction

from configuration.models import BackgroundTask
from pydfs_lineup_optimizer import Site, Sport, Player, get_optimizer

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
