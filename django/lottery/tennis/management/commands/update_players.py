import csv
import datetime
import traceback

from django.core.management.base import BaseCommand

from tennis.models import Player


class Command(BaseCommand):
    help = 'Update players from github'

    def handle(self, *args, **options):
        Player.update_player_list()
