import itertools
import time

import numpy
import pandas

from django.db.models import Q

from nascar import models, filters

def run():
    build = models.SlateBuild.objects.get(id=2)

    start = time.time()
    projections = build.projections.filter(in_play=True).order_by('-slate_player__salary')
    player_outcomes = pandas.DataFrame([p.sim_scores for p in projections], index=[p.slate_player.slate_player_id for p in projections], dtype='float16')
    print(f'Getting player outcomes took {time.time() - start}s')
    # print(player_outcomes)
    # print(player_outcomes.info(verbose=True, memory_usage='deep'))

    # start = time.time()
    # player_outcomes = pandas.DataFrame.from_records(build.projections.filter(in_play=True).values('slate_player_id', 'sim_scores'))
    # player_outcomes = player_outcomes.set_index('slate_player_id')
    # print(f'Getting player outcomes took {time.time() - start}s')
    # print(player_outcomes)
    # print(player_outcomes.info(verbose=True, memory_usage='deep'))

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
    )  
    slate_lineups = filters.SlateLineupFilter(models.BUILD_TYPE_FILTERS.get(build.build_type), possible_lineups).qs
    print(f'Filtered slate lineups took {time.time() - start}s')
    
    start = time.time()
    # df_build_lineups = pandas.DataFrame.from_records(slate_lineups.values('id', 'player_1', 'player_2', 'player_3', 'player_4', 'player_5', 'player_6'))
    df_build_lineups = pandas.DataFrame(slate_lineups.values_list('player_1', 'player_2', 'player_3', 'player_4', 'player_5', 'player_6'), index=list(slate_lineups.values_list('id', flat=True)))
    df_build_lineups['build_id'] = build.id
    df_build_lineups = df_build_lineups.apply(pandas.to_numeric, downcast='unsigned')
    print(f'  Initial dataframe took {time.time() - start}s')
    # df_build_lineups = df_build_lineups.set_index('id')
    print(df_build_lineups)
    # print(df_build_lineups.info(verbose=True, memory_usage='deep'))
    start = time.time()
    df_build_lineups = df_build_lineups.apply(lambda x: numpy.array(player_outcomes.loc[str(x[0])]) + numpy.array(player_outcomes.loc[str(x[1])]) + numpy.array(player_outcomes.loc[str(x[2])]) + numpy.array(player_outcomes.loc[str(x[3])]) + numpy.array(player_outcomes.loc[str(x[4])]) + numpy.array(player_outcomes.loc[str(x[5])]), axis=1, result_type='expand')
    print(f'  Sim scores lineups took {time.time() - start}s')
    # print(df_build_lineups.info(verbose=True, memory_usage='deep'))
    print(df_build_lineups)
    
    start = time.time()
    df_ranks = df_build_lineups.rank(method='min')
    df_ranks = df_ranks.apply(pandas.to_numeric, downcast='unsigned')
    print(f'  Ranking took {time.time() - start}s')
    # print(df_ranks.info(verbose=True, memory_usage='deep'))
    print(df_ranks)

    # start = time.time()
    # matchups  = list(itertools.product(slate_lineups.values_list('id', flat=True), field_lineups.values_list('id', flat=True)))
    # df_matchups = pandas.DataFrame(matchups, columns=['build_lineup', 'field_lineup'])
    # df_matchups['wins'] = df_matchups.apply(lambda x: numpy.count_nonzero((numpy.array(df_build_lineups.loc[x['build_lineup'], 'sim_scores']) - numpy.array(df_field_lineups.loc[x['field_lineup'], 'sim_scores'])) > 0.0), axis=1)
    # df_matchups = df_matchups.drop(['field_lineup'], axis=1)
    # print(f'Matchups took {time.time() - start}s. There are {len(matchups)} matchups.')

    # start = time.time()
    # df_lineups = df_matchups.groupby('build_lineup').sum()
    # df_lineups['slate_lineup_id'] = df_lineups.index
    # df_lineups['win_rate'] = df_lineups['wins'] / (build.sim.iterations * field_lineups.count())
    # df_lineups['median'] = df_lineups.apply(lambda x: numpy.median(numpy.array(df_build_lineups.loc[x['slate_lineup_id'], 'sim_scores'])), axis=1)
    # df_lineups['s75'] = df_lineups.apply(lambda x: numpy.percentile(numpy.array(df_build_lineups.loc[x['slate_lineup_id'], 'sim_scores']), 75.0), axis=1)
    # df_lineups['s90'] = df_lineups.apply(lambda x: numpy.percentile(numpy.array(df_build_lineups.loc[x['slate_lineup_id'], 'sim_scores']), 90.0), axis=1)
    # print(df_lineups)
    # print(f'Win Rates took {time.time() - start}s. There are {len(df_lineups.index)} lineups.')
