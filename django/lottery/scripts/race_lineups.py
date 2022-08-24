import gc
import itertools
import time

import numpy
import pandas

from django.db.models.aggregates import Count, Sum, Avg
from django.db.models import Q, F

from nascar import models, filters

def run():
    # build = models.SlateBuild.objects.get(id=4)
    build = models.SlateBuild.objects.get(id=122)

    start = time.time()
    projections = build.projections.filter(in_play=True).order_by('-slate_player__salary')
    # player_outcomes = pandas.DataFrame([p.sim_scores for p in projections], index=[p.slate_player.slate_player_id for p in projections], dtype='float16')
    player_outcomes = {}
    for p in projections:
        player_outcomes[p.slate_player.slate_player_id] = numpy.array(p.sim_scores)
    print(f'Getting player outcomes took {time.time() - start}s')

    start = time.time()
    not_in_play = build.projections.filter(in_play=False).values_list('slate_player_id', flat=True)
    possible_lineups = build.slate.possible_lineups.exclude(
        Q(
            Q(player_1_id__in=not_in_play) | 
            Q(player_2_id__in=not_in_play) | 
            Q(player_3_id__in=not_in_play) | 
            Q(player_4_id__in=not_in_play) | 
            Q(player_5_id__in=not_in_play) | 
            Q(player_6_id__in=not_in_play)
        )
    ).annotate(
        pos_sum=F('player_1__builds__starting_position') + F('player_2__builds__starting_position') + F('player_3__builds__starting_position') + F('player_4__builds__starting_position') + F('player_5__builds__starting_position') + F('player_6__builds__starting_position')
    )
    slate_lineups = filters.SlateLineupFilter(models.BUILD_TYPE_FILTERS.get(build.build_type), possible_lineups.filter(pos_sum__gte=150)).qs.order_by('id')
    print(f'Filtered slate lineups took {time.time() - start}s. There are {slate_lineups.count()} lineups.')

    start = time.time()
    df_slate_lineups = pandas.DataFrame(slate_lineups.values_list('player_1', 'player_2', 'player_3', 'player_4', 'player_5', 'player_6'), index=list(slate_lineups.values_list('id', flat=True)))
    df_slate_lineups['build_id'] = build.id
    df_slate_lineups['slate_lineup_id'] = df_slate_lineups.index
    # df_slate_lineups = df_slate_lineups.apply(pandas.to_numeric, downcast='unsigned')
    print(f'  Initial dataframe took {time.time() - start}s')

    start = time.time()
    df_slate_lineups = df_slate_lineups.apply(lambda x: player_outcomes.get(str(x[0])) + player_outcomes.get(str(x[1])) + player_outcomes.get(str(x[2])) + player_outcomes.get(str(x[3])) + player_outcomes.get(str(x[4])) + player_outcomes.get(str(x[5])), axis=1, result_type='expand')
    df_slate_lineups = df_slate_lineups.apply(pandas.to_numeric, downcast='float')
    print(f'  Sim scores took {time.time() - start}s')

    start = time.time()
    field_lineups = build.field_lineups.all().order_by('id')
    print(f'Getting field lineups took {time.time() - start}s.')
    start = time.time()
    df_field_lineups = pandas.DataFrame(field_lineups.values_list('slate_lineup__player_1', 'slate_lineup__player_2', 'slate_lineup__player_3', 'slate_lineup__player_4', 'slate_lineup__player_5', 'slate_lineup__player_6'), index=list(field_lineups.values_list('id', flat=True)))
    df_field_lineups = df_field_lineups.apply(pandas.to_numeric, downcast='unsigned')
    print(f'  Initial dataframe took {time.time() - start}s')
    start = time.time()
    df_field_lineups = df_field_lineups.apply(lambda x: player_outcomes.get(str(x[0])) + player_outcomes.get(str(x[1])) + player_outcomes.get(str(x[2])) + player_outcomes.get(str(x[3])) + player_outcomes.get(str(x[4])) + player_outcomes.get(str(x[5])), axis=1, result_type='expand')
    df_field_lineups = df_field_lineups.apply(pandas.to_numeric, downcast='float')
    print(f'  Sim scores took {time.time() - start}s')

    start = time.time()
    matchups  = list(itertools.product(slate_lineups.values_list('id', flat=True), field_lineups.values_list('id', flat=True)))
    df_matchups = pandas.DataFrame(matchups, columns=['slate_lineup_id', 'field_lineup_id'])
    df_matchups['win_rate'] = df_matchups.apply(lambda x: numpy.count_nonzero((numpy.array(df_slate_lineups.loc[x['slate_lineup_id']]) - numpy.array(df_field_lineups.loc[x['field_lineup_id']])) > 0.0) / build.sim.iterations, axis=1)
    df_matchups = df_matchups[(df_matchups.win_rate >= 0.58)]
    df_matchups['build_id'] = build.id
    df_matchups = df_matchups.apply(pandas.to_numeric, downcast='float')
    print(f'Matchups took {time.time() - start}s. There are {len(matchups)} matchups.')
