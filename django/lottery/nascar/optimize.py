import random
import numpy

from collections import namedtuple
from pydfs_lineup_optimizer import Site, Sport, Player, get_optimizer, exceptions
from pydfs_lineup_optimizer.solvers.mip_solver import MIPSolver

# from draftfast import rules
# from draftfast.optimize import run_multi
# from draftfast.orm import Player
# from draftfast.csv_parse import salary_download


GameInfo = namedtuple('GameInfo', ['home_team', 'away_team', 'starts_at', 'game_started'])


# def optimize(site, projections, config, num_lineups=150):
#     players_list = get_player_list(
#         projections, 
#         config=config
#     )
#     exposure_bounds = [
#         {
#             'name': p.slate_player.name,
#             'max': float(p.max_exposure),
#             'min': float(p.min_exposure)
#         } for p in projections
#     ]
#     rosters, _ = run_multi(
#         iterations=num_lineups,
#         exposure_bounds=exposure_bounds,
#         rule_set=rules.DK_TEN_CLASSIC_RULE_SET,
#         player_pool=players_list,
#         verbose=True,
#     )
#     return rosters

def optimize(site, projections, config, num_lineups=150):
    if site == 'draftkings':
        optimizer = get_optimizer(Site.DRAFTKINGS, Sport.NASCAR)
    elif site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL, Sport.NASCAR)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    
    # Salary
    if config.min_salary > 0:
        optimizer.set_min_salary_cap(config.min_salary)
    
    # Uniques
    if site == 'draftkings':
        optimizer.set_max_repeating_players(6 - config.uniques) 
    else:
        optimizer.set_max_repeating_players(5 - config.uniques) 

    players_list = get_player_list(
        projections, 
        config=config
    )
    optimizer.load_players(players_list)

    lineups = []

    try:
        optimized_lineups = optimizer.optimize(
            n=num_lineups * config.lineup_multiplier,
            randomness=True if config.randomness > 0.0 else False
        )

        for lineup in optimized_lineups:
            lineups.append(lineup)
    except exceptions.LineupOptimizerException:
        print('Cannot generate more lineups')

    return lineups


def get_player_list(projections, config):
    '''
    Returns the player list on which to optimize
    '''
    player_list = []

    for player in projections.filter(in_play=True):
        if ' ' in player.slate_player.name:
            first = player.slate_player.name.split(' ')[0]
            last = player.slate_player.name.split(' ')[-1]
        else:
            first = player.slate_player.name
            last = ''

        # if ' ' in player.slate_match.match.home_participant:
        #     home_last = player.slate_match.match.home_participant.split(' ')[-1]
        # else:
        #     home_last = player.slate_match.match.home_participant

        # if ' ' in player.slate_match.match.away_participant:
        #     away_last = player.slate_match.match.away_participant.split(' ')[-1]
        # else:
        #     away_last = player.slate_match.match.away_participant

        # game_info = GameInfo(
        #     home_team=home_last, 
        #     away_team=away_last,
        #     starts_at=player.slate_match.match.start_time,
        #     game_started=False
        # )

        fppg = player.get_percentile_projection(config.optimize_by_percentile)

        player = Player(
            player.slate_player.slate_player_id,
            first,
            last,
            ['D'],
            last,
            player.slate_player.salary,
            float(fppg),
            # game_info=game_info,
            min_deviation=-float(config.randomness) if config.randomness > 0.0 else None,
            max_deviation=float(config.randomness) if config.randomness > 0.0 else None,
            min_exposure=float(player.min_exposure),
            max_exposure=float(player.max_exposure),
        )

        player_list.append(player)
    return player_list


# def get_player_list(projections, config):
#     '''
#     Returns the player list on which to optimize
#     '''
#     player_list = []

#     for player in projections.filter(in_play=True):
#         fppg = None
#         if config.optimize_by == 'implied_win_pct':
#             fppg = numpy.average([float(player.implied_win_pct), float(player.implied_win_pct), float(player.implied_win_pct), float(player.sim_win_pct)]) * 100
#         elif config.optimize_by == 'sim_win_pct':
#             fppg = player.sim_win_pct * 100
#         elif config.optimize_by == 'projection':
#             fppg = player.projection
#         else:
#             fppg = player.ceiling

#         player = Player(
#             name=player.slate_player.name,
#             cost=player.slate_player.salary,
#             proj=float(fppg),
#             pos='P'
#         )

#         player_list.append(player)
#     return player_list

def generateRandomLineups(projections, num_lineups, num_drivers, salary_cap, timeout_seconds=60):
    lineups = []
    for count in range(0, num_lineups):
        total_salary = 999999
        duplicate = False

        while total_salary > salary_cap or duplicate:
            l = []
    
            # get drivers
            for _ in range(0, num_drivers):
                d = projections[(int)(abs(random.random() - random.random()) * projections.count())]
                while d in l:
                    d = projections[(int)(abs(random.random() - random.random()) * projections.count())]
                l.append(d)

            total_salary = sum([lp.salary for lp in l])
            
            # TODO: Handle duplicates
        
        lineups.append(l)
        print(count)
    
    return lineups
