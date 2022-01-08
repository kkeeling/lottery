# import csv
# import datetime
# import decimal
# import math
# import random
# import string
# import traceback

# from collections import namedtuple
# from django.core.management.base import BaseCommand
# from django.db.models import ObjectDoesNotExist
# from fcpro_fd_nfl import models
# from pydfs_lineup_optimizer import Site, Sport, Player, PlayersGroup, get_optimizer, \
#     PositionsStack, exceptions, Stack, TeamStack, AfterEachExposureStrategy, LineupOptimizer
# from pydfs_lineup_optimizer.sites.fanduel.classic.settings import FanDuelSettings
# from sklearn.metrics.pairwise import cosine_similarity
# from sklearn.feature_extraction.text import CountVectorizer

# from . import models

# GameInfo = namedtuple('GameInfo', ['home_team', 'away_team', 'starts_at', 'game_started'])


# def optimize_for_simulation(player_tuples):
#     optimizer = get_optimizer(Site.DRAFTKINGS, Sport.TENNIS)
    
#     players_list = get_player_list(
#         player_tuples, 
#         randomness=0.0,
#     )
#     optimizer.load_players(players_list)

#     lineups = []

#     num_lineups = math.ceil(len(player_tuples) / 16) + 1
#     try:
#         optimized_lineups = optimizer.optimize(
#             n=num_lineups,
#             randomness=False, 
#         )
#         count = 0

#         for lineup in optimized_lineups:
#             lineups.append(lineup)
#             count += num_lineups
#     except exceptions.LineupOptimizerException:
#         print('Cannot generate more lineups')

#     return lineups


# def optimize_for_ownership(slate_players, num_lineups=1000):
#     optimizer = get_optimizer(Site.DRAFTKINGS, Sport.TENNIS)
#     op = {}

#     (players_list, underdogs) = get_player_list_for_op(
#         slate_players, 
#         randomness=0.20)
#     optimizer.load_players(players_list)
#     optimizer.restrict_positions_for_opposing_team(['P'], ['P'])  # no opposing players
#     underdog_group = PlayersGroup(underdogs, max_from_group=2)
#     optimizer.add_players_group(underdog_group)

#     try:
#         optimized_lineups = optimizer.optimize(
#             n=num_lineups,
#             randomness=False, 
#         )
#         count = 0

#         for lineup in optimized_lineups: 
#             if lineup.players[0].id not in op:
#                 op[lineup.players[0].id] = 0
#             if lineup.players[1].id not in op:
#                 op[lineup.players[1].id] = 0
#             if lineup.players[2].id not in op:
#                 op[lineup.players[2].id] = 0
#             if lineup.players[3].id not in op:
#                 op[lineup.players[3].id] = 0
#             if lineup.players[4].id not in op:
#                 op[lineup.players[4].id] = 0
#             if lineup.players[5].id not in op:
#                 op[lineup.players[5].id] = 0
                
#             op[lineup.players[0].id] += 1
#             op[lineup.players[1].id] += 1
#             op[lineup.players[2].id] += 1
#             op[lineup.players[3].id] += 1
#             op[lineup.players[4].id] += 1
#             op[lineup.players[5].id] += 1

#             count += num_lineups
#     except exceptions.LineupOptimizerException:
#         print('Cannot generate more lineups')

#     return op


# def optimize(slate_players, config, groups, num_lineups=150):
#     optimizer = get_optimizer(Site.DRAFTKINGS, Sport.TENNIS)
    
#     # Salary
#     if config.min_salary > 0:
#         optimizer.set_min_salary_cap(config.min_salary)
    
#     # Uniques
#     optimizer.set_max_repeating_players(6 - config.uniques) 

#     player_tuples = []

#     for slate_player in slate_players:
#         player_tuples.append(
#             (slate_player, float(slate_player.projection.implied_win_pct * 100))
#         )

#     players_list = get_player_list(
#         player_tuples, 
#         randomness=config.randomness,
#         config=config,
#         use_projections=True
#     )
#     optimizer.load_players(players_list)
#     optimizer.restrict_positions_for_opposing_team(['P'], ['P'])  # no opposing players

#     locked_players = slate_players.filter(projection__lock=True)
#     for locked_player in locked_players:
#         player = optimizer.get_player_by_id(locked_player.slate_player_id)

#         if player is not None:
#             optimizer.add_player_to_lineup(player)

#     # add players groups
#     for group in groups:
#         player_ids = group.players.all().values_list('slate_player__slate_player_id', flat=True)
#         g = PlayersGroup(
#             [optimizer.get_player_by_id(id) for id in player_ids],
#             min_from_group=group.min_from_group,
#             max_from_group=group.max_from_group
#         )
#         optimizer.add_players_group(g)

#     lineups = []

#     try:
#         optimized_lineups = optimizer.optimize(
#             n=num_lineups,
#             randomness=True
#         )
#         count = 0

#         for lineup in optimized_lineups:
#             lineups.append(lineup)
#             count += num_lineups
#     except exceptions.LineupOptimizerException:
#         print('Cannot generate more lineups')

#     return lineups


# def get_player_list(player_tuples, randomness=0.75, config=None, use_projections=False):
#     '''
#     Returns the player list on which to optimize
#     '''
#     player_list = []

#     for tup in player_tuples:
#         slate_player = tup[0]
#         score = tup[1]
#         if ' ' in slate_player.name:
#             first = slate_player.name.split(' ')[0]
#             last = slate_player.name.split(' ')[-1]
#         else:
#             first = slate_player.name
#             last = ''
        
#         match = slate_player.find_pinn_match()

#         if ' ' in match.home_participant:
#             home_last = match.home_participant.split(' ')[-1]
#         else:
#             home_last = match.home_participant

#         if ' ' in match.away_participant:
#             away_last = match.away_participant.split(' ')[-1]
#         else:
#             away_last = match.away_participant

#         game_info = GameInfo(
#             home_team=home_last, 
#             away_team=away_last,
#             starts_at=match.start_time,
#             game_started=False
#         )

#         player = Player(
#             slate_player.slate_player_id,
#             first,
#             last,
#             ['P'],
#             last,
#             slate_player.salary,
#             score,
#             game_info=game_info,
#             min_deviation=-float(randomness),
#             max_deviation=float(randomness)
#         )

#         if use_projections and not slate_player.projection.lock:
#             if slate_player.projection.min_exposure > 0.0:
#                 player.min_exposure = float(slate_player.projection.min_exposure)
#             if slate_player.projection.max_exposure > 0.0:
#                 player.max_exposure = float(slate_player.projection.max_exposure)

#         player_list.append(player)
#     return player_list


# def get_player_list_for_op(slate_players, randomness=0.75):
#     '''
#     Returns the player list on which to optimize
#     '''
#     player_tuples = []

#     for slate_player in slate_players:
#         proj = float(slate_player.projection.implied_win_pct) * 100.0
#         if slate_player.get_best_ace_rate() is not None:
#             if slate_player.get_best_ace_rate() >= 1.25:
#                 proj += 5.0
#             elif slate_player.get_best_ace_rate() >= 1.0:
#                 proj += 3.5
#             elif slate_player.get_best_ace_rate() >= 0.85:
#                 proj += 2.0

#         player_tuples.append(
#             (slate_player, proj)
#         )

#     player_list = []
#     underdogs = []

#     if slate_players.count() <= 18:
#         max_exposure = 1.0
#         underdog_max_exposure = 0.3
#         big_underdog_max_exposure = 0.2
#     else:
#         if slate_players.count() <= 20:
#             max_exposure = 0.70
#             underdog_max_exposure = 0.25
#             big_underdog_max_exposure = 0.15
#         elif slate_players.count() <= 25:
#             max_exposure = 0.65
#             underdog_max_exposure = 0.25
#             big_underdog_max_exposure = 0.10
#         elif slate_players.count() <= 30:
#             max_exposure = 0.55
#             underdog_max_exposure = 0.20
#             big_underdog_max_exposure = 0.10
#         elif slate_players.count() <= 40:
#             max_exposure = 0.45
#             underdog_max_exposure = 0.20
#             big_underdog_max_exposure = 0.10
#         else:
#             max_exposure = 0.35
#             underdog_max_exposure = 0.20
#             big_underdog_max_exposure = 0.7

#     for tup in player_tuples:
#         slate_player = tup[0]
#         score = tup[1]
#         if ' ' in slate_player.name:
#             first, last = slate_player.name.split(' ', 1)
#         else:
#             first = slate_player.name
#             last = ''
        
#         match = slate_player.find_pinn_match()
#         print(slate_player, match)

#         if ' ' in match.home_participant:
#             _, home_last = match.home_participant.split(' ', 1)
#         else:
#             home_last = match.home_participant

#         if ' ' in match.away_participant:
#             _, away_last = match.away_participant.split(' ', 1)
#         else:
#             away_last = match.away_participant

#         game_info = GameInfo(
#             home_team=home_last, 
#             away_team=away_last,
#             starts_at=match.start_time,
#             game_started=False
#         )

#         player = Player(
#             slate_player.slate_player_id,
#             first,
#             last,
#             ['P'],
#             last,
#             slate_player.salary,
#             score,
#             game_info=game_info,
#             min_deviation=-float(randomness),
#             max_deviation=float(randomness),
#             max_exposure=max_exposure
#         )

#         if slate_player.projection.implied_win_pct < 0.44:
#             if slate_player.projection.implied_win_pct < 0.35:
#                 player.max_exposure = big_underdog_max_exposure
#             else:
#                 player.max_exposure = underdog_max_exposure
#             underdogs.append(player)
            
#         if slate_player.projection.min_exposure_for_op > 0.0:
#             player.min_exposure = float(slate_player.projection.min_exposure_for_op)

#         if slate_player.projection.max_exposure_for_op > 0.0:
#             player.max_exposure = float(slate_player.projection.max_exposure_for_op)

#         player_list.append(player)
#     return (player_list, underdogs)
