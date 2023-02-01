import logging
import numpy
import pandas
import time
from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.neighbors import KNeighborsRegressor
from random import random

from . import serializers, models

logger = logging.getLogger(__name__)


class SlateMatch:
    def __init__(self, player1, player2, odds1, odds2):
        self.player1 = player1
        self.player2 = player2
        self.odds1 = odds1
        self.odds2 = odds2
        self.tournament_name = 'Australian Open'

    @property
    def home_player(self):
        return models.Alias.find_alias(self.player1, 'draftkings').player

    @property
    def away_player(self):
        return models.Alias.find_alias(self.player2, 'draftkings').player

    @property
    def favorite(self):
        if self.odds1 < self.odds2:
            return (self.home_player, self.odds1)
        return (self.away_player, self.odds2)

    @property
    def underdog(self):
        if self.odds1 >= self.odds2:
            return (self.home_player, self.odds1)
        return (self.away_player, self.odds2)

    def simple_simulate(self, iterations=10000):
        best_of = 3
        surface = 'Hard'
        if 'Australian Open' in self.tournament_name or 'French Open' in self.tournament_name or 'Wimbledon Open' in self.tournament_name or 'US Open' in self.tournament_name:
            if self.home_player.tour == 'atp':
                best_of = 5

        all_matches = models.Match.objects.filter(
            winner__tour=self.home_player.tour,
            best_of=best_of,
            surface=surface
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
        
        # start = time.time()
        # X_train, X_test, y_train, y_test = train_test_split(
        #     X, y, test_size=0.2, random_state=12345
        # )
        # parameters = {"n_neighbors": range(1, 500)}
        # gridsearch = GridSearchCV(KNeighborsRegressor(), parameters)
        # gridsearch.fit(X_train, y_train)
        # k = gridsearch.best_params_.get('n_neighbors')
        # logger.info(f'Finding k took {time.time() - start}s')

        k = 304
        fav = self.favorite[0]
        dog = self.underdog[0]

        # logger.info(f'fav = {fav}')
        # logger.info(f'dog = {dog}')
        
        if self.favorite[1] > 0:
            fav_implied = 100/(100+self.favorite[1])
        else:
            fav_implied = -self.favorite[1]/(-self.favorite[1]+100)
        
        if self.underdog[1] > 0:
            dog_implied = 100/(100+self.underdog[1])
        else:
            dog_implied = -self.underdog[1]/(-self.underdog[1]+100)

        # remove the vig
        total_implied = fav_implied + dog_implied
        fav_implied = fav_implied / total_implied
        dog_implied = dog_implied / total_implied

        # Find comp for this outcome (favorite wins)
        start = time.time()
        new_dp = numpy.array([
            float(self.favorite[1]),
            float(self.underdog[1]),
        ])
        distances = numpy.linalg.norm(X - new_dp, axis=1)

        # k = 50
        nearest_neighbor_ids = distances.argsort()[:k]
        fav_win_scores = df_all_matches.iloc[nearest_neighbor_ids]
        logger.info(f'Finding {k} fav-win comps took {time.time() - start}s')

        # Find comp for other outcome (favorite loses)
        start = time.time()
        new_dp = numpy.array([
            float(self.underdog[1]),
            float(self.favorite[1]),
        ])
        distances = numpy.linalg.norm(X - new_dp, axis=1)

        # k = 50
        nearest_neighbor_ids = distances.argsort()[:k]
        dog_win_scores = df_all_matches.iloc[nearest_neighbor_ids]
        logger.info(f'Finding {k} dog-win comps took {time.time() - start}s')

        # find outcomes based on odds 
        start = time.time()
        outcomes = []
        for _ in range(0, iterations):
            if random() <= fav_implied:
                outcome = fav_win_scores.sample(1)
                outcomes.append([outcome['winner_dk'].values[0], outcome['loser_dk'].values[0]])
            else:
                outcome = dog_win_scores.sample(1)
                outcomes.append([outcome['loser_dk'].values[0], outcome['winner_dk'].values[0]])

        df_outcomes = pandas.DataFrame(outcomes, columns=[fav.full_name, dog.full_name])
        logger.info(df_outcomes)
        # df_outcomes.to_csv('data/tennis_sim.csv')
        logger.info(f'Simulating 10k outcomes took {time.time() - start}s')

        return df_outcomes

    def simulate(self, iterations=10000):
        best_of = 3
        surface = 'Hard'
        if 'Australian Open' in self.tournament_name or 'French Open' in self.tournament_name or 'Wimbledon Open' in self.tournament_name or 'US Open' in self.tournament_name:
            if self.home_player.tour == 'atp':
                best_of = 5

        if self.home_player.get_num_matches(on_surface=surface) == 0 or self.away_player.get_num_matches(on_surface=surface) == 0:
            logger.info('SIMPLE')
            return self.simple_simulate(iterations)


        all_matches = models.Match.objects.filter(
            winner__tour=self.home_player.tour,
            best_of=best_of,
            surface=surface
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
        
        # start = time.time()
        # X_train, X_test, y_train, y_test = train_test_split(
        #     X, y, test_size=0.2, random_state=12345
        # )
        # parameters = {"n_neighbors": range(1, 500)}
        # gridsearch = GridSearchCV(KNeighborsRegressor(), parameters)
        # gridsearch.fit(X_train, y_train)
        # k = gridsearch.best_params_.get('n_neighbors')
        # logger.info(f'Finding k took {time.time() - start}s')

        k = 304
        fav = self.favorite[0]
        dog = self.underdog[0]

        # logger.info(f'fav = {fav}')
        # logger.info(f'dog = {dog}')
        
        if self.favorite[1] > 0:
            fav_implied = 100/(100+self.favorite[1])
        else:
            fav_implied = -self.favorite[1]/(-self.favorite[1]+100)
        
        if self.underdog[1] > 0:
            dog_implied = 100/(100+self.underdog[1])
        else:
            dog_implied = -self.underdog[1]/(-self.underdog[1]+100)

        # remove the vig
        total_implied = fav_implied + dog_implied
        fav_implied = fav_implied / total_implied
        dog_implied = dog_implied / total_implied

        # Find comp for this outcome (favorite wins)
        start = time.time()
        new_dp = numpy.array([
            float(self.favorite[1]),
            float(self.underdog[1]),
            float(fav.get_ace_rate(on_surface=surface)),
            float(fav.get_df_rate(on_surface=surface)),
            float(fav.get_first_in_rate(on_surface=surface)),
            float(fav.get_first_won_rate(on_surface=surface)),
            float(fav.get_second_won_rate(on_surface=surface)),
            float(fav.get_hold_rate(on_surface=surface)),
            float(fav.get_break_rate(on_surface=surface)),
            float(dog.get_ace_rate(on_surface=surface)),
            float(dog.get_v_ace_rate(on_surface=surface)),
            float(dog.get_first_won_rate(on_surface=surface)),
            float(dog.get_second_won_rate(on_surface=surface)),
            float(dog.get_hold_rate(on_surface=surface)),
            float(dog.get_break_rate(on_surface=surface))
        ])
        distances = numpy.linalg.norm(X - new_dp, axis=1)

        # k = 50
        nearest_neighbor_ids = distances.argsort()[:k]
        fav_win_scores = df_all_matches.iloc[nearest_neighbor_ids]
        logger.info(f'Finding {k} fav-win comps took {time.time() - start}s')

        # Find comp for other outcome (favorite loses)
        start = time.time()
        new_dp = numpy.array([
            float(self.underdog[1]),
            float(self.favorite[1]),
            float(dog.get_ace_rate(on_surface=surface)),
            float(dog.get_df_rate(on_surface=surface)),
            float(dog.get_first_in_rate(on_surface=surface)),
            float(dog.get_first_won_rate(on_surface=surface)),
            float(dog.get_second_won_rate(on_surface=surface)),
            float(dog.get_hold_rate(on_surface=surface)),
            float(dog.get_break_rate(on_surface=surface)),
            float(fav.get_ace_rate(on_surface=surface)),
            float(fav.get_v_ace_rate(on_surface=surface)),
            float(fav.get_first_won_rate(on_surface=surface)),
            float(fav.get_second_won_rate(on_surface=surface)),
            float(fav.get_hold_rate(on_surface=surface)),
            float(fav.get_break_rate(on_surface=surface))
        ])
        distances = numpy.linalg.norm(X - new_dp, axis=1)

        # k = 50
        nearest_neighbor_ids = distances.argsort()[:k]
        dog_win_scores = df_all_matches.iloc[nearest_neighbor_ids]
        logger.info(f'Finding {k} dog-win comps took {time.time() - start}s')

        # find outcomes based on odds 
        start = time.time()
        outcomes = []
        for _ in range(0, iterations):
            if random() <= fav_implied:
                outcome = fav_win_scores.sample(1)
                outcomes.append([outcome['winner_dk'].values[0], outcome['loser_dk'].values[0]])
            else:
                outcome = dog_win_scores.sample(1)
                outcomes.append([outcome['loser_dk'].values[0], outcome['winner_dk'].values[0]])

        df_outcomes = pandas.DataFrame(outcomes, columns=[fav.full_name, dog.full_name])
        logger.info(df_outcomes)
        # df_outcomes.to_csv('data/tennis_sim.csv')
        logger.info(f'Simulating 10k outcomes took {time.time() - start}s')

        return df_outcomes


class PlayerProjection(dict):
    def __init__(self, player, median):
        dict.__init__(self, player=player, median=median)


class SlateSimulatorViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.CsvUploadSerializer
    permission_classes = []

    def create(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data['file']
        df_csv = pandas.read_csv(file, index_col='Player')
        df_csv['opp'] = df_csv['Opponent'].map(lambda x: x.replace('vs. ', ''))
        # logger.info(df_csv.loc['Andrey Rublev']['Odds'])
        df_csv['opponent_odds'] = df_csv.apply(lambda x: df_csv.loc[x['opp'], 'Odds'], axis=1)
        logger.info(df_csv)

        # create matches
        projections = []
        used_players = []
        for index, row in df_csv.iterrows():
            player = index
            opponent = row['opp']
            player_odds = row['Odds']
            opponent_odds = row['opponent_odds']

            if player not in used_players:
                m = SlateMatch(player, opponent, player_odds, opponent_odds)
                logger.info(f'{player} ({player_odds}) v. {opponent} ({opponent_odds})')
                
                median_proj = m.simulate(10000).median().to_numpy()
                projections.append(PlayerProjection(m.player1, median_proj[0]))
                projections.append(PlayerProjection(m.player2, median_proj[1]))

                used_players.append(player)
                used_players.append(opponent)
                

        pandas.DataFrame(projections).to_csv('data/tennis_projections.csv')
        return Response(projections,
                        status.HTTP_201_CREATED)
