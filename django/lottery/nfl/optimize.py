import csv
import datetime
import decimal
import math
import logging
from numpy.core.fromnumeric import trace
import pandas
import random
import string
import traceback

from collections import namedtuple
from django.core.management.base import BaseCommand
from pydfs_lineup_optimizer import Site, Sport, Player, get_optimizer, \
    exceptions, LineupOptimizer
from pydfs_lineup_optimizer.stacks import PlayersGroup, Stack, GameStack
from pydfs_lineup_optimizer.player_pool import PlayerFilter
from pydfs_lineup_optimizer.solvers.mip_solver import MIPSolver
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer

from . import optimizer_settings

logger = logging.getLogger(__name__)

GameInfo = namedtuple('GameInfo', ['home_team', 'away_team', 'starts_at', 'game_started'])


def optimize(site, projections, num_lineups=1):
    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
    elif site == 'draftkings':
        optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL)
    elif site == 'yahoo':
        optimizer = get_optimizer(Site.YAHOO, Sport.FOOTBALL)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    player_list = []

    for player_projection in projections:
        if ' ' in player_projection.name:
            first, last = player_projection.name.split(' ', 1)
        else:
            first = player_projection.name
            last = ''

        if player_projection.slate_player.slate_game is None:
            continue
        
        slate_game = player_projection.slate_player.slate_game.game
        game_info = GameInfo(
            home_team=slate_game.home_team, 
            away_team=slate_game.away_team,
            starts_at=slate_game.game_date,
            game_started=False
        )

        player = Player(
            player_projection.slate_player.player_id,
            first,
            'DST' if player_projection.position == 'DST' else last,
            ['D' if player_projection.position == 'DST' and player_projection.slate_player.slate.site == 'fanduel' else player_projection.position],
            player_projection.team,
            player_projection.salary,
            float(player_projection.balanced_projection),
            game_info=game_info
        )

        player_list.append(player)
    
    optimizer.load_players(player_list)

    lineups = []
    try:
        optimized_lineups = optimizer.optimize(
            n=num_lineups 
        )

        for lineup in optimized_lineups:
            lineups.append(lineup)
    except exceptions.LineupOptimizerException:
        traceback.print_exc()

    return lineups


def optimize_for_ownership(site, projections, num_lineups=1, min_sal_pct=0.99):
    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
        min_salary = int(60000 * min_sal_pct)
    elif site == 'draftkings':
        optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL)
        min_salary = int(50000 * min_sal_pct)
    elif site == 'yahoo':
        optimizer = get_optimizer(Site.YAHOO, Sport.FOOTBALL)
        min_salary = int(200 * min_sal_pct)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    player_list = []

    for player_projection in projections:
        if ' ' in player_projection.name:
            first, last = player_projection.name.split(' ', 1)
        else:
            first = player_projection.name
            last = ''

        if player_projection.slate_player.slate_game is None:
            continue
        
        slate_game = player_projection.slate_player.slate_game.game
        game_info = GameInfo(
            home_team=slate_game.home_team, 
            away_team=slate_game.away_team,
            starts_at=slate_game.game_date,
            game_started=False
        )

        player = Player(
            player_projection.slate_player.player_id,
            first,
            'DST' if player_projection.position == 'DST' else last,
            ['D' if player_projection.position == 'DST' and player_projection.slate_player.slate.site == 'fanduel' else player_projection.position],
            player_projection.team,
            player_projection.salary,
            float(player_projection.ownership_projection),
            game_info=game_info
        )

        player_list.append(player)
    
    optimizer.load_players(player_list)
    optimizer.set_min_salary_cap(min_salary)

    group_player_list = []
    for player in projections.filter(slate_player__site_pos='TE'): 
        p = optimizer.get_player_by_id(player.slate_player.player_id)

        if p is not None:
            group_player_list.append(p)
    
    if len(group_player_list) > 0:
        opto_group = PlayersGroup(
            group_player_list, 
            min_from_group=1,
            max_from_group=1
        )
        optimizer.add_players_group(opto_group)
    
    lineups = []
    try:
        optimized_lineups = optimizer.optimize(
            n=num_lineups 
        )

        for lineup in optimized_lineups:
            lineups.append(lineup)
    except exceptions.LineupOptimizerException:
        traceback.print_exc()

    return lineups


def optimize_for_showdown(site, projections, num_lineups=1, min_sal_pct=0.99):
    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL_SINGLE_GAME, Sport.FOOTBALL)
        min_salary = int(60000 * min_sal_pct)
    elif site == 'draftkings':
        optimizer = get_optimizer(Site.DRAFTKINGS_CAPTAIN_MODE, Sport.FOOTBALL)
        min_salary = int(50000 * min_sal_pct)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    player_list = []

    for player_projection in projections:
        if ' ' in player_projection.name:
            first, last = player_projection.name.split(' ', 1)
        else:
            first = player_projection.name
            last = ''

        if player_projection.slate_player.slate_game is None:
            continue
        
        slate_game = player_projection.slate_player.slate_game.game
        game_info = GameInfo(
            home_team=slate_game.home_team, 
            away_team=slate_game.away_team,
            starts_at=slate_game.game_date,
            game_started=False
        )

        player = Player(
            player_projection.slate_player.player_id,
            first,
            'DST' if player_projection.position == 'DST' else last,
            [player_projection.slate_player.roster_position],
            player_projection.team,
            player_projection.salary,
            float(player_projection.projection),
            game_info=game_info
        )

        player_list.append(player)
    
    optimizer.load_players(player_list)
    optimizer.set_min_salary_cap(min_salary)
    
    lineups = []
    try:
        optimized_lineups = optimizer.optimize(
            n=num_lineups 
        )

        for lineup in optimized_lineups:
            lineups.append(lineup)
    except exceptions.LineupOptimizerException:
        traceback.print_exc()

    return lineups


def naked_simulate(site, projections, config, player_sim_index=0, optimals_per_sim_outcome=10):
    lineups = []

    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
    elif site == 'draftkings':
        optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    player_list = []

    for player_projection in projections:
        if ' ' in player_projection.name:
            first, last = player_projection.name.split(' ', 1)
        else:
            first = player_projection.name
            last = ''

        slate_game = player_projection.slate_player.slate_game.game
        game_info = GameInfo(
            home_team=slate_game.home_team, 
            away_team=slate_game.away_team,
            starts_at=slate_game.game_date,
            game_started=False
        )

        player_position = player_projection.position
        if player_projection.position == 'DST' and player_projection.slate_player.slate.site == 'fanduel':
            player_position = ['D']
        elif '/' in player_projection.position:
            player_position = player_projection.position.split('/')
        else:
            player_position = [player_projection.position]

        if player_projection.sim_scores is not None and len(player_projection.sim_scores) > 0:
            player = Player(
                player_projection.slate_player.player_id,
                first,
                'DST' if player_projection.position == 'DST' else last,
                player_position,
                player_projection.team,
                player_projection.salary,
                float(player_projection.sim_scores[player_sim_index]),
                game_info=game_info
            )

            player_list.append(player)
    
    optimizer.player_pool.load_players(player_list)

    ### SETTINGS ###
    dst_label = 'D' if site == 'fanduel' else 'DST'

    # Salary
    # if config.min_salary > 0:
    #     optimizer.set_min_salary_cap(config.min_salary)

    ### STACKING RULES ###

    # Players vs DST
    # optimizer.restrict_positions_for_opposing_team([dst_label], ['QB', 'RB', 'WR', 'TE'], max_allowed=config.num_players_vs_dst)

    # RBs from same team (always disallowed)
    # same_team_stack_tuple = (('RB', 'RB'),)

    # RB/DST Stack
    # if not config.allow_dst_rb_stack:
    #     same_team_stack_tuple += ((dst_label, 'RB'),)

    # QB/DST Stack
    # if not config.allow_qb_dst_from_same_team:
    #     same_team_stack_tuple += (('QB', dst_label),)

    # QB/RB Stack
    # if not config.allow_rb_qb_from_same_team:
    #     same_team_stack_tuple += (('QB', 'RB'),)

    # optimizer.restrict_positions_for_same_team(*same_team_stack_tuple)

    # RBs from Same Game
    # if not config.allow_rbs_from_same_game and not config.allow_rb_qb_from_opp_team:
    #     optimizer.restrict_positions_for_opposing_team(['RB'], ['QB', 'RB'])
    # elif not config.allow_rbs_from_same_game:
    #     optimizer.restrict_positions_for_opposing_team(['RB'], ['RB'])
    # elif not config.allow_rb_qb_from_opp_team:
    #     optimizer.restrict_positions_for_opposing_team(['RB'], ['QB'])

    # Game Stacks
    # optimizer.set_total_teams(min_teams=3)
    # optimizer.add_stack(GameStack(size=3, min_from_team=1))
    
    # For each QB, create a stack with his pass in-play pass catchers and the opposing pass catchers
    # for qb in qbs:
    #     stack_players = []
    #     for pos in config.qb_stack_positions:
    #         stack_players += optimizer.player_pool.get_players(PlayerFilter(
    #                 positions=[pos],
    #                 teams=[qb.team]
    #             ))
    #     qb_team_stack = PlayersGroup(
    #         stack_players,
    #         max_from_group=config.game_stack_size - 1 if len(config.opp_qb_stack_positions) == 0 else config.game_stack_size - 2,
    #         depends_on=optimizer.player_pool.get_player_by_id(qb.slate_player.player_id),
    #         strict_depend=False
    #     )
    #     optimizer.add_players_group(qb_team_stack)

    #     if len(config.opp_qb_stack_positions) > 0:
    #         stack_players = []
    #         for pos in config.opp_qb_stack_positions:
    #             stack_players += optimizer.player_pool.get_players(PlayerFilter(
    #                     positions=[pos],
    #                     teams=[qb.get_opponent()]
    #                 ))
    #         qb_opp_team_stack = PlayersGroup(
    #             stack_players,
    #             max_from_group=1,
    #             depends_on=optimizer.player_pool.get_player_by_id(qb.slate_player.player_id),
    #             strict_depend=False
    #         )
    #         optimizer.add_players_group(qb_opp_team_stack)

    try:
        optimized_lineups = optimizer.optimize(
            n=optimals_per_sim_outcome 
        )

        for lineup in (optimized_lineups):
            # qb = qbs.get(slate_player__player_id = lineup.players[0].id)
            # stack = ','.join([p.id for p in lineup.players if p.team == qb.team or p.team == qb.get_opponent()])
            lineups.append([p.id for p in lineup.players] + [lineup.salary_costs])

        return lineups
    except exceptions.GenerateLineupException:
        traceback.print_exc()

        return []


def simulate(site, projections, qbs, config, player_sim_index=0, optimals_per_sim_outcome=10):
    # For each iteration of player outcomes...
        # For each contest simulation...
            # Make all lineups greater that score enough to be top 3 (or 100 lineups, whichever is smaller)
            # Each lineup should be stored in a pandas dataframe

    lineups = []

    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
    elif site == 'draftkings':
        optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    player_list = []

    for player_projection in projections:
        if ' ' in player_projection.name:
            first, last = player_projection.name.split(' ', 1)
        else:
            first = player_projection.name
            last = ''

        slate_game = player_projection.slate_player.slate_game.game
        game_info = GameInfo(
            home_team=slate_game.home_team, 
            away_team=slate_game.away_team,
            starts_at=slate_game.game_date,
            game_started=False
        )

        player_position = player_projection.position
        if player_projection.position == 'DST' and player_projection.slate_player.slate.site == 'fanduel':
            player_position = ['D']
        elif '/' in player_projection.position:
            player_position = player_projection.position.split('/')
        else:
            player_position = [player_projection.position]

        if player_projection.sim_scores is not None and len(player_projection.sim_scores) > 0:
            player = Player(
                player_projection.slate_player.player_id,
                first,
                'DST' if player_projection.position == 'DST' else last,
                player_position,
                player_projection.team,
                player_projection.salary,
                float(player_projection.sim_scores[player_sim_index]),
                game_info=game_info
            )

            player_list.append(player)
    
    optimizer.player_pool.load_players(player_list)

    ### SETTINGS ###
    dst_label = 'D' if site == 'fanduel' else 'DST'

    # Salary
    if config.min_salary > 0:
        optimizer.set_min_salary_cap(config.min_salary)

    ### STACKING RULES ###

    # Players vs DST
    optimizer.restrict_positions_for_opposing_team([dst_label], ['QB', 'RB', 'WR', 'TE'], max_allowed=config.num_players_vs_dst)

    # RBs from same team (always disallowed)
    same_team_stack_tuple = (('RB', 'RB'),)

    # RB/DST Stack
    if not config.allow_dst_rb_stack:
        same_team_stack_tuple += ((dst_label, 'RB'),)

    # QB/DST Stack
    if not config.allow_qb_dst_from_same_team:
        same_team_stack_tuple += (('QB', dst_label),)

    # QB/RB Stack
    if not config.allow_rb_qb_from_same_team:
        same_team_stack_tuple += (('QB', 'RB'),)

    optimizer.restrict_positions_for_same_team(*same_team_stack_tuple)

    # RBs from Same Game
    if not config.allow_rbs_from_same_game and not config.allow_rb_qb_from_opp_team:
        optimizer.restrict_positions_for_opposing_team(['RB'], ['QB', 'RB'])
    elif not config.allow_rbs_from_same_game:
        optimizer.restrict_positions_for_opposing_team(['RB'], ['RB'])
    elif not config.allow_rb_qb_from_opp_team:
        optimizer.restrict_positions_for_opposing_team(['RB'], ['QB'])

    # Game Stacks
    optimizer.set_total_teams(min_teams=3)
    optimizer.add_stack(GameStack(size=3, min_from_team=1))
    
    # For each QB, create a stack with his pass in-play pass catchers and the opposing pass catchers
    for qb in qbs:
        stack_players = []
        for pos in config.qb_stack_positions:
            stack_players += optimizer.player_pool.get_players(PlayerFilter(
                    positions=[pos],
                    teams=[qb.team]
                ))
        qb_team_stack = PlayersGroup(
            stack_players,
            max_from_group=config.game_stack_size - 1 if len(config.opp_qb_stack_positions) == 0 else config.game_stack_size - 2,
            depends_on=optimizer.player_pool.get_player_by_id(qb.slate_player.player_id),
            strict_depend=False
        )
        optimizer.add_players_group(qb_team_stack)

        if len(config.opp_qb_stack_positions) > 0:
            stack_players = []
            for pos in config.opp_qb_stack_positions:
                stack_players += optimizer.player_pool.get_players(PlayerFilter(
                        positions=[pos],
                        teams=[qb.get_opponent()]
                    ))
            qb_opp_team_stack = PlayersGroup(
                stack_players,
                max_from_group=1,
                depends_on=optimizer.player_pool.get_player_by_id(qb.slate_player.player_id),
                strict_depend=False
            )
            optimizer.add_players_group(qb_opp_team_stack)

    try:
        optimized_lineups = optimizer.optimize(
            n=optimals_per_sim_outcome 
        )

        for lineup in (optimized_lineups):
            qb = qbs.get(slate_player__player_id = lineup.players[0].id)
            stack = ','.join([p.id for p in lineup.players if p.team == qb.team or p.team == qb.get_opponent()])
            lineups.append([p.id for p in lineup.players] + [lineup.salary_costs] + [stack])

        return lineups
    except exceptions.GenerateLineupException:
        traceback.print_exc()

        return []


def optimize_for_stack(site, stack, projections, slate_teams, config, num_lineups, groups=[], for_optimals=False):
    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
        # if config.game_stack_size == 3:
        #     if config.use_mini_stacks:
        #         if stack.player_2 is not None:
        #             optimizer = LineupOptimizer(optimizer_settings.FanduelNFLSettingsMax3PerTeam)
        #         else:
        #             optimizer = LineupOptimizer(optimizer_settings.FanduelNFLSettingsMax2PerTeam)
        #     else:
        #         optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
        # elif config.game_stack_size == 4:
        #     if config.use_mini_stacks:
        #         optimizer = LineupOptimizer(optimizer_settings.FanduelNFLSettingsMax3PerTeamMax5Games)
        #     else:
        #         optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
    elif site == 'draftkings':
        optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL)
        # if config.game_stack_size == 3:
        #     if config.use_mini_stacks:
        #         if stack.player_2 is not None:
        #             if 'RB' not in config.flex_positions:
        #                 optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoRBFlexSettingsMax3PerTeam)
        #             elif 'TE' not in config.flex_positions:
        #                 optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoTEFlexSettingsMax3PerTeam)
        #             else:
        #                 optimizer = LineupOptimizer(optimizer_settings.DraftKingsNFLSettingsMax3PerTeam)
        #         else:
        #             if 'RB' not in config.flex_positions:
        #                 optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoRBFlexSettingsMax2PerTeam)
        #             elif 'TE' not in config.flex_positions:
        #                 optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoTEFlexSettingsMax2PerTeam)
        #             else:
        #                 optimizer = LineupOptimizer(optimizer_settings.DraftKingsNFLSettingsMax2PerTeam)
        #     else:
        #         if 'RB' not in config.flex_positions:
        #             optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoRBFlexSettings)
        #         elif 'TE' not in config.flex_positions:
        #             optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoTEFlexSettings)
        #         else:
        #             optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL)
        # elif config.game_stack_size == 4:
        #     if config.use_mini_stacks:
        #         if 'RB' not in config.flex_positions:
        #             optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoRBFlexSettingsMax3PerTeamMax5Games)
        #         elif 'TE' not in config.flex_positions:
        #             optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoTEFlexSettingsMax3PerTeamMax5Games)
        #         else:
        #             optimizer = LineupOptimizer(optimizer_settings.DraftKingsNFLSettingsMax3PerTeamMax5Games)
        #     else:
        #         if 'RB' not in config.flex_positions:
        #             optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoRBFlexSettings)
        #         elif 'TE' not in config.flex_positions:
        #             optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoTEFlexSettings)
        #         else:
        #             optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL)
    elif site == 'yahoo':
        if config.game_stack_size == 3:
            if config.use_mini_stacks:
                if stack.player_2 is not None:
                    optimizer = LineupOptimizer(optimizer_settings.YahooNFLSettingsMax3PerTeam)
                else:
                    optimizer = LineupOptimizer(optimizer_settings.YahooNFLSettingsMax2PerTeam)
            else:
                optimizer = get_optimizer(Site.YAHOO, Sport.FOOTBALL)
        elif config.game_stack_size == 4:
            if config.use_mini_stacks:
                optimizer = LineupOptimizer(optimizer_settings.YahooNFLSettingsMax3PerTeamMax5Games)
            else:
                optimizer = get_optimizer(Site.Yahoo, Sport.FOOTBALL)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    players_list = get_player_list_for_game_stack(
        projections, 
        stack.qb.slate_player,
        stack,
        randomness=config.randomness,
        use_stack_only=True,
        allow_qb_dst_stack=config.allow_qb_dst_from_same_team,
        allow_rb_qb_stack=config.allow_rb_qb_from_same_team,
        allow_opp_rb_qb_stack=config.allow_rb_qb_from_opp_team,
        max_dst_exposure=config.max_dst_exposure,
        for_optimals=for_optimals
    )
    optimizer.load_players(players_list)
    logger.info('  Loaded {} players.'.format(len(players_list)))

    lineups = []

    ### SETTINGS ###
    if site == 'fanduel':
        dst_label = 'D' 
    elif site == 'yahoo':
        dst_label = 'DEF' 
    else:
        dst_label = 'DST'

    # Locked Players
    locked_players = projections.filter(locked=True)
    for locked_player in locked_players:
        player = optimizer.get_player_by_id(locked_player.slate_player.player_id)

        if player is not None:
            optimizer.add_player_to_lineup(player)

    # Groups
    for group in groups:
        group_player_list = []
        for player in group.players.all(): 
            p = optimizer.get_player_by_id(player.slate_player.player_id)

            if p is not None:
                group_player_list.append(p)
        
        if len(group_player_list) > 0:
            opto_group = PlayersGroup(
                group_player_list, 
                min_from_group=group.min_from_group,
                max_from_group=group.max_from_group
            )
            optimizer.add_players_group(opto_group)

    # Salary
    if config.min_salary > 0:
        optimizer.set_min_salary_cap(config.min_salary)
    
    # Uniques
    if not for_optimals:
        optimizer.set_max_repeating_players(9 - config.uniques) 

    ### LIMIT RULES ###

    # Limit Flex Position
    d = {}
    for p in config.flex_positions:
        d[p] = 1
    if len(d) == 1 and get_num_tes_in_list(stack.players) < 2:  # allow TE in flex when game stack has 2 TEs
        optimizer.set_players_with_same_position(d)

    ### STACKING RULES ###

    # Players vs DST
    optimizer.restrict_positions_for_opposing_team([dst_label], ['QB', 'RB', 'WR', 'TE'], max_allowed=config.num_players_vs_dst)

    # RB/DST Stack
    if not config.allow_dst_rb_stack:
        optimizer.restrict_positions_for_same_team((dst_label, 'RB'))

    # Game Stack -- Lock players for incoming stack
    for p in stack.players:  
        player = optimizer.get_player_by_id(p.slate_player.player_id)

        if player is not None:
            try:
                optimizer.add_player_to_lineup(player)
            except exceptions.LineupOptimizerException as e:
                logger.info(e)

    # RBs from Same Game
    if not config.allow_rbs_from_same_game:
        same_game_rb_groups = get_same_game_rb_groups(players_list)
        optimizer.add_stack(Stack(same_game_rb_groups))

    # optimizer.force_positions_for_opposing_team(('RB', 'WR'), ('RB', 'TE'), ('WR', 'WR'), ('WR', 'TE'))

    try:
        optimized_lineups = optimizer.optimize(
            n=num_lineups,
            randomness=not for_optimals, 
        )
        count = 0
        for lineup in optimized_lineups:
            lineups.append(lineup)
            count += 1
    except exceptions.LineupOptimizerException:
        logger.info('Cannot generate more lineups for: {}'.format(stack.qb.name))

    logger.info('created {} lineups'.format(len(lineups)))

    return lineups


def get_player_list_for_game_stack(projections, game_qb, stack, randomness=0.75, use_stack_only=True, allow_rb_qb_stack=False, allow_qb_dst_stack=False, allow_opp_rb_qb_stack=False, max_dst_exposure=1.0, for_optimals=False):
    '''
    Returns the player list on which to optimize based on a game stack with game_qb
    '''
    player_list = []

    for player_projection in projections:
        # Add players to pool based on config rules
        valid_player = True
        try:
            # If player is in-play
            if player_projection.in_play:
                stack_player_ids = [
                    stack.qb.slate_player.player_id,
                    stack.player_1.slate_player.player_id
                ]
                if stack.player_2 is not None:
                    stack_player_ids.append(stack.player_2.slate_player.player_id)
                if stack.opp_player is not None:
                    stack_player_ids.append(stack.opp_player.slate_player.player_id)
                    
                # If player is stack-only and not in the same game as qb, not a valid player
                if use_stack_only and player_projection.stack_only and player_projection.slate_player.slate_game != game_qb.slate_game:
                    valid_player = False
                elif not allow_qb_dst_stack and (player_projection.position == 'DST' or player_projection.position == 'D' or player_projection.position == 'DEF') and player_projection.team == game_qb.team and not stack.contains_slate_player(player_projection.slate_player):
                    valid_player = False
                elif not allow_rb_qb_stack and player_projection.position == 'RB' and player_projection.team == game_qb.team and not stack.contains_slate_player(player_projection.slate_player):
                    valid_player = False
                elif not allow_opp_rb_qb_stack and player_projection.position == 'RB' and player_projection.team == get_slate_player_opponent(game_qb) and not stack.contains_slate_player(player_projection.slate_player):
                    valid_player = False
                elif player_projection.position == 'QB' and player_projection.slate_player != game_qb:
                    valid_player = False
                
                if valid_player:
                    if ' ' in player_projection.name:
                        first, last = player_projection.name.split(' ', 1)
                    else:
                        first = player_projection.name
                        last = ''

                    slate_game = player_projection.slate_player.get_slate_game().game
                    game_info = GameInfo(
                        home_team=slate_game.home_team, 
                        away_team=slate_game.away_team,
                        starts_at=slate_game.game_date,
                        game_started=False
                    )

                    player_position = player_projection.position
                    if player_projection.position == 'DST' and player_projection.slate_player.slate.site == 'fanduel':
                        player_position = ['D']
                    elif player_projection.position == 'DST' and player_projection.slate_player.slate.site == 'yahoo':
                        player_position = ['DEF']
                    elif '/' in player_projection.position:
                        player_position = player_projection.position.split('/')
                    else:
                        player_position = [player_projection.position]

                    player = Player(
                        player_projection.slate_player.player_id,
                        first,
                        'DST' if player_projection.position == 'DST' else last,
                        player_position,
                        player_projection.team,
                        player_projection.salary,
                        float(player_projection.balanced_projection) if not for_optimals else float(player_projection.slate_player.fantasy_points),
                        game_info=game_info,
                        min_deviation=-float(randomness) if not for_optimals else None,
                        max_deviation=float(randomness) if not for_optimals else None,
                        max_exposure=float(player_projection.max_exposure / 100) if not for_optimals else None,
                        min_exposure=float(player_projection.min_exposure / 100) if not for_optimals else None,
                    )

                    player_list.append(player)
        except:
            traceback.print_exc()
    return player_list  


def get_same_game_rb_groups(players):
    groups = []

    for player in players:
        # if the player is a RB create a group with all other RB in the same game
        if player.positions[0] == 'RB':
            player_group_list = [player]

            # for each remaining player, add to group if in same game
            for player2 in players:
                if player2 != player and player2.positions[0] == 'RB' and player2.game_info.home_team == player.game_info.home_team:
                    player_group_list.append(player2)
            
            # create players group
            group = PlayersGroup(
                players=player_group_list,
                max_from_group=1
            )
            groups.append(group)
    return groups


def get_player_opponent(player):
    if player.game_info.home_team == player.team:
        return player.game_info.away_team
    return player.game_info.home_team


def get_slate_player_opponent(slate_player):
    return slate_player.game.replace(slate_player.team, '').replace('_', '')


def export_pool(players, slate):
    with open('{}_playerpool.csv'.format(slate.name), 'w') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(['Player', 'Position', 'Salary', 'Team', 'Projection'])

        for player in players:
            csv_writer.writerow([player.full_name, player.positions[0], player.salary, player.team, player.fppg])


def evaluate_lineup(lineup):
    # return false if lineup contains no secondary stack
    qb = lineup.players[0]
    for player in lineup.players:
        # if player isn't in primary stack
        if player.team != qb.game_info.home_team and player.team != qb.game_info.away_team:
            player_opponent = player.game_info.home_team if player.team == player.game_info.away_team else player.game_info.away_team

            # if player opponent in lineup, return true (exlude dst)
            if lineup.players[1].team == player_opponent:
                return True
            elif lineup.players[2].team == player_opponent:
                return True
            elif lineup.players[3].team == player_opponent:
                return True
            elif lineup.players[4].team == player_opponent:
                return True
            elif lineup.players[5].team == player_opponent:
                return True
            elif lineup.players[6].team == player_opponent:
                return True
            elif lineup.players[7].team == player_opponent:
                return True
            elif lineup.players[8].team == player_opponent:
                return True
    
    return False


def get_mav_similarity_scores(all_lineups):
    '''
    Returns a list of similarity scores as tuples, (lineup, score)
    '''
    sim_scores = []

    # Create list of lineups as strings from all_lineups
    all_lineups_as_str = list(map(get_lineup_as_str, all_lineups))

    # Create vectors
    vectors = CountVectorizer().fit_transform(all_lineups_as_str).toarray()

    # Calculate cosine similarity between each vector and the remaining vectors using product
    for index, v1 in enumerate(vectors):
        score = 1
        for index2, v2 in enumerate(vectors):
            if index != index2:
                score *= cosine_sim_vectors(v1, v2)
        sim_scores.append((all_lineups[index], score))
    
    return sim_scores


def get_num_tes_in_list(player_list):
    num_tes = 0
    for p in player_list:
        try:
            if p.positions[0] == 'TE':
                num_tes += 1
        except AttributeError:
            if p.position == 'TE':
                num_tes += 1
    
    return num_tes


def get_lineup_as_str(lineup):
    return ', '.join([p.full_name for p in lineup.players])


def cosine_sim_vectors(vec1, vec2):
    vec1 = vec1.reshape(1, -1)
    vec2 = vec2.reshape(1, -1)

    return cosine_similarity(vec1, vec2)[0][0]
