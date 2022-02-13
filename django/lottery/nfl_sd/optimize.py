import traceback

from collections import namedtuple
from pydfs_lineup_optimizer import Site, Sport, Player, get_optimizer, \
    exceptions


GameInfo = namedtuple('GameInfo', ['home_team', 'away_team', 'starts_at', 'game_started'])


def optimize_for_captain(site, projections, config, num_lineups):
    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL_SINGLE_GAME, Sport.FOOTBALL)
    elif site == 'draftkings':
        optimizer = get_optimizer(Site.DRAFTKINGS_CAPTAIN_MODE, Sport.FOOTBALL)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    players_list = get_player_list(
        projections, 
        config.randomness
    )
    optimizer.load_players(players_list)
    print('  Loaded {} players.'.format(len(players_list)))

    lineups = []

    ### SETTINGS ###

    # Locked Players
    locked_players = projections.filter(locked=True)
    for locked_player in locked_players:
        player = optimizer.get_player_by_id(locked_player.slate_player.player_id)

        if player is not None:
            optimizer.add_player_to_lineup(player)

    # Salary
    if config.min_salary > 0:
        optimizer.set_min_salary_cap(config.min_salary)
    
    # Uniques
    optimizer.set_max_repeating_players(6 - config.uniques) 

    try:
        optimized_lineups = optimizer.optimize(
            n=num_lineups,
            randomness=(config.randomness > 0.0), 
        )
        count = 0
        for lineup in optimized_lineups:
            lineups.append(lineup)
            count += 1
    except exceptions.LineupOptimizerException:
        traceback.print_exc()
        print('Cannot generate more lineups')

    print('created {} lineups'.format(len(lineups)))

    return lineups


def get_player_list(projections, randomness=0.75):
    '''
    Returns the player list
    '''
    player_list = []

    for player_projection in projections:
        # Add players to pool based on config rules
        try:
            if ' ' in player_projection.name:
                first, last = player_projection.name.split(' ', 1)
            else:
                first = player_projection.name
                last = ''

            game_info = GameInfo(
                home_team=player_projection.game.home_team, 
                away_team=player_projection.game.away_team,
                starts_at=player_projection.game.game_date,
                game_started=False
            )

            player_position = [player_projection.roster_position]

            player = Player(
                player_projection.slate_player.player_id,
                first,
                'DST' if player_projection.position == 'DST' else last,
                player_position,
                player_projection.team,
                player_projection.salary,
                float(player_projection.projection),
                game_info=game_info,
                min_deviation=-float(randomness),
                max_deviation=float(randomness),
                max_exposure=float(player_projection.max_exposure / 100),
                min_exposure=float(player_projection.min_exposure / 100),
            )

            player_list.append(player)
        except:
            traceback.print_exc()
    return player_list  
