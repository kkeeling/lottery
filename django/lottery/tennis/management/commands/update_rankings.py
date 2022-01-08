import csv
import datetime
import traceback

from django.core.management.base import BaseCommand

from tennis.models import RankingHistory


class Command(BaseCommand):
    help = 'Update rankings from github'

    def handle(self, *args, **options):
        RankingHistory.update_rankings()
