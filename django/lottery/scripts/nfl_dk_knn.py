import math
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import seaborn as sns
import traceback

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.neighbors import KNeighborsRegressor
from sklearn.metrics import mean_squared_error

from django.db.models import F

from nfl import models


def run():
    players = models.SlatePlayerProjection.objects.filter(
        # projection__gt=3,
        slate_player__slate__is_main_slate=True,
        slate_player__slate__site='draftkings',
        slate_player__site_pos='WR'
    ).exclude(
        slate_player__fantasy_points=None
    ).exclude(
        slate_player__fantasy_points__lt=1.0
    )

    df = pd.DataFrame.from_records(
        players.values('slate_player__salary', 'projection', 'slate_player__fantasy_points'),
        index=players.values_list('slate_player_id', flat=True)
    )
    df['projection'] = df['projection'].map(lambda x: float(x))
    df['slate_player__fantasy_points'] = df['slate_player__fantasy_points'].map(lambda x: float(x))

    # df['variance'] = (df['slate_player__fantasy_points'] - (df['projection'] + df['slate_player__fantasy_points']) / 2) ** 2
    # df['variance'] = df['variance'].map(lambda x: float(x))
    X = df.drop(['slate_player__salary', 'slate_player__fantasy_points'], axis=1)
    # y = df['variance'].values

    new_dp = np.array([
        # 5500,
        17.5
    ])
    distances = np.linalg.norm(X - new_dp, axis=1)

    # correlation_matrix = df.corr()
    # print(correlation_matrix['variance'])

    k = 50
    nearest_neighbor_ids = distances.argsort()[:k]
    print(df.iloc[nearest_neighbor_ids])

    scores = df.iloc[nearest_neighbor_ids]['slate_player__fantasy_points']
    print(f'mean = {scores.mean()}')
    print(f'median = {scores.median()}')
    print(f'variance = {scores.var()}')
    print(f'stdev = {scores.std()}')
    

    # print(f'stdev = {math.sqrt(df.iloc[nearest_neighbor_ids].mean()[3])}')

    # X_train, X_test, y_train, y_test = train_test_split(
    #     X, y, test_size=0.2, random_state=12345
    # )
    # knn_model = KNeighborsRegressor(n_neighbors=3)
    # knn_model.fit(X_train, y_train)
    # # train_preds = knn_model.predict(X_train)
    # # mse = mean_squared_error(y_train, train_preds)
    # test_preds = knn_model.predict(X_test)
    # mse = mean_squared_error(y_test, test_preds)
    # rmse = math.sqrt(mse)
    # print(f'rmse = {rmse}')

    # parameters = {"n_neighbors": range(1, 50)}
    # gridsearch = GridSearchCV(KNeighborsRegressor(), parameters)
    # gridsearch.fit(X_train, y_train)
    # print(gridsearch.best_params_)