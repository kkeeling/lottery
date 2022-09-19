import itertools
import numpy as np
import pandas as pd
import random
import time

from django.db.models.aggregates import Count, Sum, Avg
from django.db.models import F, Q
from nfl import models

NUM_RBS = 2
NUM_WRS = 3
NUM_TES = 1
NUM_DSTS = 1
NUM_FLEX = 1

def get_random_lineup(slate, qb_id, rb_combos, wr_combos, tes, flexes, dsts):
    random_rbs = rb_combos[random.randrange(0, len(rb_combos))]
    random_wrs = wr_combos[random.randrange(0, len(wr_combos))]
    random_te = tes[random.randrange(0, len(tes))]
    random_flex = flexes[random.randrange(0, len(flexes))]
    random_dst = dsts[random.randrange(0, len(dsts))]

    l = [qb_id, random_rbs[0], random_rbs[1], random_wrs[0], random_wrs[1], random_wrs[2], random_te, random_flex, random_dst]
    total_salary = slate.get_projections().filter(
        slate_player__player_id__in=l
    ).aggregate(total_salary=Sum('slate_player__salary')).get('total_salary')

    return (l, total_salary)

def is_lineup_valid(slate, l):
    players = slate.get_projections().filter(
        slate_player__player_id__in=l
    )
    
    num_qbs = players.aggregate(num_qbs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='QB'))).get('num_qbs')
    if num_qbs > 1:
        return False
    
    num_wrs = players.aggregate(num_wrs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='WR'))).get('num_wrs')
    if num_wrs > 4:
        return False
    
    num_rbs = players.aggregate(num_rbs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='RB'))).get('num_rbs')
    if num_rbs > 3:
        return False
    
    num_tes = players.aggregate(num_tes=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='TE'))).get('num_tes')
    if num_tes > 2:
        return False

    # prevent duplicate players
    visited = set()
    dup = [x for x in l if x in visited or (visited.add(x) or False)]
    if len(dup) > 0:
        return False

    return True

def run():
    # lineups = []
    # build = models.FindWinnerBuild.objects.get(id=1)
    # build = models.SlateBuild.objects.get(id=30965)


    top_start = time.time()
    slate = models.Slate.objects.get(id=116)
    dst_label = slate.dst_label
    
    start = time.time()
    slate_players = slate.players.filter(projection__in_play=True).order_by('-salary')
    salaries = {}
    for p in slate_players:
        salaries[p.player_id] = p.salary
    print(f'Finding players and salaries took {time.time() - start}s. There are {slate_players.count()} players in the player pool.')

    start = time.time()
    qbs = list(slate.get_projections().filter(
        slate_player__site_pos='QB',
        in_play=True
    ).order_by('-projection').values_list('slate_player__player_id', flat=True))
    rbs = list(slate.get_projections().filter(
        slate_player__site_pos='RB',
        in_play=True
    ).order_by('-projection').values_list('slate_player__player_id', flat=True))
    wrs = list(slate.get_projections().filter(
        slate_player__site_pos='WR',
        in_play=True
    ).order_by('-projection').values_list('slate_player__player_id', flat=True))
    tes = list(slate.get_projections().filter(
        slate_player__site_pos='TE',
        in_play=True
    ).order_by('-projection').values_list('slate_player__player_id', flat=True))
    dsts = list(slate.get_projections().filter(
        slate_player__site_pos=dst_label,
        in_play=True
    ).order_by('-projection').values_list('slate_player__player_id', flat=True))
    print(f'Filtering player positions took {time.time() - start}s')

    salary_thresholds = slate.salary_thresholds
    lineups = []

    start = time.time()
    rb_combos = list(itertools.combinations(rbs, 2))
    print(f'RB combos took {time.time() - start}s. There are {len(rb_combos)} combinations.')

    start = time.time()
    wr_combos = list(itertools.combinations(wrs, 3))
    print(f'WR combos took {time.time() - start}s. There are {len(wr_combos)} combinations.')
    
    start = time.time()
    projections = slate.get_projections().filter(in_play=True).order_by('-slate_player__salary')
    player_outcomes = {}
    for p in projections:
        player_outcomes[p.slate_player.player_id] = np.array(p.sim_scores)
    print(f'Getting player outcomes took {time.time() - start}s')

    for qb in qbs:
        print(f'qb = {qb}')

        # start = time.time()
        # lineup_combos = list(itertools.product(rb_combos, wr_combos, tes, dsts))
        # lineup_combos = list(itertools.combinations(rbs+rbs+wrs+wrs+wrs, 5))
        # print(f'  Lineup combos took {time.time() - start}s. There are {len(lineup_combos)} combos.')

        start = time.time()
        for _ in range(0, 100):
            l, total_salary = get_random_lineup(slate, qb, rb_combos, wr_combos, tes, list(rbs) + list(wrs), dsts)

            '''
            TODO: Add additional constraints
                - No duplicate lineups
            '''
            while (total_salary < salary_thresholds[0] or total_salary > salary_thresholds[1] or not is_lineup_valid(slate, l)):
                l, total_salary = get_random_lineup(slate, qb, rb_combos, wr_combos, tes, list(rbs) + list(wrs), dsts)

            l.append(total_salary)  ## append total salary to end of lineup array so we can make a dataframe
            lineups.append(l)
        print(f'Lineup selection took {time.time() - start}s')

        start = time.time()
        df_lineups = pd.DataFrame(lineups, columns=[
            'qb_id',
            'rb1_id',
            'rb2_id',
            'wr1_id',
            'wr2_id',
            'wr3_id',
            'te_id',
            'flex_id',
            'dst_id',
            'total_salary',
        ])
        print(f'Dataframe took {time.time() - start}s')
        # print(df_lineups)

        start = time.time()
        df_lineups['sim_scores'] = df_lineups.apply(lambda x: player_outcomes.get(str(x[0])) + player_outcomes.get(str(x[1])) + player_outcomes.get(str(x[2])) + player_outcomes.get(str(x[3])) + player_outcomes.get(str(x[4])) + player_outcomes.get(str(x[5])) + player_outcomes.get(str(x[6])) + player_outcomes.get(str(x[7])) + player_outcomes.get(str(x[8])), axis=1)
        print(f'Sim scores took {time.time() - start}s')
        print(df_lineups)

        # race lineups to find the best
        # start = time.time()
        # df_matchups = df_lineups_sim_scores.rank(method="min", ascending=False).median(axis=1)
        # print(f'Matchups took {time.time() - start}s.')
        # print(df_matchups)

        print(f'Process took {time.time() - top_start}s')
        break


    #     start = time.time()
    #     stack_partners = build.projections.filter(
    #         slate_player__site_pos__in=['RB', 'WR', 'TE'],
    #         slate_player__team__in=[qb.team, qb.get_opponent()],
    #         in_play=True
    #     ).order_by('-projection')
    #     print(f'  Getting stack partners took {time.time() - start}s')

    #     start = time.time()
    #     r = 2
    #     stack_combos = list(itertools.combinations(stack_partners.values_list('id', flat=True), r))
    #     print(f'  There are {len(stack_combos)} possible stack combos. Calculation took {time.time() - start}s')

    #     start = time.time()
    #     mini_combos = []
        
    #     for game in build.slate.games.all():
    #         if game != qb.game:
    #             mini_stack_partners = build.projections.filter(
    #                 slate_player__site_pos__in=['RB', 'WR', 'TE'],
    #                 slate_player__slate_game=game,
    #                 in_play=True
    #             ).order_by('-projection')
                
    #             s = 2
    #             mini_combos += list(itertools.combinations(mini_stack_partners.values_list('id', flat=True), s))
        
    #     print(f'  There are {len(mini_combos)} possible mini-stack combos. Calculation took {time.time() - start}s')

    #     start = time.time()
    #     other_players = build.projections.filter(
    #         slate_player__site_pos__in=['RB', 'WR'],
    #         in_play=True
    #     ).exclude(
    #         slate_player__team__in=[qb.team, qb.get_opponent()]
    #     )
    #     other_combos = list(itertools.combinations(other_players.values_list('id', flat=True), 2))
    #     print(f'  There are {len(other_combos)} possible combos of 4 non-stacked players. Calculation took {time.time() - start}s')

        # Get 1000 random lineups
    #     start = time.time()
    #     for i in range(0, 100):
    #         l, total_salary = get_random_lineup(build, qb, rb_combos, wr_combos, tes, list(rbs) + list(wrs), dsts)

    #         '''
    #         TODO: Add additional constraints
    #             - No duplicate lineups
    #         '''
    #         while (total_salary < 495000 or total_salary > 50000 or not is_lineup_valid(build, l)):
    #             l, total_salary = get_random_lineup(build, qb, rb_combos, wr_combos, tes, list(rbs) + list(wrs), dsts)

    #         lineups.append(l)
    #     print(f'  Lineup selection took {time.time() - start}s')

    #     break

    # df_lineups = pd.DataFrame(lineups)
    # print(df_lineups)
    # df_lineups.to_csv('data/lineups.csv')


# def is_lineup_valid(build, l):
#     players = build.slate.get_projections().filter(
#         id__in=l
#     )
    
#     num_wrs = players.aggregate(num_wrs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='WR'))).get('num_wrs')
#     if num_wrs > 4:
#         return False
    
#     num_rbs = players.aggregate(num_rbs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='RB'))).get('num_rbs')
#     if num_rbs > 3:
#         return False

#     visited = set()
#     dup = [x for x in l if x in visited or (visited.add(x) or False)]
#     if len(dup) > 0:
#         return False

#     return True

# def get_random_lineup(build, qb, stack_combos, mini_combos, other_combos, tes, dsts):
#     random_stack = stack_combos[random.randrange(0, len(stack_combos))]
#     random_mini_stack = mini_combos[random.randrange(0, len(mini_combos))]
#     random_other_combo = other_combos[random.randrange(0, len(other_combos))]
#     random_te = tes[random.randrange(0, len(tes))]
#     random_dst = dsts[random.randrange(0, len(dsts))]

#     l = [qb.id, random_stack[0], random_stack[1], random_mini_stack[0], random_mini_stack[1], random_other_combo[0], random_other_combo[1], random_te, random_dst]
#     total_salary = build.projections.filter(
#         id__in=l
#     ).aggregate(total_salary=Sum('slate_player__salary')).get('total_salary')

#     return (l, total_salary)

# def get_random_lineup(slate, qb, rb_combos, wr_combos, tes, flexes, dsts):
#     random_rbs = rb_combos[random.randrange(0, len(rb_combos))]
#     random_wrs = wr_combos[random.randrange(0, len(wr_combos))]
#     random_te = tes[random.randrange(0, len(tes))]
#     random_flex = flexes[random.randrange(0, len(flexes))]
#     random_dst = dsts[random.randrange(0, len(dsts))]

#     l = [qb, random_rbs[0], random_rbs[1], random_wrs[0], random_wrs[1], random_wrs[2], random_te, random_flex, random_dst]
#     total_salary = slate.get_projections().filter(
#         id__in=l
#     ).aggregate(total_salary=Sum('slate_player__salary')).get('total_salary')

#     return (l, total_salary)