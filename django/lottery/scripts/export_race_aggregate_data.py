import datetime
import numpy as np
import pandas as pd
import math

from random import random

from django.db.models import Count, Q

from nascar import models


def run():
    races = models.Race.objects.filter(
        race_season=2021,
        race_type=1
    ).annotate(
        num_infractions=Count('infractions', filter=Q(infractions__lap__gt=0, infractions__infraction='Pitting before pit road is open'), distinct=True),
        num_cautions_segments=Count('cautions', filter=Q(cautions__start_lap__gt=0), distinct=True)
    )

    df_races = pd.DataFrame.from_records(races.values('race_name', 'series', 'restrictor_plate', 'scheduled_distance', 'scheduled_laps', 'num_cautions_segments', 'num_infractions'))
    print(df_races)
    df_races.to_csv(f'data/race_data.csv')
