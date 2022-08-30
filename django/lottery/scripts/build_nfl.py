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

def run():
    lineups = []
    build = models.SlateBuild.objects.get(id=327)
    # build = models.SlateBuild.objects.get(id=30965)

    qbs = build.projections.filter(
        slate_player__site_pos='QB',
        in_play=True
    ).order_by('-projection')
    

    for qb in qbs:
        print(qb)
        start = time.time()
        tes = build.projections.filter(
            slate_player__site_pos='TE',
            in_play=True
        ).order_by('-projection').values_list('id', flat=True)
        dsts = build.projections.filter(
            slate_player__site_pos='D',
            in_play=True
        ).order_by('-projection').values_list('id', flat=True)
        print(f'  Getting players & positions took {time.time() - start}s')

        start = time.time()
        stack_partners = build.projections.filter(
            slate_player__site_pos__in=['RB', 'WR', 'TE'],
            slate_player__team__in=[qb.team, qb.get_opponent()],
            in_play=True
        ).order_by('-projection')
        print(f'  Getting stack partners took {time.time() - start}s')

        start = time.time()
        r = 2
        stack_combos = list(itertools.combinations(stack_partners.values_list('id', flat=True), r))
        print(f'  There are {len(stack_combos)} possible stack combos. Calculation took {time.time() - start}s')

        start = time.time()
        mini_combos = []
        
        for game in build.slate.games.all():
            if game != qb.game:
                mini_stack_partners = build.projections.filter(
                    slate_player__site_pos__in=['RB', 'WR', 'TE'],
                    slate_player__slate_game=game,
                    in_play=True
                ).order_by('-projection')
                
                s = 2
                mini_combos += list(itertools.combinations(mini_stack_partners.values_list('id', flat=True), s))
        
        print(f'  There are {len(mini_combos)} possible mini-stack combos. Calculation took {time.time() - start}s')

        start = time.time()
        other_players = build.projections.filter(
            slate_player__site_pos__in=['RB', 'WR'],
            in_play=True
        ).exclude(
            slate_player__team__in=[qb.team, qb.get_opponent()]
        )
        other_combos = list(itertools.combinations(other_players.values_list('id', flat=True), 2))
        print(f'  There are {len(other_combos)} possible combos of 4 non-stacked players. Calculation took {time.time() - start}s')

        # Get 1000 random lineups
        start = time.time()
        for i in range(0, 1000):
            l, total_salary = get_random_lineup(build, qb, stack_combos, mini_combos, other_combos, tes, dsts)

            '''
            TODO: Add additional constraints
                - No duplicate lineups
            '''
            while (total_salary < 59000 or total_salary > 60000 or not is_lineup_valid(build, l)):
                l, total_salary = get_random_lineup(build, qb, stack_combos, mini_combos, other_combos, tes, dsts)

            lineups.append(l)
        print(f'  Lineup selection took {time.time() - start}s')

    df_lineups = pd.DataFrame(lineups)
    df_lineups.to_csv('data/lineups.csv')


def is_lineup_valid(build, l):
    players = build.projections.filter(
        id__in=l
    )
    
    num_wrs = players.aggregate(num_wrs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='WR'))).get('num_wrs')
    if num_wrs > 4:
        return False
    
    num_rbs = players.aggregate(num_rbs=Count('slate_player__site_pos', filter=Q(slate_player__site_pos='RB'))).get('num_rbs')
    if num_rbs > 5:
        return False

    visited = set()
    dup = [x for x in l if x in visited or (visited.add(x) or False)]
    if len(dup) > 0:
        return False

    return True

def get_random_lineup(build, qb, stack_combos, mini_combos, other_combos, tes, dsts):
    random_stack = stack_combos[random.randrange(0, len(stack_combos))]
    random_mini_stack = mini_combos[random.randrange(0, len(mini_combos))]
    random_other_combo = other_combos[random.randrange(0, len(other_combos))]
    random_te = tes[random.randrange(0, len(tes))]
    random_dst = dsts[random.randrange(0, len(dsts))]

    l = [qb.id, random_stack[0], random_stack[1], random_mini_stack[0], random_mini_stack[1], random_other_combo[0], random_other_combo[1], random_te, random_dst]
    total_salary = build.projections.filter(
        id__in=l
    ).aggregate(total_salary=Sum('slate_player__salary')).get('total_salary')

    return (l, total_salary)