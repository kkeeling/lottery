import itertools
import numpy as np
import pandas as pd
import random
import time

from django.db.models.aggregates import Count, Sum, Avg
from django.db.models import F, Q
from nfl import models

OWNERSHIP_THRESHOLD = 0.01

FLEX_OWNERSHIP_MULTIPLIER = {
    'RB': 1.2,
    'WR': 1.0,
    'TE': 0.25
}

STACK_TYPES = [
    {
        'name': '5-man (Opp 1)',
        'num_players': 4,
        'opposing_players': 1,
        'rate': .03
    },
    {
        'name': '5-man (Opp 2)',
        'num_players': 4,
        'opposing_players': 2,
        'rate': .03
    },
    {
        'name': '5-man (Opp 3)',
        'num_players': 4,
        'opposing_players': 3,
        'rate': .01
    },
    {
        'name': '4-man (Opp 1)',
        'num_players': 3,
        'opposing_players': 1,
        'rate': .345
    },
    {
        'name': '4-man (Opp 0)',
        'num_players': 3,
        'opposing_players': 0,
        'rate': .05
    },
    {
        'name': '3-man (Opp 1)',
        'num_players': 2,
        'opposing_players': 1,
        'rate': .25
    },
    {
        'name': '3-man (Opp 0)',
        'num_players': 2,
        'opposing_players': 0,
        'rate': .10
    },
    {
        'name': '2-man (Opp 0)',
        'num_players': 1,
        'opposing_players': 0,
        'rate': .20
    },
    {
        'name': 'No Stack',
        'num_players': 0,
        'opposing_players': 0,
        'rate': .03
    }
]

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
    salary_thresholds = slate.salary_thresholds

    players = slate.players.filter(
        player_id__in=l
    )
    
    num_qbs = players.aggregate(num_qbs=Count('site_pos', filter=Q(site_pos='QB'))).get('num_qbs')
    if num_qbs > 1:
        return False
    
    num_wrs = players.aggregate(num_wrs=Count('site_pos', filter=Q(site_pos='WR'))).get('num_wrs')
    if num_wrs > 4:
        return False
    
    num_rbs = players.aggregate(num_rbs=Count('site_pos', filter=Q(site_pos='RB'))).get('num_rbs')
    if num_rbs > 3:
        return False
    
    num_tes = players.aggregate(num_tes=Count('site_pos', filter=Q(site_pos='TE'))).get('num_tes')
    if num_tes > 2:
        return False

    total_salary = slate.get_projections().filter(
        slate_player__player_id__in=l
    ).aggregate(total_salary=Sum('slate_player__salary')).get('total_salary')
    if total_salary < salary_thresholds[0] or total_salary > salary_thresholds[1]:
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

    # prepare stack types
    start = time.time()
    stack_types = []
    for st in STACK_TYPES:
        count = int(st.get('rate')*1000)
        for _ in range (0, count):
            stack_types.append(st)
    print(f'Preparing stack types took {time.time() - start}s')

    num_entries = 1

    slate = models.Slate.objects.get(id=128)
    dst_label = slate.dst_label
    
    start = time.time()
    slate_players = slate.players.filter(projection__ownership_projection__gt=OWNERSHIP_THRESHOLD).order_by('-salary')
    salaries = {}
    for p in slate_players:
        salaries[p.player_id] = p.salary
    print(f'Finding players and salaries took {time.time() - start}s. There are {slate_players.count()} players in the player pool.')

    start = time.time()
    qbs = slate.get_projections().filter(
        slate_player__site_pos='QB'
    ).order_by('-projection')
    rbs = slate.get_projections().filter(
        slate_player__site_pos='RB'
    ).order_by('-projection')
    wrs = slate.get_projections().filter(
        slate_player__site_pos='WR'
    ).order_by('-projection')
    tes = slate.get_projections().filter(
        slate_player__site_pos='TE'
    ).order_by('-projection')
    flexes = slate.get_projections().filter(
        slate_player__site_pos__in=['RB', 'WR', 'TE']
    ).order_by('-projection')
    dsts = slate.get_projections().filter(
        slate_player__site_pos=dst_label
    ).order_by('-projection')
    print(f'Finding player projections took {time.time() - start}s')

    salary_thresholds = slate.salary_thresholds

    start = time.time()
    qb_list = []
    total_qb_ownership = float(qbs.aggregate(total_own=Sum('ownership_projection')).get('total_own'))
    for qb in qbs:
        this_qb_count = round((float(qb.ownership_projection) / total_qb_ownership * 100))
        for _ in range (0, this_qb_count):
            qb_list.append(qb)
    print(f'QB list took {time.time() - start}s. There are {len(qb_list)} qbs.')

    start = time.time()
    rb_list = []
    total_rb_ownership = float(rbs.aggregate(total_own=Sum('ownership_projection')).get('total_own'))
    for rb in rbs:
        this_rb_count = round((float(rb.ownership_projection) / total_rb_ownership * 100))
        for _ in range (0, this_rb_count):
            rb_list.append(rb)
    print(f'RB list took {time.time() - start}s. There are {len(rb_list)} rbs.')

    start = time.time()
    wr_list = []
    total_wr_ownership = float(wrs.aggregate(total_own=Sum('ownership_projection')).get('total_own'))
    for wr in wrs:
        this_wr_count = round((float(wr.ownership_projection) / total_wr_ownership * 100))
        for _ in range (0, this_wr_count):
            wr_list.append(wr)
    print(f'WR list took {time.time() - start}s. There are {len(wr_list)} wrs.')

    start = time.time()
    te_list = []
    total_te_ownership = float(tes.aggregate(total_own=Sum('ownership_projection')).get('total_own'))
    for te in tes:
        this_te_count = round((float(te.ownership_projection) / total_te_ownership * 100))
        for _ in range (0, this_te_count):
            te_list.append(te)
    print(f'TE list took {time.time() - start}s. There are {len(te_list)} tes.')

    start = time.time()
    flex_list = []
    total_flex_ownership = float(flexes.aggregate(total_own=Sum('ownership_projection')).get('total_own'))
    for flex in flexes:
        this_flex_count = round((float(flex.ownership_projection) / total_flex_ownership * 1000) * FLEX_OWNERSHIP_MULTIPLIER.get(flex.slate_player.site_pos))
        for _ in range (0, this_flex_count):
            flex_list.append(flex)
    print(f'FLEX list took {time.time() - start}s. There are {len(flex_list)} flexes.')

    start = time.time()
    dst_list = []
    total_dst_ownership = float(dsts.aggregate(total_own=Sum('ownership_projection')).get('total_own'))
    for dst in dsts:
        this_dst_count = round((float(dst.ownership_projection) / total_dst_ownership * 100))
        for _ in range (0, this_dst_count):
            dst_list.append(dst)
    print(f'DST list took {time.time() - start}s. There are {len(dst_list)} dsts.')

    for i in range(0, num_entries):
        start = time.time()

        # Pick QB
        qb = qb_list[random.randrange(0, len(qb_list))]
        print(f'QB = {qb}')
        
        # Pick Stack Type
        st = stack_types[random.randrange(0, len(stack_types))]
        print(f'Stack Type = {st.get("name")}')

        final_tsc = []  # final team stack combos
        final_osc = []  # final opossing stack combos

        if st.get('num_players') > 0:
            # Set up stack combos
            team_stack_partners = slate.get_projections().filter(
                slate_player__site_pos__in=['RB', 'WR', 'TE'],
                slate_player__team=qb.team,
                ownership_projection__gt=OWNERSHIP_THRESHOLD
            ).order_by('-projection')
                
            if st.get('num_players') - st.get('opposing_players') > 1:
                team_stack_combos = list(itertools.combinations(team_stack_partners.values_list('slate_player__player_id', flat=True), st.get('num_players') - st.get('opposing_players')))
                team_stack_ownership = []

                # adjust combo counts for ownership
                for combo in team_stack_combos:
                    combo_ownership = list(slate.players.filter(player_id__in=combo).values_list('projection__ownership_projection', flat=True))
                    team_stack_ownership.append(float(np.prod(combo_ownership)))
                total_combo_ownership = sum(team_stack_ownership)
                team_stack_ownership = list(map(lambda x: x/total_combo_ownership, team_stack_ownership))

                for i, combo in enumerate(team_stack_combos):
                    c = int(team_stack_ownership[i] * 100)
                    p = slate_players.filter(player_id__in=combo, site_pos='RB')  # RB stacks are low owned and no 2 RB combos
                    if p.count() > 0:
                        if p.count() == 2:
                            c = 0
                        else:
                            c = 5
                    p = slate_players.filter(player_id__in=combo, site_pos='TE')  # No 2 TE combos
                    if p.count() == 2:
                        c = 0
                    
                    for _ in range (0, c):
                        final_tsc.append(combo)
            else:
                team_stack_combos = list(team_stack_partners.values_list('slate_player__player_id', flat=True))

                for i, player in enumerate(team_stack_combos):
                    p = slate.players.get(player_id=player)
                    c = int(p.projection.ownership_projection * 100)

                    if p.site_pos == 'RB':  # QB/RB stacks are low owned
                        c = 5
                    
                    for _ in range (0, c):
                        final_tsc.append((p.player_id, ))

            # print(f'Stack Partners = {team_stack_partners}')
            print(f'There are {len(team_stack_combos)} possible team stack combos.')

            if st.get('opposing_players') > 0:
                opp_team_stack_partners = slate.get_projections().filter(
                    slate_player__site_pos__in=['RB', 'WR', 'TE'],
                    slate_player__team=qb.get_opponent(),
                    ownership_projection__gt=OWNERSHIP_THRESHOLD
                ).order_by('-projection')
                
                if st.get('opposing_players') > 1:
                    opp_team_stack_combos = list(itertools.combinations(opp_team_stack_partners.values_list('slate_player__player_id', flat=True), st.get('opposing_players')))
                    opp_stack_ownership = []

                    # adjust combo counts for ownership
                    for combo in opp_team_stack_combos:
                        combo_ownership = list(slate.players.filter(player_id__in=combo).values_list('projection__ownership_projection', flat=True))
                        opp_stack_ownership.append(float(np.prod(combo_ownership)))
                    total_combo_ownership = sum(opp_stack_ownership)
                    opp_stack_ownership = list(map(lambda x: x/total_combo_ownership, opp_stack_ownership))

                    for i, combo in enumerate(opp_team_stack_combos):
                        c = int(opp_stack_ownership[i] * 100)
                        p = slate_players.filter(player_id__in=combo, site_pos='RB')  # RB stacks are low owned and no 2 RB combos
                        if p.count() > 0:
                            if p.count() == 2:
                                c = 0
                            else:
                                c = 10
                        p = slate_players.filter(player_id__in=combo, site_pos='TE')  # No 2 TE combos
                        if p.count() == 2:
                            c = 0
                        
                        for _ in range (0, c):
                            final_osc.append(combo)
                else:
                    opp_team_stack_combos = list(opp_team_stack_partners.values_list('slate_player__player_id', flat=True))

                    for i, player in enumerate(opp_team_stack_combos):
                        p = slate.players.get(player_id=player)
                        c = int(p.projection.ownership_projection * 100)

                        if p.site_pos == 'RB':  # QB/Opp RB stacks are low owned
                            c = round(c * 0.05)
                        
                        for _ in range (0, c):
                            final_osc.append((p.player_id, ))

                # print(f'Opposing Stack Partners = {opp_team_stack_partners}')
                print(f'There are {len(opp_team_stack_combos)} possible opposing stack combos.')
        else:
            print('TODO: Implement no-stack lineup')

        lineup = [qb.slate_player.player_id]
        
        # pick stack combos
        if len(final_tsc) > 0:
            combo = final_tsc[random.randrange(0, len(final_tsc))]
            lineup += [p for p in combo]
        if len(final_osc) > 0:
            combo = final_osc[random.randrange(0, len(final_osc))]
            lineup += [p for p in combo]

        # determine remaining positions
        positions = slate_players.filter(player_id__in=lineup).values_list('site_pos', flat=True)
        num_rbs = sum(map(lambda x : x == 'RB', positions))
        num_wrs = sum(map(lambda x : x == 'WR', positions))
        num_tes = sum(map(lambda x : x == 'TE', positions))

        print(f'num_rbs = {num_rbs}; num_wrs = {num_wrs}; num_tes = {num_tes}')
        
        # remove existing players from lists
        remaining_rbs = filter(lambda rb: rb.player_id not in lineup, rb_list)
        remaining_wrs = filter(lambda wr: wr.player_id not in lineup, wr_list)
        remaining_tes = filter(lambda te: te.player_id not in lineup, te_list)
        remaining_flexes = filter(lambda flex: flex.player_id not in lineup, flex_list)

        # add remaining players
        # if num_rbs < 2:


        print(f'Lineup took {time.time() - start}s.')
    # lineups = []

    # start = time.time()
    # rb_combos = list(itertools.combinations(rbs, 2))
    # print(f'RB combos took {time.time() - start}s. There are {len(rb_combos)} combinations.')

    # start = time.time()
    # wr_combos = list(itertools.combinations(wrs, 3))
    # print(f'WR combos took {time.time() - start}s. There are {len(wr_combos)} combinations.')
    
    # start = time.time()
    # projections = slate.get_projections().filter(in_play=True).order_by('-slate_player__salary')
    # player_outcomes = {}
    # for p in projections:
    #     player_outcomes[p.slate_player.player_id] = np.array(p.sim_scores)
    # print(f'Getting player outcomes took {time.time() - start}s')

    # for qb in qbs:
    #     print(f'qb = {qb}')

    #     # start = time.time()
    #     # lineup_combos = list(itertools.product(rb_combos, wr_combos, tes, dsts))
    #     # lineup_combos = list(itertools.combinations(rbs+rbs+wrs+wrs+wrs, 5))
    #     # print(f'  Lineup combos took {time.time() - start}s. There are {len(lineup_combos)} combos.')

    #     start = time.time()
    #     for _ in range(0, 100):
    #         l, total_salary = get_random_lineup(slate, qb, rb_combos, wr_combos, tes, list(rbs) + list(wrs), dsts)

    #         '''
    #         TODO: Add additional constraints
    #             - No duplicate lineups
    #         '''
    #         while (total_salary < salary_thresholds[0] or total_salary > salary_thresholds[1] or not is_lineup_valid(slate, l)):
    #             l, total_salary = get_random_lineup(slate, qb, rb_combos, wr_combos, tes, list(rbs) + list(wrs), dsts)

    #         l.append(total_salary)  ## append total salary to end of lineup array so we can make a dataframe
    #         lineups.append(l)
    #     print(f'Lineup selection took {time.time() - start}s')

    #     start = time.time()
    #     df_lineups = pd.DataFrame(lineups, columns=[
    #         'qb_id',
    #         'rb1_id',
    #         'rb2_id',
    #         'wr1_id',
    #         'wr2_id',
    #         'wr3_id',
    #         'te_id',
    #         'flex_id',
    #         'dst_id',
    #         'total_salary',
    #     ])
    #     print(f'Dataframe took {time.time() - start}s')
    #     # print(df_lineups)

    #     start = time.time()
    #     df_lineups['sim_scores'] = df_lineups.apply(lambda x: player_outcomes.get(str(x[0])) + player_outcomes.get(str(x[1])) + player_outcomes.get(str(x[2])) + player_outcomes.get(str(x[3])) + player_outcomes.get(str(x[4])) + player_outcomes.get(str(x[5])) + player_outcomes.get(str(x[6])) + player_outcomes.get(str(x[7])) + player_outcomes.get(str(x[8])), axis=1)
    #     print(f'Sim scores took {time.time() - start}s')
    #     print(df_lineups)

    #     # race lineups to find the best
    #     # start = time.time()
    #     # df_matchups = df_lineups_sim_scores.rank(method="min", ascending=False).median(axis=1)
    #     # print(f'Matchups took {time.time() - start}s.')
    #     # print(df_matchups)

    #     print(f'Process took {time.time() - top_start}s')
    #     break


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