import csv
import datetime
import traceback

from django.core.management.base import BaseCommand

from tennis.models import Match


class Command(BaseCommand):
    help = 'Update rankings from github'

    def handle(self, *args, **options):
        Match.update_matches()
