import itertools
import time

import numpy
import pandas

from django.db.models import Q

from nascar import models, filters

def run():
    build = models.SlateBuild.objects.get(id=1)

    start = time.time()
    player_outcomes = pandas.DataFrame.from_records(build.projections.filter(in_play=True).values('slate_player_id', 'sim_scores'))
    player_outcomes = player_outcomes.set_index('slate_player_id')
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
    slate_lineups = filters.SlateLineupFilter(models.BUILD_TYPE_FILTERS.get(build.build_type), possible_lineups).qs
    print(f'Filtered slate lineups took {time.time() - start}s')
    
    start = time.time()
    df_build_lineups = pandas.DataFrame.from_records(slate_lineups.values('id', 'player_1', 'player_2', 'player_3', 'player_4', 'player_5', 'player_6'))
    print(f'  Initial dataframe took {time.time() - start}s')
    df_build_lineups['slate_lineup_id'] = df_build_lineups['id']
    df_build_lineups['build_id'] = build.id
    df_build_lineups = df_build_lineups.set_index('id')
    start = time.time()
    df_build_lineups['sim_scores'] = df_build_lineups.apply(lambda x: numpy.array(player_outcomes.loc[x['player_1'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_2'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_3'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_4'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_5'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_6'], 'sim_scores']), axis=1)
    print(f'  Sim scores lineups took {time.time() - start}s')

    start = time.time()
    field_lineups = build.field_lineups.all()
    print(f'Getting field lineups took {time.time() - start}s.')
    start = time.time()
    df_field_lineups = pandas.DataFrame.from_records(field_lineups.values('id', 'player_1__slate_player_id', 'player_2__slate_player_id', 'player_3__slate_player_id', 'player_4__slate_player_id', 'player_5__slate_player_id', 'player_6__slate_player_id'))
    df_field_lineups['player_1'] = df_field_lineups['player_1__slate_player_id']
    df_field_lineups['player_2'] = df_field_lineups['player_2__slate_player_id']
    df_field_lineups['player_3'] = df_field_lineups['player_3__slate_player_id']
    df_field_lineups['player_4'] = df_field_lineups['player_4__slate_player_id']
    df_field_lineups['player_5'] = df_field_lineups['player_5__slate_player_id']
    df_field_lineups['player_6'] = df_field_lineups['player_6__slate_player_id']
    df_field_lineups = df_field_lineups.set_index('id')
    df_field_lineups = df_field_lineups.drop([
        'player_1__slate_player_id',
        'player_2__slate_player_id',
        'player_3__slate_player_id',
        'player_4__slate_player_id',
        'player_5__slate_player_id',
        'player_6__slate_player_id',
    ], axis=1)
    print(f'  Initial dataframe took {time.time() - start}s')
    start = time.time()
    df_field_lineups['sim_scores'] = df_field_lineups.apply(lambda x: numpy.array(player_outcomes.loc[x['player_1'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_2'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_3'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_4'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_5'], 'sim_scores']) + numpy.array(player_outcomes.loc[x['player_6'], 'sim_scores']), axis=1)
    print(f'  Sim scores lineups took {time.time() - start}s')

    start = time.time()
    matchups  = list(itertools.product(slate_lineups.values_list('id', flat=True), field_lineups.values_list('id', flat=True)))
    df_matchups = pandas.DataFrame(matchups, columns=['build_lineup', 'field_lineup'])
    df_matchups['wins'] = df_matchups.apply(lambda x: numpy.count_nonzero((numpy.array(df_build_lineups.loc[x['build_lineup'], 'sim_scores']) - numpy.array(df_field_lineups.loc[x['field_lineup'], 'sim_scores'])) > 0.0), axis=1)
    print(df_matchups)
    df_matchups = df_matchups.drop(['field_lineup'], axis=1)
    df_win_rate = df_matchups.groupby('build_lineup').sum() / (build.sim.iterations * field_lineups.count())
    print(df_win_rate)
    print(f'Matchups took {time.time() - start}s. There are {len(matchups)} matchups.')
