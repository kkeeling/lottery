import csv
import datetime
import decimal
import math
import random
import string
import traceback

from collections import namedtuple
from django.core.management.base import BaseCommand
from django.db.models import ObjectDoesNotExist
from fcpro_fd_nfl import models
from pulp import PULP_CBC_CMD
from pydfs_lineup_optimizer import Site, Sport, Player, PlayersGroup, get_optimizer, \
    PositionsStack, exceptions, Stack, TeamStack, AfterEachExposureStrategy, LineupOptimizer, LineupOptimizerException
from pydfs_lineup_optimizer.solvers.pulp_solver import PuLPSolver
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer

from . import optimizer_settings

GameInfo = namedtuple('GameInfo', ['home_team', 'away_team', 'starts_at', 'game_started'])


class CustomPuLPSolver(PuLPSolver):
    LP_SOLVER = PULP_CBC_CMD(verbose=False, msg=False, threads=8, options=['preprocess off'])


def optimize_for_stack(site, stack, slate_players, slate_teams, config, num_lineups):
    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL, solver=CustomPuLPSolver)
    elif site == 'draftkings':
        if len(config.flex_positions) > 1:
            if 'RB' not in config.flex_positions:
                optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoRBFlexSettings, solver=CustomPuLPSolver)
            elif 'TE' not in config.flex_positions and stack.num_tes() <= 1:
                optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoTEFlexSettings, solver=CustomPuLPSolver)
            else:
                optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL, solver=CustomPuLPSolver)
        else:
            optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL, solver=CustomPuLPSolver)
    else:
        raise Exception('{} is not a supported dfs site.'.format(site))

    players_list = get_player_list_for_game_stack(
        slate_players, 
        stack.qb.slate_player,
        stack,
        randomness=config.randomness,
        use_stack_only=True,
        allow_rb_qb_stack=config.allow_rb_qb_from_same_team,
        allow_opp_rb_qb_stack=config.allow_rb_qb_from_opp_team,
        max_dst_exposure=config.max_dst_exposure,
        stack_positions=config.qb_stack_positions
    )
    optimizer.load_players(players_list)

    lineups = []

    ### SETTINGS ###
    dst_label = 'D' if site == 'fanduel' else 'DST'

    # Locked Players
    locked_players = slate_players.filter(projection__locked=True)
    for locked_player in locked_players:
        player = optimizer.get_player_by_id(locked_player.player_id)

        if player is not None:
            optimizer.add_player_to_lineup(player)

        if player is not None:
            optimizer.add_player_to_lineup(player)

    # At least 1 Group
    at_least_one_players = slate_players.filter(projection__at_least_one_in_lineup=True)
    al1_players_list = []
    for player in at_least_one_players:
        p = optimizer.get_player_by_id(player.player_id)

        if p is not None:
            al1_players_list.append(p)
    
    if len(al1_players_list) > 0:
        al1_players_group = PlayersGroup(al1_players_list, min_from_group=1)
        optimizer.add_players_group(al1_players_group)

    # At least 2 Group
    at_least_two_players = slate_players.filter(projection__at_least_two_in_lineup=True)
    al2_players_list = []
    for player in at_least_two_players:
        p = optimizer.get_player_by_id(player.player_id)

        if p is not None:
            al2_players_list.append(p)
    
    if len(al2_players_list) > 0:
        al2_players_group = PlayersGroup(al2_players_list, min_from_group=1)
        optimizer.add_players_group(al2_players_group)

    # Salary
    if config.min_salary > 0:
        optimizer.set_min_salary_cap(config.min_salary)

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
            except LineupOptimizerException:
                traceback.print_exc()

    # RBs from Same Game
    if not config.allow_rbs_from_same_game:
        same_game_rb_groups = get_same_game_rb_groups(players_list)
        optimizer.add_stack(Stack(same_game_rb_groups))

    try:
        optimized_lineups = optimizer.optimize(
            n=num_lineups 
        )
        count = 0
        for lineup in optimized_lineups:
            lineups.append(lineup)
            count += 1
    except exceptions.LineupOptimizerException:
        print('Cannot generate more lineups for: {}'.format(stack.qb.name))

    return lineups


def get_player_list_for_game_stack(slate_players, game_qb, stack, randomness=0.75, use_stack_only=True, allow_rb_qb_stack=False, allow_opp_rb_qb_stack=False, max_dst_exposure=1.0, stack_positions=['WR', 'TE'], opp_stack_positions=['WR', 'TE']):
    '''
    Returns the player list on which to optimize based on a game stack with game_qb
    '''
    player_list = []

    for slate_player in slate_players:
        # Add players to pool based on config rules
        valid_player = True
        try:
            # If player is in-play
            if slate_player.projection.in_play:
                # If player is stack-only and not in the same game as qb, not a valid player
                if use_stack_only and slate_player.projection.stack_only and slate_player.game != game_qb.game:
                    valid_player = False
                elif not allow_rb_qb_stack and slate_player.site_pos == 'RB' and slate_player.team == game_qb.team and not stack.contains_slate_player(slate_player):
                    valid_player = False
                elif not allow_opp_rb_qb_stack and slate_player.site_pos == 'RB' and slate_player.team == get_slate_player_opponent(game_qb) and not stack.contains_slate_player(slate_player):
                    valid_player = False
                elif slate_player.site_pos == 'QB' and slate_player != game_qb:
                    valid_player = False
                
                if valid_player:
                    if ' ' in slate_player.name:
                        first, last = slate_player.name.split(' ', 1)
                    else:
                        first = slate_player.name
                        last = ''

                    home_team, away_team = slate_player.game.split('_')
                    game_info = GameInfo(
                        home_team=home_team, 
                        away_team=away_team,
                        starts_at=None,
                        game_started=False
                    )

                    player = Player(
                        slate_player.player_id,
                        first,
                        'DST' if slate_player.site_pos == 'DST' else last,
                        ['D' if slate_player.site_pos == 'DST' and slate_player.slate.site == 'fanduel' else slate_player.site_pos],
                        slate_player.team,
                        slate_player.salary,
                        float(slate_player.fantasy_points),
                        game_info=game_info
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
