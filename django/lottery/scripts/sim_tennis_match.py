import datetime
import numpy
import pandas
import math
import time

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.neighbors import KNeighborsRegressor
from random import random

from django.db.models import Q, Sum

from tennis import models


def run():
    curr_match = models.PinnacleMatch.objects.get(id=1565414250)
    best_of = 3
    if 'Australian Open' in curr_match.tournament_name or 'French Open' in curr_match.tournament_name or 'Wimbledon Open' in curr_match.tournament_name or 'US Open' in curr_match.tournament_name:
        if curr_match.home_player.tour == 'atp':
            best_of = 5
    all_matches = models.Match.objects.filter(
        winner__tour=curr_match.home_player.tour,
        best_of=best_of
    ).exclude(Q(
        Q(w_ace=None) | Q(w_df=None) | Q(l_ace=None) | Q(l_df=None)
    )).exclude(
        score__icontains='RET'
    ).order_by('-tourney_date')
    # winner_scores = [m.winner_dk_points for m in all_matches]
    # loser_scores = [m.loser_dk_points for m in all_matches]
    # winner_aces = [m.get_winner_ace_rate() for m in all_matches]

    df_all_matches = pandas.DataFrame.from_records(
        all_matches.values(
            'winner_name',
            'winner_odds',
            'loser_name',
            'loser_odds',
            'surface',
            'winner_dk',
            'loser_dk',
            'winner_num_matches',
            'winner_ace_rate',
            'winner_vace_rate',
            'winner_df_rate',
            'winner_firstin_rate',
            'winner_firstwon_rate',
            'winner_secondwon_rate',
            'winner_hold_rate',
            'winner_break_rate',
            'loser_num_matches',
            'loser_ace_rate',
            'loser_vace_rate',
            'loser_df_rate',
            'loser_firstin_rate',
            'loser_firstwon_rate',
            'loser_secondwon_rate',
            'loser_hold_rate',
            'loser_break_rate',
        ),
        index=all_matches.values_list('id', flat=True)
    )
    df_all_matches.dropna(inplace=True)
    # df_all_matches['winner_dk_points'] = winner_scores
    # df_all_matches['loser_dk_points'] = loser_scores
    # df_all_matches['winner_ace'] = winner_aces

    # print(df_all_matches[df_all_matches.winner_odds <= -250])
    # print(df_all_matches[df_all_matches.winner_odds <= -250].corr()['winner_dk'])
    X = df_all_matches.drop([
        'winner_name', 
        'loser_name',
        'winner_dk',
        'loser_dk',
        'surface',
        'winner_num_matches',
        'winner_vace_rate',
        'loser_num_matches',
        'loser_df_rate',
        'loser_firstin_rate',
    ], axis=1)
    y = df_all_matches['winner_dk'].values
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=12345
    )
    parameters = {"n_neighbors": range(1, 200)}
    gridsearch = GridSearchCV(KNeighborsRegressor(), parameters)
    gridsearch.fit(X_train, y_train)
    k = gridsearch.best_params_.get('n_neighbors')

    # Find comp for this outcome (favorite wins)
    fav = curr_match.favorite[0]
    dog = curr_match.underdog[0]

    new_dp = numpy.array([
        float(curr_match.favorite[1]),
        float(curr_match.underdog[1]),
        float(fav.get_ace_rate()),
        float(fav.get_df_rate()),
        float(fav.get_first_in_rate()),
        float(fav.get_first_won_rate()),
        float(fav.get_second_won_rate()),
        float(fav.get_hold_rate()),
        float(fav.get_break_rate()),
        float(dog.get_ace_rate()),
        float(dog.get_v_ace_rate()),
        float(dog.get_first_won_rate()),
        float(dog.get_second_won_rate()),
        float(dog.get_hold_rate()),
        float(dog.get_break_rate())
    ])
    distances = numpy.linalg.norm(X - new_dp, axis=1)

    # k = 50
    nearest_neighbor_ids = distances.argsort()[:k]
    print(df_all_matches.iloc[nearest_neighbor_ids])

    scores = df_all_matches.iloc[nearest_neighbor_ids]['winner_dk']
    print(scores.median())

    # # Find comp for other outcome (favorite loses)
    # new_dp = numpy.array([
    #     float(curr_match.underdog[1]),
    #     float(curr_match.favorite[1]),
    # ])
    # distances = numpy.linalg.norm(X - new_dp, axis=1)

    # k = 50
    # nearest_neighbor_ids = distances.argsort()[:k]
    # print(df_all_matches.iloc[nearest_neighbor_ids])
