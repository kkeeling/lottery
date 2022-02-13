import datetime
import numpy as np
import pandas as pd
import math

from random import random

from django.db.models import OuterRef, Subquery, F

from nascar import models


def run():
    laps = models.RaceDriverLap.objects.filter(
        race__race_season=2021,
        race__race_type=1,
        lap__gt=0,
        running_pos=1
    ).annotate(
        race_name=F('race__race_name'),
        series=F('race__series'),
        restrictor_plate=F('race__restrictor_plate'),
        track=F('race__track__track_name'),
        distance=F('race__scheduled_distance'),
        num_laps=F('race__scheduled_laps'),
        num_cautions=F('race__num_cautions'),
        num_caution_laps=F('race__num_caution_laps'),
        name=F('driver__full_name'),
        starting_position=Subquery(
            models.RaceResult.objects.filter(
                driver=OuterRef('driver'),
                race=OuterRef('race')
            ).values('starting_position')[:1]
        )
    ).order_by(
        'race_name',
        'lap'
    )

    df_laps = pd.DataFrame.from_records(laps.values(
        'race__race_name',
        'series',
        'restrictor_plate',
        'track',
        'distance',
        'num_laps',
        'num_cautions',
        'num_caution_laps',
        'name',
        'lap',
        'lap_speed',
        'running_pos',
        'starting_position'
    ))
    
    print(df_laps)
    df_laps.to_csv(f'data/lap_leaders.csv')
