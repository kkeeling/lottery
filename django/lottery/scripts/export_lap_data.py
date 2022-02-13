import datetime
import numpy as np
import pandas as pd
import math

from random import random

from django.db.models import Count, Q, F

from nascar import models


def run():
    laps = models.RaceDriverLap.objects.filter(
        race__race_season=2021,
        race__race_type=1,
        lap__gt=0
    ).annotate(
        race_name=F('race__race_name'),
        series=F('race__series'),
        restrictor_plate=F('race__restrictor_plate'),
        track=F('race__track__track_name'),
        distance=F('race__scheduled_distance'),
        num_laps=F('race__scheduled_laps'),
        num_cautions=F('race__num_cautions'),
        num_caution_laps=F('race__num_caution_laps'),
        name=F('driver__full_name')
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
        'running_pos'
    ))
    # df_laps = df_laps.groupby([
    #     'series',
    #     'race__race_name',
    #     'lap'
    # ]).max('lap_speed')
    
    df_laps = df_laps.loc[df_laps.groupby([
        'series',
        'race__race_name',
        'lap'
    ])['lap_speed'].idxmax()]

    print(df_laps)
    df_laps.to_csv(f'data/lap_data.csv')

    caution_segments = models.RaceCautionSegment.objects.filter(
        race__race_season=2021,
        race__race_type=1,
    )
    df_cautions = pd.DataFrame.from_records(caution_segments.values(
        'race__race_name',
        'start_lap',
        'end_lap',
        'reason', 
        'comment',
    ))
        
    # df_cautions.to_csv(f'data/caution_data.csv')
