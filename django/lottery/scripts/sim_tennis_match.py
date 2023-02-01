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
    curr_match = models.PinnacleMatch.objects.get(id=1511602092)
    best_of = 3
    if 'Australian Open' in curr_match.tournament_name or 'French Open' in curr_match.tournament_name or 'Wimbledon Open' in curr_match.tournament_name or 'US Open' in curr_match.tournament_name:
        if curr_match.home_player.tour == 'atp':
            best_of = 5

    all_matches = models.Match.objects.filter(
        winner__tour=curr_match.home_player.tour,
        best_of=best_of,
        surface='Hard'
    ).exclude(Q(
        Q(w_ace=None) | Q(w_df=None) | Q(l_ace=None) | Q(l_df=None)
    )).exclude(
        score__icontains='RET'
    ).order_by('-tourney_date')

    df_all_matches = pandas.DataFrame.from_records(
        all_matches.values(
            'winner_name',
            'winner_odds',
            'loser_name',
            'loser_odds',
            'winner_dk',
            'loser_dk',
            'winner_ace_rate',
            'winner_df_rate',
            'winner_firstin_rate',
            'winner_firstwon_rate',
            'winner_secondwon_rate',
            'winner_hold_rate',
            'winner_break_rate',
            'loser_ace_rate',
            'loser_vace_rate',
            'loser_firstwon_rate',
            'loser_secondwon_rate',
            'loser_hold_rate',
            'loser_break_rate',
        ),
        index=all_matches.values_list('id', flat=True)
    )
    df_all_matches.dropna(inplace=True)

    X = df_all_matches.drop([
        'winner_name', 
        'loser_name',
        'winner_dk',
        'loser_dk',
    ], axis=1)
    y = df_all_matches['winner_dk'].values
    
    start = time.time()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=12345
    )
    parameters = {"n_neighbors": range(1, 500)}
    gridsearch = GridSearchCV(KNeighborsRegressor(), parameters)
    gridsearch.fit(X_train, y_train)
    k = gridsearch.best_params_.get('n_neighbors')
    print(f'Finding k took {time.time() - start}s')

    fav = curr_match.favorite[0]
    dog = curr_match.underdog[0]
    
    if curr_match.favorite[1] > 0:
        fav_implied = 100/(100+curr_match.favorite[1])
    else:
        fav_implied = -curr_match.favorite[1]/(-curr_match.favorite[1]+100)
    
    if curr_match.underdog[1] > 0:
        dog_implied = 100/(100+curr_match.underdog[1])
    else:
        dog_implied = -curr_match.underdog[1]/(-curr_match.underdog[1]+100)

    # remove the vig
    total_implied = fav_implied + dog_implied
    fav_implied = fav_implied / total_implied
    dog_implied = dog_implied / total_implied

    # Find comp for this outcome (favorite wins)
    start = time.time()
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
    fav_win_scores = df_all_matches.iloc[nearest_neighbor_ids]
    print(f'Finding {k} fav-win comps took {time.time() - start}s')

    # Find comp for other outcome (favorite loses)
    start = time.time()
    new_dp = numpy.array([
        float(curr_match.underdog[1]),
        float(curr_match.favorite[1]),
        float(dog.get_ace_rate()),
        float(dog.get_df_rate()),
        float(dog.get_first_in_rate()),
        float(dog.get_first_won_rate()),
        float(dog.get_second_won_rate()),
        float(dog.get_hold_rate()),
        float(dog.get_break_rate()),
        float(fav.get_ace_rate()),
        float(fav.get_v_ace_rate()),
        float(fav.get_first_won_rate()),
        float(fav.get_second_won_rate()),
        float(fav.get_hold_rate()),
        float(fav.get_break_rate())
    ])
    distances = numpy.linalg.norm(X - new_dp, axis=1)

    # k = 50
    nearest_neighbor_ids = distances.argsort()[:k]
    dog_win_scores = df_all_matches.iloc[nearest_neighbor_ids]
    print(f'Finding {k} dog-win comps took {time.time() - start}s')

    # find 10k outcomes based on odds 
    start = time.time()
    outcomes = []
    for _ in range(0, 10000):
        if random() <= fav_implied:
            outcome = fav_win_scores.sample(1)
            outcomes.append([outcome['winner_dk'].values[0], outcome['loser_dk'].values[0]])
        else:
            outcome = dog_win_scores.sample(1)
            outcomes.append([outcome['loser_dk'].values[0], outcome['winner_dk'].values[0]])

    df_outcomes = pandas.DataFrame(outcomes, columns=[fav.full_name, dog.full_name])
    print(df_outcomes)
    df_outcomes.to_csv('data/tennis_sim.csv')
    print(f'Simulating 10k outcomes took {time.time() - start}s')
