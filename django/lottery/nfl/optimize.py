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
from pydfs_lineup_optimizer import Site, Sport, Player, PlayersGroup, get_optimizer, \
    PositionsStack, exceptions, Stack, TeamStack, AfterEachExposureStrategy, LineupOptimizer
from pydfs_lineup_optimizer.sites.fanduel.classic.settings import FanDuelSettings
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer

from . import optimizer_settings

GameInfo = namedtuple('GameInfo', ['home_team', 'away_team', 'starts_at', 'game_started'])


def optimize_for_stack(site, stack, slate_players, slate_teams, config, num_lineups):
    print('  Building for {}'.format(stack))
    if site == 'fanduel':
        optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
    elif site == 'draftkings':
        if len(config.flex_positions) > 1:
            if 'RB' not in config.flex_positions:
                optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoRBFlexSettings)
            elif 'TE' not in config.flex_positions:
                optimizer = LineupOptimizer(optimizer_settings.DraftKingsFootballNoTEFlexSettings)
            else:
                optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL)
        else:
            optimizer = get_optimizer(Site.DRAFTKINGS, Sport.FOOTBALL)
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
    print('  Loaded {} players.'.format(len(players_list)))

    lineups = []

    ### SETTINGS ###
    dst_label = 'D' if site == 'fanduel' else 'DST'

    # Locked Players
    locked_players = slate_players.filter(projection__locked=True)
    for locked_player in locked_players:
        player = optimizer.get_player_by_id(locked_player.player_id)

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
        al2_players_group = PlayersGroup(al2_players_list, min_from_group=2)
        optimizer.add_players_group(al2_players_group)

    # Salary
    if config.min_salary > 0:
        optimizer.set_min_salary_cap(config.min_salary)
    
    # Uniques
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
                print(e)

    # RBs from Same Game
    if not config.allow_rbs_from_same_game:
        same_game_rb_groups = get_same_game_rb_groups(players_list)
        optimizer.add_stack(Stack(same_game_rb_groups))

    try:
        optimized_lineups = optimizer.optimize(
            n=num_lineups,
            randomness=True, 
        )
        count = 0
        for lineup in optimized_lineups:
            lineups.append(lineup)
            count += 1
    except exceptions.LineupOptimizerException:
        print('Cannot generate more lineups for: {}'.format(stack.qb.name))

    print('created {} lineups'.format(len(lineups)))

    return lineups


def get_slate_qbs(slate):
    return slate.players.filter(site_pos='QB', projection__in_play=True)

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
                    slate_game = slate_player.get_slate_game().game
                    game_info = GameInfo(
                        home_team=slate_game.home_team, 
                        away_team=slate_game.away_team,
                        starts_at=slate_game.game_date,
                        game_started=False
                    )

                    player = Player(
                        slate_player.player_id,
                        first,
                        'DST' if slate_player.site_pos == 'DST' else last,
                        ['D' if slate_player.site_pos == 'DST' and slate_player.slate.site == 'fanduel' else slate_player.site_pos],
                        slate_player.team,
                        slate_player.salary,
                        float(slate_player.projection.balanced_projection),
                        game_info=game_info,
                        min_deviation=-float(randomness),
                        max_deviation=float(randomness),
                        max_exposure=float(max_dst_exposure) if slate_player.site_pos == 'DST' or slate_player.site_pos == 'D' else None
                    )

                    player_list.append(player)
        except:
            traceback.print_exc()
    return player_list  

def get_slate_team_player_max_dict(slate_teams, game):
    '''
    Returns the max number of players allowed in lineups for every team on slate except those in game stack
    '''
    slate_team_dict = {}
    for slate_team in slate_teams:
        if slate_team not in game:
            slate_team_dict[slate_team] = 1

    return slate_team_dict

def get_game_stack_groups(qb, game_stack_players, am1_players=[], use_iseo=True, min_player_count=3):
    if min_player_count != 3 and min_player_count != 4:
        raise Exception('InvalidParameter: min_player_count must be 3 or 4')

    groups = []

    # calculate sum of all projections for both qb team and opp team
    # and separate players into teams
    team_players = []
    opp_players = []
    for player in game_stack_players:
        if player.team == qb.team:
            team_players.append(player)
        else:
            opp_players.append(player)

    team_players.sort(key=lambda p: p.fppg, reverse=True)
    opp_players.sort(key=lambda p: p.fppg, reverse=True)

    team_has_all_stack_only = (len(am1_players) == len(team_players))

    stack_combos = []
    if min_player_count == 3:
        # For each player, loop over opposing player to make a group for each possible stack combination,
        # such that each group's exposure reflects the median projection of each of the players
        for (index, player) in enumerate(team_players):
            for opp_player in opp_players:
                stack_combos.append({
                    'players': [qb, player, opp_player],
                    'projection': sum(p.fppg for p in [qb, player, opp_player])
                })
    elif min_player_count == 4:
        # For each player, loop over the remaining players and then loop over opposing player to make a group for each possible stack combination,
        # such that each group's exposure reflects the median projection of each of the players
        for (index, player) in enumerate(team_players):
            if team_has_all_stack_only or player not in am1_players:
                for player2 in team_players[index+1:]:
                    if player2 != player:  # don't include previously selected player
                        for opp_player in opp_players:
                            stack_combos.append({
                                'players': [qb, player, player2, opp_player],
                                'projection': sum(p.fppg for p in [qb, player, player2, opp_player])
                            })
            
    sum_all_stacks = sum(s.get('projection') for s in stack_combos)
    for stack in stack_combos:
        max_exposure = stack.get('projection') / sum_all_stacks
        print(stack.get('players'), max_exposure)
        group = PlayersGroup(
            players=stack.get('players'),
            max_exposure=max_exposure if use_iseo else None
        )
        groups.append(group)

    return groups

def get_mini_stack_groups(exclude_game, players, num_players):
    if num_players < 2 or num_players > 3:
        raise ValueError('num_players must be 2 or 3')
    groups = []

    for player in players:
        if player.game_info.home_team not in exclude_game:
            # if the player is a WR or TE, create a group for each combination other WR, RB, and TE in the same game where at least 1 opposing player is in the group
            if player.positions[0] in ['WR', 'TE']:
                # first, add player to group
                same_team_list = get_players_on_same_team(players, player, ['WR', 'TE'])
                opposing_team_list = get_players_on_opp_team(players, player, ['RB', 'WR', 'TE'])

                # next loop over opposing players and create a group with player, opposing player to ensure at least 1 player from opposing team is in every group
                for opp_player in opposing_team_list:

                    # if num player == 3, then add a third player to the group from the same game, that isn't already in the group
                    if num_players == 3:
                        same_game_list = same_team_list + opposing_team_list
                        for player3 in same_game_list:
                            if player3 != player and player3 != opp_player:
                                
                                # create players group
                                group = PlayersGroup(
                                    players=[player, opp_player, player3],
                                    max_exposure=0.05
                                )
                                groups.append(group)
                    else:
                        # create players group
                        group = PlayersGroup(
                            players=[player, opp_player]
                        )
                        groups.append(group)    
    return groups

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

def get_players_on_same_team(all_players, player, positions=None):
    same_team = []
    for p in all_players:
        if p != player and p.team == player.team:
            if p.positions[0] in positions or positions is None:
                same_team.append(p)

    return same_team

def get_players_on_opp_team(all_players, player, positions=None):
    opp_team = []
    opponent = get_player_opponent(player)
    for p in all_players:
        if p.team == opponent:
            if p.positions[0] in positions or positions is None:
                opp_team.append(p)

    return opp_team

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

def write_lineups_to_csv(slate, lineups):
    with open('{}_backtest.csv'.format(slate.name), mode='w+') as f:
        optimal_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for (index, lineup) in enumerate(lineups):
            optimal_writer.writerow([
                index,
                lineup.fantasy_points_projection,
                lineup.players[0].full_name,
                lineup.players[1].full_name,
                lineup.players[2].full_name,
                lineup.players[3].full_name,
                lineup.players[4].full_name,
                lineup.players[5].full_name,
                lineup.players[6].full_name,
                lineup.players[7].full_name,
                lineup.players[8].full_name,
                lineup.players[0].team,
                lineup.players[1].team,
                lineup.players[2].team,
                lineup.players[3].team,
                lineup.players[4].team,
                lineup.players[5].team,
                lineup.players[6].team,
                lineup.players[7].team,
                lineup.players[8].team,
                '{}_{}'.format(lineup.players[0].game_info.home_team, lineup.players[0].game_info.away_team),
                '{}_{}'.format(lineup.players[1].game_info.home_team, lineup.players[1].game_info.away_team),
                '{}_{}'.format(lineup.players[2].game_info.home_team, lineup.players[2].game_info.away_team),
                '{}_{}'.format(lineup.players[3].game_info.home_team, lineup.players[3].game_info.away_team),
                '{}_{}'.format(lineup.players[4].game_info.home_team, lineup.players[4].game_info.away_team),
                '{}_{}'.format(lineup.players[5].game_info.home_team, lineup.players[5].game_info.away_team),
                '{}_{}'.format(lineup.players[6].game_info.home_team, lineup.players[6].game_info.away_team),
                '{}_{}'.format(lineup.players[7].game_info.home_team, lineup.players[7].game_info.away_team),
                '{}_{}'.format(lineup.players[8].game_info.home_team, lineup.players[8].game_info.away_team),
                lineup.players[0].positions[0],
                lineup.players[1].positions[0],
                lineup.players[2].positions[0],
                lineup.players[3].positions[0],
                lineup.players[4].positions[0],
                lineup.players[5].positions[0],
                lineup.players[6].positions[0],
                lineup.players[7].positions[0],
                lineup.players[8].positions[0],
                lineup.players[0].salary,
                lineup.players[1].salary,
                lineup.players[2].salary,
                lineup.players[3].salary,
                lineup.players[4].salary,
                lineup.players[5].salary,
                lineup.players[6].salary,
                lineup.players[7].salary,
                lineup.players[8].salary,
                lineup.players[0].fppg,
                lineup.players[1].fppg,
                lineup.players[2].fppg,
                lineup.players[3].fppg,
                lineup.players[4].fppg,
                lineup.players[5].fppg,
                lineup.players[6].fppg,
                lineup.players[7].fppg,
                lineup.players[8].fppg
            ])
