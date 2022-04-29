import csv
import datetime
import numpy
import os
import traceback

import requests

from celery import shared_task, chord, group, chain

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db.models import Q, F
from django.db.models.aggregates import Avg
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import path
from django.utils.html import mark_safe
from django import forms

from django_admin_listfilter_dropdown.filters import DropdownFilter, RelatedDropdownFilter

from configuration.models import BackgroundTask
from . import models, tasks, forms


## Inlines


## Admins
