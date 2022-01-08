import datetime
import numpy as np
import pandas as pd
import math

from random import random

from django.db.models import Q, Sum

from tennis.models import Player, Alias


def run():
    for alias in Alias.objects.filter(player__isnull=True):
        name_arr = alias.dk_name.split(" ", 1)
        first = name_arr[0]
        last = name_arr[1] if len(name_arr) > 1 else ""

        try:
            player = Player.objects.get(
                first_name=first,
                last_name=last
            )
            alias.player = player
            alias.save()
        except Player.DoesNotExist:
            print(f'Cannot find {alias.dk_name}; first = {first}, last = {last}')
