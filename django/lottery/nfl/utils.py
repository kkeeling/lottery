import datetime
import numpy as np
import pandas as pd

from nfl import models


def get_variance(site, site_pos, projection):
    players = models.SlatePlayerProjection.objects.filter(
        slate_player__slate__is_main_slate=True,
        slate_player__slate__site=site,
        slate_player__site_pos=site_pos,
        slate_player__slate__datetime__lt=datetime.date(2022, 2, 28)
    ).exclude(
        slate_player__fantasy_points=None
    ).exclude(
        slate_player__fantasy_points__lt=1.0
    )

    df = pd.DataFrame.from_records(
        players.values('projection', 'slate_player__fantasy_points'),
        index=players.values_list('slate_player_id', flat=True),
        coerce_float=True
    )
    # df['projection'] = df['projection'].map(lambda x: float(x))
    # df['slate_player__fantasy_points'] = df['slate_player__fantasy_points'].map(lambda x: float(x))

    X = df.drop(['slate_player__fantasy_points'], axis=1)

    new_dp = np.array([
        float(projection)
    ])
    distances = np.linalg.norm(X - new_dp, axis=1)

    k = 50
    nearest_neighbor_ids = distances.argsort()[:k]

    scores = df.iloc[nearest_neighbor_ids]['slate_player__fantasy_points']

    return scores.std()
