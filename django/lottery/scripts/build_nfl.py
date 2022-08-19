import itertools
import numpy as np
import pandas as pd
import time

from nfl import models

NUM_RBS = 2
NUM_WRS = 3
NUM_TES = 1
NUM_DSTS = 1
NUM_FLEX = 1

def run():
    build = models.SlateBuild.objects.get(id=30965)

    qbs = build.projections.filter(
        slate_player__site_pos='QB',
        in_play=True
    ).order_by('-projection')

    for qb in qbs:
        print(qb)
        # start = time.time()
        # rbs = build.projections.filter(
        #     slate_player__site_pos='RB',
        #     in_play=True
        # ).order_by('-projection')
        # wrs = build.projections.filter(
        #     slate_player__site_pos='WR',
        #     in_play=True
        # ).order_by('-projection')
        # tes = build.projections.filter(
        #     slate_player__site_pos='TE',
        #     in_play=True
        # ).order_by('-projection')
        # dsts = build.projections.filter(
        #     slate_player__site_pos='D',
        #     in_play=True
        # ).order_by('-projection')
        # print(f'  Getting players & positions took {time.time() - start}s')

        # start = time.time()
        # rb_combos = list(itertools.combinations(rbs.values_list('slate_player__name', flat=True), NUM_RBS))
        # print(f'  There are {len(rb_combos)} possible RB combos. Calculation took {time.time() - start}s')
        # start = time.time()
        # wr_combos = list(itertools.combinations(wrs.values_list('slate_player__name', flat=True), NUM_WRS))
        # print(f'  There are {len(wr_combos)} possible WR combos. Calculation took {time.time() - start}s')
        # start = time.time()
        # lineup_combos = list(itertools.product(rb_combos, wr_combos, tes.values_list('slate_player__name', flat=True), dsts.values_list('slate_player__name', flat=True)))
        # print(f'  There are {len(lineup_combos)} possible lineup combos. Calculation took {time.time() - start}s')

        start = time.time()
        stack_partners = build.projections.filter(
            slate_player__site_pos__in=['RB', 'WR', 'TE'],
            slate_player__team__in=[qb.team, qb.get_opponent()],
            in_play=True
        ).order_by('-projection')
        print(f'  Getting stack partners took {time.time() - start}s')

        start = time.time()
        r = 2
        stack_combos = list(itertools.combinations(stack_partners.values_list('slate_player__name', flat=True), r))
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
                mini_combos += list(itertools.combinations(mini_stack_partners.values_list('slate_player__name', flat=True), s))
        
        print(f'  There are {len(mini_combos)} possible mini-stack combos. Calculation took {time.time() - start}s')

        # start = time.time()
        # total_combos = list(itertools.product(stack_combos, mini_combos))
        # print(f'  There are {len(total_combos)} possible stack + mini-stack combos. Calculation took {time.time() - start}s')
        # start = time.time()
        # df_combos = pd.DataFrame([[qb.slate_player.name, t[0][0], t[0][1], t[1][0], t[1][1]] for t in total_combos], columns=['qb', 'player_1', 'player_2', 'mini_1', 'mini_2'])
        # print(f'  Combos dataframe took {time.time() - start}s')
        # print(df_combos)

        start = time.time()
        other_players = build.projections.filter(
            slate_player__site_pos__in=['RB', 'WR', 'TE', 'D'],
            in_play=True
        ).exclude(
            slate_player__team__in=[qb.team, qb.get_opponent()]
        )
        other_combos = list(itertools.combinations(other_players.values_list('slate_player__name', flat=True), 4))
        print(f'  There are {len(other_combos)} possible combos of 4 non-stacked players. Calculation took {time.time() - start}s')

        start = time.time()
        lineup_combos = list(itertools.product(stack_combos, mini_combos, other_combos))
        print(f'  There are {len(lineup_combos)} lineup combos stacking 3 from same game plus a ministack. Calculation took {time.time() - start}s')
        break