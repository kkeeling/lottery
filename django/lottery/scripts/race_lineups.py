import gc
import itertools
import time

import numpy
import pandas

from django.db.models import Q

from nascar import models, filters

def run():
    # build = models.SlateBuild.objects.get(id=4)
    build = models.SlateBuild.objects.get(id=116)

    build.matchups.all().delete()
    build.lineups.all().delete()

    start = time.time()
    projections = build.projections.filter(in_play=True).order_by('-slate_player__salary')
    player_outcomes = pandas.DataFrame.from_records(projections.values('slate_player_id', 'sim_scores'), index=[p.slate_player.slate_player_id for p in projections])
    # player_outcomes = pandas.DataFrame([p.sim_scores for p in projections], index=[p.slate_player.slate_player_id for p in projections], dtype='float16')
    # player_outcomes['slate_player_id'] = [p.slate_player.slate_player_id for p in projections]
    # print(player_outcomes)
    # player_outcomes = {}
    # for p in projections:
    #     player_outcomes[p.slate_player.slate_player_id] = numpy.array(p.sim_scores)
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
    )  
    slate_lineups = filters.SlateLineupFilter(models.BUILD_TYPE_FILTERS.get(build.build_type), possible_lineups).qs.order_by('id')
    print(f'Filtered slate lineups took {time.time() - start}s')
    
    # start = time.time()
    df_slate_lineups = pandas.DataFrame(slate_lineups.values_list('player_1', 'player_2', 'player_3', 'player_4', 'player_5', 'player_6'), index=list(slate_lineups.values_list('id', flat=True)))
    # df_slate_lineups['build_id'] = build.id
    df_slate_lineups['slate_lineup_id'] = df_slate_lineups.index
    # df_slate_lineups = df_slate_lineups.apply(pandas.to_numeric, downcast='unsigned')
    print(f'  Initial dataframe took {time.time() - start}s')
    # print(df_slate_lineups)
    # print(f'{player_outcomes.get(str(df_slate_lineups.loc[2009202, 0]))[0]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 1]))[0]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 2]))[0]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 3]))[0]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 4]))[0]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 5]))[0]}')
    # print(f'{player_outcomes.get(str(df_slate_lineups.loc[2009202, 0]))[1]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 1]))[1]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 2]))[1]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 3]))[1]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 4]))[1]} + {player_outcomes.get(str(df_slate_lineups.loc[2009202, 5]))[1]}')
    start = time.time()
    # p1 = df_slate_lineups.merge(player_outcomes, how='left', left_on=0, right_on='slate_player_id').merge(player_outcomes, how='left', left_on=1, right_on='slate_player_id', suffixes=('_0', '_1')).merge(player_outcomes, how='left', left_on=2, right_on='slate_player_id', suffixes=('_1', '_2')).merge(player_outcomes, how='left', left_on=3, right_on='slate_player_id', suffixes=('_2', '_3')).merge(player_outcomes, how='left', left_on=4, right_on='slate_player_id', suffixes=('_3', '_4')).merge(player_outcomes, how='left', left_on=5, right_on='slate_player_id', suffixes=('_4', '_5'))
    p1 = numpy.array(df_slate_lineups.merge(player_outcomes, how='left', left_on=0, right_on='slate_player_id')['sim_scores'].to_list())
    # print(p1.query('slate_player_id in ["23136059", "23136060", "23136061", "23136077", "23136096", "23136098"]').sum(numeric_only=True))

    # print(f'  Merge took {time.time() - start}s')
    # start = time.time()
    p2 = numpy.array(df_slate_lineups.merge(player_outcomes, how='left', left_on=1, right_on='slate_player_id')['sim_scores'].to_list())
    # print(f'  Merge took {time.time() - start}s')
    # start = time.time()
    p3 = numpy.array(df_slate_lineups.merge(player_outcomes, how='left', left_on=2, right_on='slate_player_id')['sim_scores'].to_list())
    # print(f'  Merge took {time.time() - start}s')
    # start = time.time()
    p4 = numpy.array(df_slate_lineups.merge(player_outcomes, how='left', left_on=3, right_on='slate_player_id')['sim_scores'].to_list())
    # print(f'  Merge took {time.time() - start}s')
    # start = time.time()
    p5 = numpy.array(df_slate_lineups.merge(player_outcomes, how='left', left_on=4, right_on='slate_player_id')['sim_scores'].to_list())
    # print(f'  Merge took {time.time() - start}s')
    # start = time.time()
    p6 = numpy.array(df_slate_lineups.merge(player_outcomes, how='left', left_on=5, right_on='slate_player_id')['sim_scores'].to_list())
    # print(f'  Merge took {time.time() - start}s')
    # print(p1)
    # print(p1.info(verbose=True, memory_usage='deep'))
    # print(p2)
    # print(p3)
    # print(p4)
    # print(p5)
    # print(p6)
    # start = time.time()
    slate_lineup_scores = p1+p2+p3+p4+p5+p6
    # scores = p1['sim_scores_0'].to_numpy() + p1['sim_scores_1'].to_numpy() + p1['sim_scores_2'].to_numpy() + p1['sim_scores_3'].to_numpy() + p1['sim_scores_4'].to_numpy() + p1['sim_scores_5'].to_numpy()
    # print(scores)
    # df = pandas.DataFrame(numpy.array(p1['sim_scores'].to_list()) + numpy.array(p2['sim_scores'].to_list()) + numpy.array(p3['sim_scores'].to_list()) + numpy.array(p4['sim_scores'].to_list()) + numpy.array(p5['sim_scores'].to_list()) + numpy.array(p6['sim_scores'].to_list()), index=list(slate_lineups.values_list('id', flat=True)))
    # df.to_csv('data/slate_lineups.csv')
    # print(df)
    # print(player_outcomes.query('slate_player_id in ["23136059", "23136060", "23136061", "23136077", "23136096", "23136098"]').sum(numeric_only=True))
    # print(df_slate_lineups.apply(lambda x: player_outcomes.query(f'slate_player_id in ["{str(x[0])}", "{str(x[1])}", "{str(x[2])}", "{str(x[3])}", "{str(x[4])}", "{str(x[5])}"]').sum(numeric_only=True), axis=1))
    # df_slate_lineups = df_slate_lineups.apply(lambda x: player_outcomes.loc[str(x[0])] + player_outcomes.loc[str(x[1])] + player_outcomes.loc[str(x[2])] + player_outcomes.loc[str(x[3])] + player_outcomes.loc[str(x[4])] + player_outcomes.loc[str(x[5])], axis=1, result_type='expand')
    # df_slate_lineups = df_slate_lineups.apply(pandas.to_numeric, downcast='float')
    # print(df_slate_lineups.loc[2009202])
    # print(df_slate_lineups)
    print(f'  Sim scores took {time.time() - start}s')

    start = time.time()
    field_lineups = build.field_lineups.all().order_by('id')
    print(f'Getting field lineups took {time.time() - start}s.')
    start = time.time()
    df_field_lineups = pandas.DataFrame(field_lineups.values_list('slate_lineup__player_1', 'slate_lineup__player_2', 'slate_lineup__player_3', 'slate_lineup__player_4', 'slate_lineup__player_5', 'slate_lineup__player_6'), index=list(field_lineups.values_list('id', flat=True)))
    # df_field_lineups = df_field_lineups.apply(pandas.to_numeric, downcast='unsigned')
    print(f'  Initial dataframe took {time.time() - start}s')
    start = time.time()
    p1 = numpy.array(df_field_lineups.merge(player_outcomes, how='left', left_on=0, right_on='slate_player_id')['sim_scores'].to_list())
    p2 = numpy.array(df_field_lineups.merge(player_outcomes, how='left', left_on=1, right_on='slate_player_id')['sim_scores'].to_list())
    p3 = numpy.array(df_field_lineups.merge(player_outcomes, how='left', left_on=2, right_on='slate_player_id')['sim_scores'].to_list())
    p4 = numpy.array(df_field_lineups.merge(player_outcomes, how='left', left_on=3, right_on='slate_player_id')['sim_scores'].to_list())
    p5 = numpy.array(df_field_lineups.merge(player_outcomes, how='left', left_on=4, right_on='slate_player_id')['sim_scores'].to_list())
    p6 = numpy.array(df_field_lineups.merge(player_outcomes, how='left', left_on=5, right_on='slate_player_id')['sim_scores'].to_list())
    field_lineup_scores = p1+p2+p3+p4+p5+p6


    # df_field_lineups = df_field_lineups.apply(lambda x: player_outcomes.get(str(x[0])) + player_outcomes.get(str(x[1])) + player_outcomes.get(str(x[2])) + player_outcomes.get(str(x[3])) + player_outcomes.get(str(x[4])) + player_outcomes.get(str(x[5])), axis=1, result_type='expand')
    # df_field_lineups = df_field_lineups.apply(pandas.to_numeric, downcast='float')
    print(f'  Sim scores took {time.time() - start}s')

    start = time.time()
    matchups  = list(itertools.product(slate_lineups.values_list('id', flat=True), field_lineups.values_list('id', flat=True)))
    matchup_scores  = list(itertools.product(slate_lineup_scores, field_lineup_scores))
    # df_matchup_scores = pandas.DataFrame(matchup_scores, columns=['slate_lineup_scores', 'field_lineup_scores'])
    d1 = [score[0] for score in matchup_scores]
    d2 = [score[1] for score in matchup_scores]
    d = numpy.array(d1) - numpy.array(d2)
    win_rates = [numpy.count_nonzero(s > 0.0) / build.sim.iterations for s in d]
    print(win_rates[:100])
    # print(df_matchup_scores)
    # df_matchups = pandas.DataFrame(matchups, columns=['slate_lineup_id', 'field_lineup_id'])
    # df_matchups['win_rate'] = df_matchups.apply(lambda x: numpy.count_nonzero((numpy.array(df_slate_lineups.loc[x['slate_lineup_id']]) - numpy.array(df_field_lineups.loc[x['field_lineup_id']])) > 0.0) / build.sim.iterations, axis=1)
    # df_matchups = df_matchups[(df_matchups.win_rate >= 0.58)]
    # df_matchups['build_id'] = build.id
    # df_matchups = df_matchups.apply(pandas.to_numeric, downcast='float')
    print(f'Matchups took {time.time() - start}s. There are {len(matchups)} matchups.')

