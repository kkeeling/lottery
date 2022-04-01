import random
import numpy

from collections import namedtuple
from pydfs_lineup_optimizer import Site, Sport, Player, get_optimizer, exceptions
from pydfs_lineup_optimizer.stacks import PlayersGroup


GameInfo = namedtuple('GameInfo', ['home_team', 'away_team', 'starts_at', 'game_started'])

def optimize(site, projections, groups, config, num_lineups=150):
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

    # Groups
    for group in groups:
        group_player_list = []
        for player in group.players.all(): 
            p = optimizer.get_player_by_id(player.player.slate_player.slate_player_id)

            if p is not None:
                group_player_list.append(p)
        
        if len(group_player_list) > 0:
            opto_group = PlayersGroup(
                group_player_list, 
                min_from_group=group.min_from_group,
                max_from_group=group.max_from_group
            )
            optimizer.add_players_group(opto_group)

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


def generateRandomLineups(projections, num_lineups, num_drivers, salary_cap, timeout_seconds=60):
    lineups = []
    for count in range(0, num_lineups):
        total_salary = 999999
        duplicate = False

        while total_salary > salary_cap or duplicate:
            duplicate = False
            l = []
    
            # get drivers
            for _ in range(0, num_drivers):
                d = projections[(int)(abs(random.random() - random.random()) * projections.count())]
                while d in l:
                    d = projections[(int)(abs(random.random() - random.random()) * projections.count())]
                l.append(d)

            total_salary = sum([lp.salary for lp in l])
            
            # TODO: Handle duplicates
            for l2 in lineups:
                for lp in l:
                    if lp not in l2:
                        duplicate = False
                        break
                    duplicate = True
                
                if duplicate:
                    print('found dup')
                    break
        
        lineups.append(l)
        print(count)
    
    return lineups


def get_random_lineup(projections, num_drivers, salary_cap):
    total_salary = 999999

    l = None
    while total_salary > salary_cap or total_salary < 44000:
        l = []

        # get drivers
        for _ in range(0, num_drivers):
            d = projections[(int)(abs(random.random() - random.random()) * projections.count())]
            while d in l:
                d = projections[(int)(abs(random.random() - random.random()) * projections.count())]
            l.append(d)

        total_salary = sum([lp.salary for lp in l])

    return l