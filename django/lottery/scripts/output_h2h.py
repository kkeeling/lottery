import itertools
from math import nan
import time

import numpy
import pandas

from django.db.models import F

from nascar import models, filters

def run():
    build = models.SlateBuild.objects.get(id=4)

    opponents = list(build.field_lineups.all().values_list('opponent_handle', flat=True))
    opponents = list(set(opponents))
    print(opponents)
    df_lineups = pandas.DataFrame.from_records(build.lineups.all().order_by('-median').values(
        'slate_lineup_id', 'slate_lineup__player_1__csv_name', 'slate_lineup__player_2__csv_name', 'slate_lineup__player_3__csv_name', 'slate_lineup__player_4__csv_name', 'slate_lineup__player_5__csv_name', 'slate_lineup__player_6__csv_name', 'slate_lineup__total_salary', 'median', 's75', 's90'
    ))
    print(df_lineups)
    for opponent in opponents:
        df_lineups[opponent] = df_lineups.apply(lambda x: build.matchups.get(field_lineup__opponent_handle=opponent, slate_lineup_id=x.loc['slate_lineup_id']).win_rate if build.matchups.filter(field_lineup__opponent_handle=opponent, slate_lineup_id=x['slate_lineup_id']).count() > 0 else nan, axis=1)
    print(df_lineups)
    