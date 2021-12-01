import math
import numpy as np
import pandas as pd
import scipy
import traceback

from django.db.models import F

from nfl import models


def run():
    qbs = find_qbs()
    matrix = []

    for index, qb in enumerate(qbs):
        rbs = find_players(qb, 'RB', 2)
        if rbs.count() < 2:
            continue
        wrs = find_players(qb, 'WR', 3)
        if wrs.count() < 3:
            continue
        tes = find_players(qb, 'TE', 1)
        if tes.count() < 1:
            continue
        dsts = find_players(qb, 'DST', 1)
        if dsts.count() < 1:
            continue

        o_qbs = find_qbs(qb)
        if o_qbs.count() < 1:
            continue
        o_rbs = find_players(qb, 'RB', 2, find_opponent=True)
        if o_rbs.count() < 2:
            continue
        o_wrs = find_players(qb, 'WR', 3, find_opponent=True)
        if o_wrs.count() < 3:
            continue
        o_tes = find_players(qb, 'TE', 1, find_opponent=True)
        if o_tes.count() < 1:
            continue
        o_dsts = find_players(qb, 'DST', 1, find_opponent=True)
        if o_dsts.count() < 1:
            continue

        row = [
            qb.fantasy_points,
            rbs[0].fantasy_points,
            rbs[1].fantasy_points,
            wrs[0].fantasy_points,
            wrs[1].fantasy_points,
            wrs[2].fantasy_points,
            tes[0].fantasy_points,
            dsts[0].fantasy_points,
            o_qbs[0].fantasy_points,
            o_rbs[0].fantasy_points,
            o_rbs[1].fantasy_points,
            o_wrs[0].fantasy_points,
            o_wrs[1].fantasy_points,
            o_wrs[2].fantasy_points,
            o_tes[0].fantasy_points,
            o_dsts[0].fantasy_points,
        ]

        matrix.append(row)

    v = pd.DataFrame(matrix, dtype=float, columns=[
        'qb',
        'rb1',
        'rb2',
        'wr1',
        'wr2',
        'wr3',
        'te',
        'dst',
        'opp qb',
        'opp rb1',
        'opp rb2',
        'opp wr1',
        'opp wr2',
        'opp wr3',
        'opp te',
        'opp dst',
    ])

    r = v.corr(method='pearson')
    print(r)
    r.to_csv(f'data/dk_r.csv')


def find_qbs(qb=None):
    '''
    Query DB for relevant QBs.

    If qb parameter is used, find opposing qb
    '''
    if qb is None:
        qbs = models.SlatePlayer.objects.filter(
            slate__site='draftkings',
            site_pos='QB',
            projection__projection__gt=9.9,
            fantasy_points__gt=4.9,
            slate_game__isnull=False,
            slate__is_main_slate=True
        ).select_related('projection').annotate(proj=F('projection__projection'))
    else:
        qbs = models.SlatePlayer.objects.filter(
            slate=qb.slate,
            site_pos='QB',
            projection__projection__gt=9.9,
            fantasy_points__gt=4.9,
            team=qb.get_opponent()
        ).select_related(
            'projection'
        ).annotate(
            proj=F('projection__projection')
        )
    
    return qbs


def find_players(qb, position, depth, find_opponent=False):
    team = qb.get_opponent() if find_opponent else qb.team
    players = models.SlatePlayer.objects.filter(
        slate=qb.slate,
        site_pos=position,
        team=team,
        projection__isnull=False
    ).select_related(
        'projection'
    ).annotate(
        proj=F('projection__projection')
    ).order_by('-proj')

    if players.count() < depth:
        return players
    return players[:depth]
