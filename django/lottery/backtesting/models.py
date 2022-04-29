import csv
import datetime
import difflib
from email.policy import default
import math
from pyexpat import model
from urllib import request
from django.db.models.fields import related
import numpy
import random
import re
import requests

from statistics import mean

from celery import chain, group
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models, signals
from django.db.models import Q, Sum
from django.db.models.signals import post_save
from django.utils.html import format_html
from django.urls import reverse_lazy
from django.dispatch import receiver

from configuration.models import BackgroundTask
from . import optimize, tasks


SITE_OPTIONS = (
    ('draftkings', 'DraftKings'),
    ('fanduel', 'Fanduel'),
)

SITE_SCORING = {
    'draftkings': {
        'place_differential': 1,
        'fastest_laps': .45,
        'laps_led': .25,
        'finishing_position': {
            '1': 45,
            '2': 42,
            '3': 41,
            '4': 40,
            '5': 39,
            '6': 38,
            '7': 37,
            '8': 36,
            '9': 35,
            '10': 34,
            '11': 32,
            '12': 31,
            '13': 30,
            '14': 29,
            '15': 28,
            '16': 27,
            '17': 26,
            '18': 25,
            '19': 24,
            '20': 23,
            '21': 21,
            '22': 20,
            '23': 19,
            '24': 18,
            '25': 17,
            '26': 16,
            '27': 15,
            '28': 14,
            '29': 13,
            '30': 13,
            '31': 10,
            '32': 9,
            '33': 8,
            '34': 7,
            '35': 6,
            '36': 5,
            '37': 4,
            '38': 3,
            '39': 2,
            '40': 1,
            '41': 0,
            '42': 0
        },
        'max_salary': 50000
    }
}


