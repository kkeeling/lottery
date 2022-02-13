import datetime
import numpy as np
import pandas as pd
import math

from random import random

from django.db.models import Count, Q, F

from nascar import models


def run():
    caution_segments = models.RaceCautionSegment.objects.filter(
        race__race_season=2021,
        race__race_type=1
    ).annotate(
        race_name=F('race__race_name'),
        series=F('race__series')
    )

    df_caution_segments = pd.DataFrame.from_records(caution_segments.values(
        'race_name',
        'series',
        'start_lap',
        'end_lap',
        'reason',
        'comment'
    ))

    print(df_caution_segments)
    df_caution_segments.to_csv(f'data/race_caution_segments.csv')
