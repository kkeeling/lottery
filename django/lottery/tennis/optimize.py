import numpy

from collections import namedtuple
from pydfs_lineup_optimizer import Site, Sport, Player, get_optimizer, exceptions
from pydfs_lineup_optimizer.solvers.mip_solver import MIPSolver

# from draftfast import rules
# from draftfast.optimize import run_multi
# from draftfast.orm import Player
# from draftfast.csv_parse import salary_download


GameInfo = namedtuple('GameInfo', ['home_team', 'away_team', 'starts_at', 'game_started'])


def find_optimal_from_sims(site, projections, sim_iteration=0):
    if site == 'draftkings':
        optimizer = get_optimizer(Site.DRAFTKINGS, Sport.TENNIS)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    players_list = get_player_list(
        projections, 
        sim_iteration=sim_iteration
    )
    optimizer.load_players(players_list)

    lineups = []

    try:
        optimized_lineups = optimizer.optimize(
            n=1,
            randomness=False
        )

        for lineup in optimized_lineups:
            lineups.append(lineup)
    except exceptions.LineupOptimizerException:
        print('Cannot generate more lineups')

    return lineups


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
        optimizer = get_optimizer(Site.DRAFTKINGS, Sport.TENNIS)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    
    # Salary
    if config.min_salary > 0:
        optimizer.set_min_salary_cap(config.min_salary)
    
    # Uniques
    optimizer.set_max_repeating_players(6 - config.uniques) 

    players_list = get_player_list(
        projections, 
        config=config
    )
    optimizer.load_players(players_list)
    optimizer.restrict_positions_for_opposing_team(['P'], ['P'])  # no opposing players

    lineups = []

    try:
        optimized_lineups = optimizer.optimize(
            n=num_lineups,
            randomness=True if config.randomness > 0.0 else False
        )

        for lineup in optimized_lineups:
            lineups.append(lineup)
    except exceptions.LineupOptimizerException:
        print('Cannot generate more lineups')

    return lineups


def get_player_list(projections, config=None, sim_iteration=None):
    '''
    Returns the player list on which to optimize
    '''
    if config is None and sim_iteration is None:
        raise Exception('At least one of config or sim_iteration must be not null')
    elif config is not None and sim_iteration is not None:
        raise Exception('Only one of config or sim_iteration may be not null')

    player_list = []

    if config is not None:
        projections = projections.filter(in_play=True)

    for player in projections:
        if ' ' in player.slate_player.name:
            first = player.slate_player.name.split(' ')[0]
            last = player.slate_player.name.split(' ')[-1]
        else:
            first = player.slate_player.name
            last = ''

        if ' ' in player.slate_match.match.home_participant:
            home_last = player.slate_match.match.home_participant.split(' ')[-1]
        else:
            home_last = player.slate_match.match.home_participant

        if ' ' in player.slate_match.match.away_participant:
            away_last = player.slate_match.match.away_participant.split(' ')[-1]
        else:
            away_last = player.slate_match.match.away_participant

        game_info = GameInfo(
            home_team=home_last, 
            away_team=away_last,
            starts_at=player.slate_match.match.start_time,
            game_started=False
        )

        fppg = None

        if config is not None:
            if config.optimize_by == 'implied_win_pct':
                fppg = numpy.average([float(player.implied_win_pct), float(player.implied_win_pct), float(player.implied_win_pct), float(player.sim_win_pct)]) * 100
            elif config.optimize_by == 'sim_win_pct':
                fppg = player.sim_win_pct * 100
            elif config.optimize_by == 'projection':
                fppg = player.projection
            else:
                fppg = player.ceiling
        else:
            fppg = player.sim_scores[sim_iteration]

        player = Player(
            player.slate_player.slate_player_id,
            first,
            last,
            ['P'],
            last,
            player.slate_player.salary,
            float(fppg),
            game_info=game_info,
            min_deviation=-float(config.randomness) if sim_iteration is None and config.randomness > 0.0 else None,
            max_deviation=float(config.randomness) if sim_iteration is None and config.randomness > 0.0 else None,
            min_exposure=float(player.min_exposure) if sim_iteration is None else None,
            max_exposure=float(player.max_exposure) if sim_iteration is None else None
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
