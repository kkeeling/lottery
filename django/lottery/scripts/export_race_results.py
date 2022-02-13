import datetime
import numpy as np
import pandas as pd
import math

from random import random

from django.db.models import Count, Q, F

from nascar import models


def run():
    results = models.RaceResult.objects.filter(
        race__race_season=2021,
        race__race_type=1
    ).annotate(
        race_name=F('race__race_name'),
        name=F('driver__full_name'),
        team=F('driver__team'),
        series=F('race__series')
    )

    df_results = pd.DataFrame.from_records(results.values(
        'race_name',
        'series',
        'name',
        'team',
        'starting_position',
        'finishing_position',
        'laps_led',
        'times_led',
        'laps_completed',
        'finishing_status',
        'disqualified'
    ))

    print(df_results)
    df_results.to_csv(f'data/race_results.csv')
