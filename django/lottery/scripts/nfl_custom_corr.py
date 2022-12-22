import datetime
import math
from numpy import linalg as la
import numpy as np
import pandas as pd
import statsmodels
import scipy
import traceback

from django.db import connection
from django.db.models import F

from nfl import models, utils


def find_symmetric(matrix):
    columns = matrix.columns
    keys = matrix.keys()

    for x in keys:
        for y in columns:
            if matrix[y][x] != matrix[x][y]:
                print(f'x = {x}; y = {y}, matrix[y][x] = {matrix[y][x]}, matrix[x][y] = {matrix[x][y]}')      


def find_knn_corr(p1, p2, site):
    with connection.cursor() as cursor:
        sql = '''
            SELECT  p1.name,
                    p1_proj.projection       as p1_proj,
                    p1.fantasy_points        as p1_actual,
                    p2.name,
                    p2_proj.projection       as p2_proj,
                    p2.fantasy_points        as p2_actual
            FROM nfl_slateplayer p1
            INNER JOIN nfl_slateplayer p2 on p1.team = p2.team AND p1.slate_id = p2.slate_id
            LEFT JOIN nfl_slate slate ON slate.id = p1.slate_id
            LEFT JOIN nfl_slateplayerprojection p1_proj ON p1_proj.slate_player_id = p1.id
            LEFT JOIN nfl_slateplayerprojection p2_proj ON p2_proj.slate_player_id = p2.id
            WHERE slate.is_main_slate = true
                AND slate.site = %s
                AND p1.site_pos = %s
                AND p2.site_pos = %s
                AND slate.datetime < '2022-02-28'
                AND p1.fantasy_points >= 1.0
                AND p2.fantasy_points >= 1.0
        '''

        cursor.execute(sql, [site, p1.slate_player.site_pos, p2.slate_player.site_pos])
        rows = cursor.fetchall()

    df = pd.DataFrame.from_records(
        rows,
        columns=['p1_name', 'p1_proj', 'p1_actual', 'p2_name', 'p2_proj', 'p2_actual'],
        coerce_float=True
    )

    X = df.drop(['p1_name', 'p1_actual', 'p2_name', 'p2_actual'], axis=1)

    new_dp = np.array([
        float(p1.projection),
        float(p2.projection),
    ])
    distances = np.linalg.norm(X - new_dp, axis=1)
    k = 50
    nearest_neighbor_ids = distances.argsort()[:k]

    comps = df.iloc[nearest_neighbor_ids]
    # print(comps)
    return round(comps['p1_actual'].corr(comps['p2_actual']), 4)


def find_opp_knn_corr(p1, p2, site):
    with connection.cursor() as cursor:
        sql = '''
            SELECT  p1.name,
                    p1_proj.projection       as p1_proj,
                    p1.fantasy_points        as p1_actual,
                    p2.name,
                    p2_proj.projection       as p2_proj,
                    p2.fantasy_points        as p2_actual
            FROM nfl_slateplayer p1
            INNER JOIN nfl_slateplayer p2 on p1.team <> p2.team AND p1.slate_game_id = p2.slate_game_id
            LEFT JOIN nfl_slate slate ON slate.id = p1.slate_id
            LEFT JOIN nfl_slateplayerprojection p1_proj ON p1_proj.slate_player_id = p1.id
            LEFT JOIN nfl_slateplayerprojection p2_proj ON p2_proj.slate_player_id = p2.id
            WHERE slate.is_main_slate = true
                AND slate.site = %s
                AND p1.site_pos = %s
                AND p2.site_pos = %s
                AND slate.datetime < '2022-02-28'
                AND p1.fantasy_points >= 1.0
                AND p2.fantasy_points >= 1.0
        '''

        cursor.execute(sql, [site, p1.slate_player.site_pos, p2.slate_player.site_pos])
        rows = cursor.fetchall()

    df = pd.DataFrame.from_records(
        rows,
        columns=['p1_name', 'p1_proj', 'p1_actual', 'p2_name', 'p2_proj', 'p2_actual'],
        coerce_float=True
    )

    X = df.drop(['p1_name', 'p1_actual', 'p2_name', 'p2_actual'], axis=1)

    new_dp = np.array([
        float(p1.projection),
        float(p2.projection),
    ])
    distances = np.linalg.norm(X - new_dp, axis=1)
    k = 50
    nearest_neighbor_ids = distances.argsort()[:k]

    comps = df.iloc[nearest_neighbor_ids]
    # print(comps)
    return round(comps['p1_actual'].corr(comps['p2_actual']), 4)


def nearestPD(A):
    """Find the nearest positive-definite matrix to input

    A Python/Numpy port of John D'Errico's `nearestSPD` MATLAB code [1], which
    credits [2].

    [1] https://www.mathworks.com/matlabcentral/fileexchange/42885-nearestspd

    [2] N.J. Higham, "Computing a nearest symmetric positive semidefinite
    matrix" (1988): https://doi.org/10.1016/0024-3795(88)90223-6
    """

    B = (A + A.T) / 2
    _, s, V = la.svd(B)

    H = np.dot(V.T, np.dot(np.diag(s), V))

    A2 = (B + H) / 2

    A3 = (A2 + A2.T) / 2

    if isPD(A3):
        return A3

    spacing = np.spacing(la.norm(A))
    # The above is different from [1]. It appears that MATLAB's `chol` Cholesky
    # decomposition will accept matrixes with exactly 0-eigenvalue, whereas
    # Numpy's will not. So where [1] uses `eps(mineig)` (where `eps` is Matlab
    # for `np.spacing`), we use the above definition. CAVEAT: our `spacing`
    # will be much larger than [1]'s `eps(mineig)`, since `mineig` is usually on
    # the order of 1e-16, and `eps(1e-16)` is on the order of 1e-34, whereas
    # `spacing` will, for Gaussian random matrixes of small dimension, be on
    # othe order of 1e-16. In practice, both ways converge, as the unit test
    # below suggests.
    I = np.eye(A.shape[0])
    k = 1
    while not isPD(A3):
        mineig = np.min(np.real(la.eigvals(A3)))
        A3 += I * (-mineig * k**2 + spacing)
        k += 1

    return A3


def isPD(B):
    """Returns true when input is positive-definite, via Cholesky"""
    try:
        _ = la.cholesky(B)
        return True
    except la.LinAlgError:
        return False

def get_near_psd(A):
    C = (A + A.T)/2
    eigval, eigvec = np.linalg.eig(C)
    eigval[eigval < 0] = 0

    return eigvec.dot(np.diag(eigval)).dot(eigvec.T)

def run():
    slate = models.Slate.objects.get(id=819)
    
    for game in slate.games.all():
        print(game)

        if game.slate.site == 'fanduel':
            dst_label = 'D' 
        elif game.slate.site == 'yahoo':
            dst_label = 'DEF' 
        else:
            dst_label = 'DST' 

        # initialize variables
        home_qb = None
        home_rb1 = None
        home_rb2 = None
        home_rb3 = None
        home_wr1 = None
        home_wr2 = None
        home_wr3 = None
        home_wr4 = None
        home_wr5 = None
        home_te1 = None
        home_te2 = None
        home_k = None
        home_dst = None
        away_qb = None
        away_rb1 = None
        away_rb2 = None
        away_rb3 = None
        away_wr1 = None
        away_wr2 = None
        away_wr3 = None
        away_wr4 = None
        away_wr5 = None
        away_te1 = None
        away_te2 = None
        away_k = None
        away_dst = None

        # Set up game players
        home_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_home_players().values_list('id', flat=True)).exclude(slate_player__roster_position__in=['CPT', 'MVP'])
        away_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_away_players().values_list('id', flat=True)).exclude(slate_player__roster_position__in=['CPT', 'MVP'])

        home_qbs = home_players.filter(slate_player__site_pos='QB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_rbs = home_players.filter(slate_player__site_pos='RB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_wrs = home_players.filter(slate_player__site_pos='WR').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_tes = home_players.filter(slate_player__site_pos='TE').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_ks = home_players.filter(slate_player__site_pos='K').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        home_dsts = home_players.filter(slate_player__site_pos=dst_label).exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')

        home_qb = home_qbs[0]
        home_rb1 = home_rbs[0]
        if home_rbs.count() > 1:
            home_rb2 = home_rbs[1]
        if home_rbs.count() > 2:
            home_rb3 = home_rbs[2]
        home_wr1 = home_wrs[0]
        home_wr2 = home_wrs[1]
        if home_wrs.count() > 2:
            home_wr3 = home_wrs[2]
        if home_wrs.count() > 3:
            home_wr4 = home_wrs[3]
        if home_wrs.count() > 4:
            home_wr5 = home_wrs[4]
        home_te1 = home_tes[0]
        if home_tes.count() > 1:
            home_te2 = home_tes[1]
        if home_ks.count() > 0:
            home_k = home_ks[0]
        home_dst = home_dsts[0]

        away_qbs = away_players.filter(slate_player__site_pos='QB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_rbs = away_players.filter(slate_player__site_pos='RB').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_wrs = away_players.filter(slate_player__site_pos='WR').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_tes = away_players.filter(slate_player__site_pos='TE').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_ks = away_players.filter(slate_player__site_pos='K').exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')
        away_dsts = away_players.filter(slate_player__site_pos=dst_label).exclude(projection__lte=0.0).exclude(stdev__lte=0.0).order_by('-projection', '-slate_player__salary')

        away_qb = away_qbs[0]
        away_rb1 = away_rbs[0]
        if away_rbs.count() > 1:
            away_rb2 = away_rbs[1]
        if away_rbs.count() > 2:
            away_rb3 = away_rbs[2]
        away_wr1 = away_wrs[0]
        away_wr2 = away_wrs[1]
        if away_wrs.count() > 2:
            away_wr3 = away_wrs[2]
        if away_wrs.count() > 3:
            away_wr4 = away_wrs[3]
        if away_wrs.count() > 4:
            away_wr5 = away_wrs[4]
        away_te1 = away_tes[0]
        if away_tes.count() > 1:
            away_te2 = away_tes[1]
        if away_ks.count() > 0:
            away_k = away_ks[0]
        away_dst = away_dsts[0]

        # set up correlation combinations
        correlations = []

        # QB
        print('QB')
        qb_corr = []
        qb_corr.append(1.0)  # self
        qb_corr.append(find_knn_corr(home_qb, home_rb1, slate.site))
        if home_rb2:
            qb_corr.append(find_knn_corr(home_qb, home_rb2, slate.site))
        if home_rb3:
            qb_corr.append(find_knn_corr(home_qb, home_rb3, slate.site))
        qb_corr.append(find_knn_corr(home_qb, home_wr1, slate.site))
        qb_corr.append(find_knn_corr(home_qb, home_wr2, slate.site))
        if home_wr3:
            qb_corr.append(find_knn_corr(home_qb, home_wr3, slate.site))
        if home_wr4:
            qb_corr.append(find_knn_corr(home_qb, home_wr4, slate.site))
        if home_wr5:
            qb_corr.append(find_knn_corr(home_qb, home_wr5, slate.site))
        qb_corr.append(find_knn_corr(home_qb, home_te1, slate.site))
        if home_te2:
            qb_corr.append(find_knn_corr(home_qb, home_te2, slate.site))
        qb_corr.append(0.1)
        qb_corr.append(find_knn_corr(home_qb, home_dst, slate.site))
        qb_corr.append(find_opp_knn_corr(home_qb, away_qb, slate.site))
        qb_corr.append(find_opp_knn_corr(home_qb, away_rb1, slate.site))
        if away_rb2:
            qb_corr.append(find_opp_knn_corr(home_qb, away_rb2, slate.site))
        if away_rb3:
            qb_corr.append(find_opp_knn_corr(home_qb, away_rb3, slate.site))
        qb_corr.append(find_opp_knn_corr(home_qb, away_wr1, slate.site))
        qb_corr.append(find_opp_knn_corr(home_qb, away_wr2, slate.site))
        if away_wr3:
            qb_corr.append(find_opp_knn_corr(home_qb, away_wr3, slate.site))
        if away_wr4:
            qb_corr.append(find_opp_knn_corr(home_qb, away_wr4, slate.site))
        if away_wr5:
            qb_corr.append(find_opp_knn_corr(home_qb, away_wr5, slate.site))
        qb_corr.append(find_opp_knn_corr(home_qb, away_te1, slate.site))
        if away_te2:
            qb_corr.append(find_opp_knn_corr(home_qb, away_te2, slate.site))
        qb_corr.append(-0.03)
        qb_corr.append(find_opp_knn_corr(home_qb, away_dst, slate.site))
        correlations.append(qb_corr)
        
        # RB1
        print('RB1')
        rb1_corr = []
        rb1_corr.append(find_knn_corr(home_qb, home_rb1, slate.site))
        rb1_corr.append(1.0)  # self
        if home_rb2:
            rb1_corr.append(find_knn_corr(home_rb1, home_rb2, slate.site))
        if home_rb3:
            rb1_corr.append(find_knn_corr(home_rb1, home_rb3, slate.site))
        rb1_corr.append(find_knn_corr(home_rb1, home_wr1, slate.site))
        rb1_corr.append(find_knn_corr(home_rb1, home_wr2, slate.site))
        if home_wr3:
            rb1_corr.append(find_knn_corr(home_rb1, home_wr3, slate.site))
        if home_wr4:
            rb1_corr.append(find_knn_corr(home_rb1, home_wr4, slate.site))
        if home_wr5:
            rb1_corr.append(find_knn_corr(home_rb1, home_wr5, slate.site))
        rb1_corr.append(find_knn_corr(home_rb1, home_te1, slate.site))
        if home_te2:
            rb1_corr.append(find_knn_corr(home_rb1, home_te2, slate.site))
        rb1_corr.append(0.06)
        rb1_corr.append(find_knn_corr(home_rb1, home_dst, slate.site))
        rb1_corr.append(find_opp_knn_corr(home_rb1, away_qb, slate.site))
        rb1_corr.append(find_opp_knn_corr(home_rb1, away_rb1, slate.site))
        if away_rb2:
            rb1_corr.append(find_opp_knn_corr(home_rb1, away_rb2, slate.site))
        if away_rb3:
            rb1_corr.append(find_opp_knn_corr(home_rb1, away_rb3, slate.site))
        rb1_corr.append(find_opp_knn_corr(home_rb1, away_wr1, slate.site))
        rb1_corr.append(find_opp_knn_corr(home_rb1, away_wr2, slate.site))
        if away_wr3:
            rb1_corr.append(find_opp_knn_corr(home_rb1, away_wr3, slate.site))
        if away_wr4:
            rb1_corr.append(find_opp_knn_corr(home_rb1, away_wr4, slate.site))
        if away_wr5:
            rb1_corr.append(find_opp_knn_corr(home_rb1, away_wr5, slate.site))
        rb1_corr.append(find_opp_knn_corr(home_rb1, away_te1, slate.site))
        if away_te2:
            rb1_corr.append(find_opp_knn_corr(home_rb1, away_te2, slate.site))
        rb1_corr.append(-0.07)
        rb1_corr.append(find_opp_knn_corr(home_rb1, away_dst, slate.site))
        correlations.append(rb1_corr)
        
        # RB2
        print('RB2')
        if home_rb2:
            rb2_corr = []
            rb2_corr.append(find_knn_corr(home_qb, home_rb2, slate.site))
            rb2_corr.append(find_knn_corr(home_rb1, home_rb2, slate.site))
            rb2_corr.append(1.0)  # self
            if home_rb3:
                rb2_corr.append(find_knn_corr(home_rb2, home_rb3, slate.site))
            rb2_corr.append(find_knn_corr(home_rb2, home_wr1, slate.site))
            rb2_corr.append(find_knn_corr(home_rb2, home_wr2, slate.site))
            if home_wr3:
                rb2_corr.append(find_knn_corr(home_rb2, home_wr3, slate.site))
            if home_wr4:
                rb2_corr.append(find_knn_corr(home_rb2, home_wr4, slate.site))
            if home_wr5:
                rb2_corr.append(find_knn_corr(home_rb2, home_wr5, slate.site))
            rb2_corr.append(find_knn_corr(home_rb2, home_te1, slate.site))
            if home_te2:
                rb2_corr.append(find_knn_corr(home_rb2, home_te2, slate.site))
            rb2_corr.append(0.06)
            rb2_corr.append(find_knn_corr(home_rb2, home_dst, slate.site))
            rb2_corr.append(find_opp_knn_corr(home_rb2, away_qb, slate.site))
            rb2_corr.append(find_opp_knn_corr(home_rb2, away_rb1, slate.site))
            if away_rb2:
                rb2_corr.append(find_opp_knn_corr(home_rb2, away_rb2, slate.site))
            if away_rb3:
                rb2_corr.append(find_opp_knn_corr(home_rb2, away_rb3, slate.site))
            rb2_corr.append(find_opp_knn_corr(home_rb2, away_wr1, slate.site))
            rb2_corr.append(find_opp_knn_corr(home_rb2, away_wr2, slate.site))
            if away_wr3:
                rb2_corr.append(find_opp_knn_corr(home_rb2, away_wr3, slate.site))
            if away_wr4:
                rb2_corr.append(find_opp_knn_corr(home_rb2, away_wr4, slate.site))
            if away_wr5:
                rb2_corr.append(find_opp_knn_corr(home_rb2, away_wr5, slate.site))
            rb2_corr.append(find_opp_knn_corr(home_rb2, away_te1, slate.site))
            if away_te2:
                rb2_corr.append(find_opp_knn_corr(home_rb2, away_te2, slate.site))
            rb2_corr.append(-0.08)
            rb2_corr.append(find_opp_knn_corr(home_rb2, away_dst, slate.site))
            correlations.append(rb2_corr)
        
        # RB3
        print('RB3')
        if home_rb3:
            rb3_corr = []
            rb3_corr.append(find_knn_corr(home_qb, home_rb3, slate.site))
            rb3_corr.append(find_knn_corr(home_rb1, home_rb3, slate.site))
            rb3_corr.append(find_knn_corr(home_rb2, home_rb3, slate.site))
            rb3_corr.append(1.0)  # self
            rb3_corr.append(find_knn_corr(home_rb3, home_wr1, slate.site))
            rb3_corr.append(find_knn_corr(home_rb3, home_wr2, slate.site))
            if home_wr3:
                rb3_corr.append(find_knn_corr(home_rb3, home_wr3, slate.site))
            if home_wr4:
                rb3_corr.append(find_knn_corr(home_rb3, home_wr4, slate.site))
            if home_wr5:
                rb3_corr.append(find_knn_corr(home_rb3, home_wr5, slate.site))
            rb3_corr.append(find_knn_corr(home_rb3, home_te1, slate.site))
            if home_te2:
                rb3_corr.append(find_knn_corr(home_rb3, home_te2, slate.site))
            rb3_corr.append(0.06)
            rb3_corr.append(find_knn_corr(home_rb3, home_dst, slate.site))
            rb3_corr.append(find_opp_knn_corr(home_rb3, away_qb, slate.site))
            rb3_corr.append(find_opp_knn_corr(home_rb3, away_rb1, slate.site))
            if away_rb2:
                rb3_corr.append(find_opp_knn_corr(home_rb3, away_rb2, slate.site))
            if away_rb3:
                rb3_corr.append(find_opp_knn_corr(home_rb3, away_rb3, slate.site))
            rb3_corr.append(find_opp_knn_corr(home_rb3, away_wr1, slate.site))
            rb3_corr.append(find_opp_knn_corr(home_rb3, away_wr2, slate.site))
            if away_wr3:
                rb3_corr.append(find_opp_knn_corr(home_rb3, away_wr3, slate.site))
            if away_wr4:
                rb3_corr.append(find_opp_knn_corr(home_rb3, away_wr4, slate.site))
            if away_wr5:
                rb3_corr.append(find_opp_knn_corr(home_rb3, away_wr5, slate.site))
            rb3_corr.append(find_opp_knn_corr(home_rb3, away_te1, slate.site))
            if away_te2:
                rb3_corr.append(find_opp_knn_corr(home_rb3, away_te2, slate.site))
            rb3_corr.append(-0.09)
            rb3_corr.append(find_opp_knn_corr(home_rb3, away_dst, slate.site))
            correlations.append(rb3_corr)

        # WR1
        print('WR1')
        wr1_corr = []
        wr1_corr.append(find_knn_corr(home_qb, home_wr1, slate.site))
        wr1_corr.append(find_knn_corr(home_rb1, home_wr1, slate.site))
        if home_rb2:
            wr1_corr.append(find_knn_corr(home_rb2, home_wr1, slate.site))
        if home_rb3:
            wr1_corr.append(find_knn_corr(home_rb3, home_wr1, slate.site))
        wr1_corr.append(1.0)  # self
        wr1_corr.append(find_knn_corr(home_wr1, home_wr2, slate.site))
        if home_wr3:
            wr1_corr.append(find_knn_corr(home_wr1, home_wr3, slate.site))
        if home_wr4:
            wr1_corr.append(find_knn_corr(home_wr1, home_wr4, slate.site))
        if home_wr5:
            wr1_corr.append(find_knn_corr(home_wr1, home_wr5, slate.site))
        wr1_corr.append(find_knn_corr(home_wr1, home_te1, slate.site))
        if home_te2:
            wr1_corr.append(find_knn_corr(home_wr1, home_te2, slate.site))
        wr1_corr.append(0.05)
        wr1_corr.append(find_knn_corr(home_wr1, home_dst, slate.site))
        wr1_corr.append(find_opp_knn_corr(home_wr1, away_qb, slate.site))
        wr1_corr.append(find_opp_knn_corr(home_wr1, away_rb1, slate.site))
        if away_rb2:
            wr1_corr.append(find_opp_knn_corr(home_wr1, away_rb2, slate.site))
        if away_rb3:
            wr1_corr.append(find_opp_knn_corr(home_wr1, away_rb3, slate.site))
        wr1_corr.append(find_opp_knn_corr(home_wr1, away_wr1, slate.site))
        wr1_corr.append(find_opp_knn_corr(home_wr1, away_wr2, slate.site))
        if away_wr3:
            wr1_corr.append(find_opp_knn_corr(home_wr1, away_wr3, slate.site))
        if away_wr4:
            wr1_corr.append(find_opp_knn_corr(home_wr1, away_wr4, slate.site))
        if away_wr5:
            wr1_corr.append(find_opp_knn_corr(home_wr1, away_wr5, slate.site))
        wr1_corr.append(find_opp_knn_corr(home_wr1, away_te1, slate.site))
        if away_te2:
            wr1_corr.append(find_opp_knn_corr(home_wr1, away_te2, slate.site))
        wr1_corr.append(0.01)
        wr1_corr.append(find_opp_knn_corr(home_wr1, away_dst, slate.site))
        correlations.append(wr1_corr)

        # WR2
        print('WR2')
        wr2_corr = []
        wr2_corr.append(find_knn_corr(home_qb, home_wr2, slate.site))
        wr2_corr.append(find_knn_corr(home_rb1, home_wr2, slate.site))
        if home_rb2:
            wr2_corr.append(find_knn_corr(home_rb2, home_wr2, slate.site))
        if home_rb3:
            wr2_corr.append(find_knn_corr(home_rb3, home_wr2, slate.site))
        wr2_corr.append(find_knn_corr(home_wr1, home_wr2, slate.site))
        wr2_corr.append(1.0)  # self
        if home_wr3:
            wr2_corr.append(find_knn_corr(home_wr2, home_wr3, slate.site))
        if home_wr4:
            wr2_corr.append(find_knn_corr(home_wr2, home_wr4, slate.site))
        if home_wr5:
            wr2_corr.append(find_knn_corr(home_wr2, home_wr5, slate.site))
        wr2_corr.append(find_knn_corr(home_wr2, home_te1, slate.site))
        if home_te2:
            wr2_corr.append(find_knn_corr(home_wr2, home_te2, slate.site))
        wr2_corr.append(0.00)
        wr2_corr.append(find_knn_corr(home_wr2, home_dst, slate.site))
        wr2_corr.append(find_opp_knn_corr(home_wr2, away_qb, slate.site))
        wr2_corr.append(find_opp_knn_corr(home_wr2, away_rb1, slate.site))
        if away_rb2:
            wr2_corr.append(find_opp_knn_corr(home_wr2, away_rb2, slate.site))
        if away_rb3:
            wr2_corr.append(find_opp_knn_corr(home_wr2, away_rb3, slate.site))
        wr2_corr.append(find_opp_knn_corr(home_wr2, away_wr1, slate.site))
        wr2_corr.append(find_opp_knn_corr(home_wr2, away_wr2, slate.site))
        if away_wr3:
            wr2_corr.append(find_opp_knn_corr(home_wr2, away_wr3, slate.site))
        if away_wr4:
            wr2_corr.append(find_opp_knn_corr(home_wr2, away_wr4, slate.site))
        if away_wr5:
            wr2_corr.append(find_opp_knn_corr(home_wr2, away_wr5, slate.site))
        wr2_corr.append(find_opp_knn_corr(home_wr2, away_te1, slate.site))
        if away_te2:
            wr2_corr.append(find_opp_knn_corr(home_wr2, away_te2, slate.site))
        wr2_corr.append(0.07)
        wr2_corr.append(find_opp_knn_corr(home_wr2, away_dst, slate.site))
        correlations.append(wr2_corr)
        
        # WR3
        print('WR3')
        if home_wr3:
            wr3_corr = []
            wr3_corr.append(find_knn_corr(home_qb, home_wr3, slate.site))
            wr3_corr.append(find_knn_corr(home_rb1, home_wr3, slate.site))
            if home_rb2:
                wr3_corr.append(find_knn_corr(home_rb2, home_wr3, slate.site))
            if home_rb3:
                wr3_corr.append(find_knn_corr(home_rb3, home_wr3, slate.site))
            wr3_corr.append(find_knn_corr(home_wr1, home_wr3, slate.site))
            wr3_corr.append(find_knn_corr(home_wr2, home_wr3, slate.site))
            wr3_corr.append(1.0)  # self
            if home_wr4:
                wr3_corr.append(find_knn_corr(home_wr3, home_wr4, slate.site))
            if home_wr5:
                wr3_corr.append(find_knn_corr(home_wr3, home_wr5, slate.site))
            wr3_corr.append(find_knn_corr(home_wr3, home_te1, slate.site))
            if home_te2:
                wr3_corr.append(find_knn_corr(home_wr3, home_te2, slate.site))
            wr3_corr.append(0.01)
            wr3_corr.append(find_knn_corr(home_wr3, home_dst, slate.site))
            wr3_corr.append(find_opp_knn_corr(home_wr3, away_qb, slate.site))
            wr3_corr.append(find_opp_knn_corr(home_wr3, away_rb1, slate.site))
            if away_rb2:
                wr3_corr.append(find_opp_knn_corr(home_wr3, away_rb2, slate.site))
            if away_rb3:
                wr3_corr.append(find_opp_knn_corr(home_wr3, away_rb3, slate.site))
            wr3_corr.append(find_opp_knn_corr(home_wr3, away_wr1, slate.site))
            wr3_corr.append(find_opp_knn_corr(home_wr3, away_wr2, slate.site))
            if away_wr3:
                wr3_corr.append(find_opp_knn_corr(home_wr3, away_wr3, slate.site))
            if away_wr4:
                wr3_corr.append(find_opp_knn_corr(home_wr3, away_wr4, slate.site))
            if away_wr5:
                wr3_corr.append(find_opp_knn_corr(home_wr3, away_wr5, slate.site))
            wr3_corr.append(find_opp_knn_corr(home_wr3, away_te1, slate.site))
            if away_te2:
                wr3_corr.append(find_opp_knn_corr(home_wr3, away_te2, slate.site))
            wr3_corr.append(-0.01)
            wr3_corr.append(find_opp_knn_corr(home_wr3, away_dst, slate.site))
            correlations.append(wr3_corr)
        
        # WR4
        print('WR4')
        if home_wr4:
            wr4_corr = []
            wr4_corr.append(find_knn_corr(home_qb, home_wr4, slate.site))
            wr4_corr.append(find_knn_corr(home_rb1, home_wr4, slate.site))
            if home_rb2:
                wr4_corr.append(find_knn_corr(home_rb2, home_wr4, slate.site))
            if home_rb3:
                wr4_corr.append(find_knn_corr(home_rb3, home_wr4, slate.site))
            wr4_corr.append(find_knn_corr(home_wr1, home_wr4, slate.site))
            wr4_corr.append(find_knn_corr(home_wr2, home_wr4, slate.site))
            if home_wr3:
                wr4_corr.append(find_knn_corr(home_wr3, home_wr4, slate.site))
            wr4_corr.append(1.0)  # self
            if home_wr5:
                wr4_corr.append(find_knn_corr(home_wr4, home_wr5, slate.site))
            wr4_corr.append(find_knn_corr(home_wr4, home_te1, slate.site))
            if home_te2:
                wr4_corr.append(find_knn_corr(home_wr4, home_te2, slate.site))
            wr4_corr.append(0.00)
            wr4_corr.append(find_knn_corr(home_wr4, home_dst, slate.site))
            wr4_corr.append(find_opp_knn_corr(home_wr4, away_qb, slate.site))
            wr4_corr.append(find_opp_knn_corr(home_wr4, away_rb1, slate.site))
            if away_rb2:
                wr4_corr.append(find_opp_knn_corr(home_wr4, away_rb2, slate.site))
            if away_rb3:
                wr4_corr.append(find_opp_knn_corr(home_wr4, away_rb3, slate.site))
            wr4_corr.append(find_opp_knn_corr(home_wr4, away_wr1, slate.site))
            wr4_corr.append(find_opp_knn_corr(home_wr4, away_wr2, slate.site))
            if away_wr3:
                wr4_corr.append(find_opp_knn_corr(home_wr4, away_wr3, slate.site))
            if away_wr4:
                wr4_corr.append(find_opp_knn_corr(home_wr4, away_wr4, slate.site))
            if away_wr5:
                wr4_corr.append(find_opp_knn_corr(home_wr4, away_wr5, slate.site))
            wr4_corr.append(find_opp_knn_corr(home_wr4, away_te1, slate.site))
            if away_te2:
                wr4_corr.append(find_opp_knn_corr(home_wr4, away_te2, slate.site))
            wr4_corr.append(-0.01)
            wr4_corr.append(find_opp_knn_corr(home_wr4, away_dst, slate.site))
            correlations.append(wr4_corr)
        
        # WR5
        print('WR5')
        if home_wr5:
            wr5_corr = []
            wr5_corr.append(find_knn_corr(home_qb, home_wr5, slate.site))
            wr5_corr.append(find_knn_corr(home_rb1, home_wr5, slate.site))
            if home_rb2:
                wr5_corr.append(find_knn_corr(home_rb2, home_wr5, slate.site))
            if home_rb3:
                wr5_corr.append(find_knn_corr(home_rb3, home_wr5, slate.site))
            wr5_corr.append(find_knn_corr(home_wr1, home_wr5, slate.site))
            wr5_corr.append(find_knn_corr(home_wr2, home_wr5, slate.site))
            if home_wr3:
                wr5_corr.append(find_knn_corr(home_wr3, home_wr5, slate.site))
            if home_wr4:
                wr5_corr.append(find_knn_corr(home_wr4, home_wr5, slate.site))
            wr5_corr.append(1.0)  # self
            wr5_corr.append(find_knn_corr(home_wr5, home_te1, slate.site))
            if home_te2:
                wr5_corr.append(find_knn_corr(home_wr5, home_te2, slate.site))
            wr5_corr.append(0.00)
            wr5_corr.append(find_knn_corr(home_wr5, home_dst, slate.site))
            wr5_corr.append(find_opp_knn_corr(home_wr5, away_qb, slate.site))
            wr5_corr.append(find_opp_knn_corr(home_wr5, away_rb1, slate.site))
            if away_rb2:
                wr5_corr.append(find_opp_knn_corr(home_wr5, away_rb2, slate.site))
            if away_rb3:
                wr5_corr.append(find_opp_knn_corr(home_wr5, away_rb3, slate.site))
            wr5_corr.append(find_opp_knn_corr(home_wr5, away_wr1, slate.site))
            wr5_corr.append(find_opp_knn_corr(home_wr5, away_wr2, slate.site))
            if away_wr3:
                wr5_corr.append(find_opp_knn_corr(home_wr5, away_wr3, slate.site))
            if away_wr4:
                wr5_corr.append(find_opp_knn_corr(home_wr5, away_wr4, slate.site))
            if away_wr5:
                wr5_corr.append(find_opp_knn_corr(home_wr5, away_wr5, slate.site))
            wr5_corr.append(find_opp_knn_corr(home_wr5, away_te1, slate.site))
            if away_te2:
                wr5_corr.append(find_opp_knn_corr(home_wr5, away_te2, slate.site))
            wr5_corr.append(-0.01)
            wr5_corr.append(find_opp_knn_corr(home_wr5, away_dst, slate.site))
            correlations.append(wr5_corr)

        # TE1
        print('TE1')
        te1_corr = []
        te1_corr.append(find_knn_corr(home_qb, home_te1, slate.site))
        te1_corr.append(find_knn_corr(home_rb1, home_te1, slate.site))
        if home_rb2:
            te1_corr.append(find_knn_corr(home_rb2, home_te1, slate.site))
        if home_rb3:
            te1_corr.append(find_knn_corr(home_rb3, home_te1, slate.site))
        te1_corr.append(find_knn_corr(home_wr1, home_te1, slate.site))
        te1_corr.append(find_knn_corr(home_wr2, home_te1, slate.site))
        if home_wr3:
            te1_corr.append(find_knn_corr(home_wr3, home_te1, slate.site))
        if home_wr4:
            te1_corr.append(find_knn_corr(home_wr4, home_te1, slate.site))
        if home_wr5:
            te1_corr.append(find_knn_corr(home_wr5, home_te1, slate.site))
        te1_corr.append(1.0)  # self
        if home_te2:
            te1_corr.append(find_knn_corr(home_te1, home_te2, slate.site))
        te1_corr.append(0.05)
        te1_corr.append(find_knn_corr(home_te1, home_dst, slate.site))
        te1_corr.append(find_opp_knn_corr(home_te1, away_qb, slate.site))
        te1_corr.append(find_opp_knn_corr(home_te1, away_rb1, slate.site))
        if away_rb2:
            te1_corr.append(find_opp_knn_corr(home_te1, away_rb2, slate.site))
        if away_rb3:
            te1_corr.append(find_opp_knn_corr(home_te1, away_rb3, slate.site))
        te1_corr.append(find_opp_knn_corr(home_te1, away_wr1, slate.site))
        te1_corr.append(find_opp_knn_corr(home_te1, away_wr2, slate.site))
        if away_wr3:
            te1_corr.append(find_opp_knn_corr(home_te1, away_wr3, slate.site))
        if away_wr4:
            te1_corr.append(find_opp_knn_corr(home_te1, away_wr4, slate.site))
        if away_wr5:
            te1_corr.append(find_opp_knn_corr(home_te1, away_wr5, slate.site))
        te1_corr.append(find_opp_knn_corr(home_te1, away_te1, slate.site))
        if away_te2:
            te1_corr.append(find_opp_knn_corr(home_te1, away_te2, slate.site))
        te1_corr.append(0.00)
        te1_corr.append(find_opp_knn_corr(home_te1, away_dst, slate.site))
        correlations.append(te1_corr)

        # TE2
        print('TE2')
        if home_te2:
            te2_corr = []
            te2_corr.append(find_knn_corr(home_qb, home_te2, slate.site))
            te2_corr.append(find_knn_corr(home_rb1, home_te2, slate.site))
            if home_rb2:
                te2_corr.append(find_knn_corr(home_rb2, home_te2, slate.site))
            if home_rb3:
                te2_corr.append(find_knn_corr(home_rb3, home_te2, slate.site))
            te2_corr.append(find_knn_corr(home_wr1, home_te2, slate.site))
            te2_corr.append(find_knn_corr(home_wr2, home_te2, slate.site))
            if home_wr3:
                te2_corr.append(find_knn_corr(home_wr3, home_te2, slate.site))
            if home_wr4:
                te2_corr.append(find_knn_corr(home_wr4, home_te2, slate.site))
            if home_wr5:
                te2_corr.append(find_knn_corr(home_wr5, home_te2, slate.site))
            te2_corr.append(find_knn_corr(home_te1, home_te2, slate.site))
            te2_corr.append(1.0)  # self
            te2_corr.append(0.04)
            te2_corr.append(find_knn_corr(home_te2, home_dst, slate.site))
            te2_corr.append(find_opp_knn_corr(home_te2, away_qb, slate.site))
            te2_corr.append(find_opp_knn_corr(home_te2, away_rb1, slate.site))
            if away_rb2:
                te2_corr.append(find_opp_knn_corr(home_te2, away_rb2, slate.site))
            if away_rb3:
                te2_corr.append(find_opp_knn_corr(home_te2, away_rb3, slate.site))
            te2_corr.append(find_opp_knn_corr(home_te2, away_wr1, slate.site))
            te2_corr.append(find_opp_knn_corr(home_te2, away_wr2, slate.site))
            if away_wr3:
                te2_corr.append(find_opp_knn_corr(home_te2, away_wr3, slate.site))
            if away_wr4:
                te2_corr.append(find_opp_knn_corr(home_te2, away_wr4, slate.site))
            if away_wr5:
                te2_corr.append(find_opp_knn_corr(home_te2, away_wr5, slate.site))
            te2_corr.append(find_opp_knn_corr(home_te2, away_te1, slate.site))
            if away_te2:
                te2_corr.append(find_opp_knn_corr(home_te2, away_te2, slate.site))
            te2_corr.append(0.00)
            te2_corr.append(find_opp_knn_corr(home_te2, away_dst, slate.site))
            correlations.append(te2_corr)

        # K
        print('K')
        k_corr = []
        k_corr.append(0.1)
        k_corr.append(0.06)
        if home_rb2:
            k_corr.append(0.06)
        if home_rb3:
            k_corr.append(0.06)
        k_corr.append(0.05)
        k_corr.append(0)
        if home_wr3:
            k_corr.append(0.01)
        if home_wr4:
            k_corr.append(0)
        if home_wr5:
            k_corr.append(0)
        k_corr.append(0.05)
        if home_te2:
            k_corr.append(0.04)
        k_corr.append(1.0)
        k_corr.append(0.13)
        k_corr.append(-0.03)
        k_corr.append(-0.07)
        if away_rb2:
            k_corr.append(-0.08)
        if away_rb3:
            k_corr.append(-0.09)
        k_corr.append(0.01)
        k_corr.append(0.07)
        if away_wr3:
            k_corr.append(-0.01)
        if away_wr4:
            k_corr.append(-0.01)
        if away_wr5:
            k_corr.append(-0.01)
        k_corr.append(0.0)
        if away_te2:
            k_corr.append(0.0)
        k_corr.append(-0.05)
        k_corr.append(-0.33)
        correlations.append(k_corr)

        # DST
        print('DST')
        dst_corr = []
        dst_corr.append(find_knn_corr(home_qb, home_dst, slate.site))
        dst_corr.append(find_knn_corr(home_rb1, home_dst, slate.site))
        if home_rb2:
            dst_corr.append(find_knn_corr(home_rb2, home_dst, slate.site))
        if home_rb3:
            dst_corr.append(find_knn_corr(home_rb3, home_dst, slate.site))
        dst_corr.append(find_knn_corr(home_wr1, home_dst, slate.site))
        dst_corr.append(find_knn_corr(home_wr2, home_dst, slate.site))
        if home_wr3:
            dst_corr.append(find_knn_corr(home_wr3, home_dst, slate.site))
        if home_wr4:
            dst_corr.append(find_knn_corr(home_wr4, home_dst, slate.site))
        if home_wr5:
            dst_corr.append(find_knn_corr(home_wr5, home_dst, slate.site))
        dst_corr.append(find_knn_corr(home_te1, home_dst, slate.site))
        if home_te2:
            dst_corr.append(find_knn_corr(home_te2, home_dst, slate.site))
        dst_corr.append(0.13)
        dst_corr.append(1.0)  # self
        dst_corr.append(find_opp_knn_corr(home_dst, away_qb, slate.site))
        dst_corr.append(find_opp_knn_corr(home_dst, away_rb1, slate.site))
        if away_rb2:
            dst_corr.append(find_opp_knn_corr(home_dst, away_rb2, slate.site))
        if away_rb3:
            dst_corr.append(find_opp_knn_corr(home_dst, away_rb3, slate.site))
        dst_corr.append(find_opp_knn_corr(home_dst, away_wr1, slate.site))
        dst_corr.append(find_opp_knn_corr(home_dst, away_wr2, slate.site))
        if away_wr3:
            dst_corr.append(find_opp_knn_corr(home_dst, away_wr3, slate.site))
        if away_wr4:
            dst_corr.append(find_opp_knn_corr(home_dst, away_wr4, slate.site))
        if away_wr5:
            dst_corr.append(find_opp_knn_corr(home_dst, away_wr5, slate.site))
        dst_corr.append(find_opp_knn_corr(home_dst, away_te1, slate.site))
        if away_te2:
            dst_corr.append(find_opp_knn_corr(home_dst, away_te2, slate.site))
        dst_corr.append(-.33)
        dst_corr.append(find_opp_knn_corr(home_dst, away_dst, slate.site))
        correlations.append(dst_corr)

        # OPP QB
        print('OPP QB')
        qb_opp_corr = []
        qb_opp_corr.append(find_opp_knn_corr(home_qb, away_qb, slate.site))
        qb_opp_corr.append(find_opp_knn_corr(home_rb1, away_qb, slate.site))
        if home_rb2:
            qb_opp_corr.append(find_opp_knn_corr(home_rb2, away_qb, slate.site))
        if home_rb3:
            qb_opp_corr.append(find_opp_knn_corr(home_rb3, away_qb, slate.site))
        qb_opp_corr.append(find_opp_knn_corr(home_wr1, away_qb, slate.site))
        qb_opp_corr.append(find_opp_knn_corr(home_wr2, away_qb, slate.site))
        if home_wr3:
            qb_opp_corr.append(find_opp_knn_corr(home_wr3, away_qb, slate.site))
        if home_wr4:
            qb_opp_corr.append(find_opp_knn_corr(home_wr4, away_qb, slate.site))
        if home_wr5:
            qb_opp_corr.append(find_opp_knn_corr(home_wr5, away_qb, slate.site))
        qb_opp_corr.append(find_opp_knn_corr(home_te1, away_qb, slate.site))
        if home_te2:
            qb_opp_corr.append(find_opp_knn_corr(home_te2, away_qb, slate.site))
        qb_opp_corr.append(-0.03)
        qb_opp_corr.append(find_opp_knn_corr(home_dst, away_qb, slate.site))
        qb_opp_corr.append(1.0)  # self
        qb_opp_corr.append(find_knn_corr(away_qb, away_rb1, slate.site))
        if away_rb2:
            qb_opp_corr.append(find_knn_corr(away_qb, away_rb2, slate.site))
        if away_rb3:
            qb_opp_corr.append(find_knn_corr(away_qb, away_rb3, slate.site))
        qb_opp_corr.append(find_knn_corr(away_qb, away_wr1, slate.site))
        qb_opp_corr.append(find_knn_corr(away_qb, away_wr2, slate.site))
        if away_wr3:
            qb_opp_corr.append(find_knn_corr(away_qb, away_wr3, slate.site))
        if away_wr4:
            qb_opp_corr.append(find_knn_corr(away_qb, away_wr4, slate.site))
        if away_wr5:
            qb_opp_corr.append(find_knn_corr(away_qb, away_wr5, slate.site))
        qb_opp_corr.append(find_knn_corr(away_qb, away_te1, slate.site))
        if away_te2:
            qb_opp_corr.append(find_knn_corr(away_qb, away_te2, slate.site))
        qb_opp_corr.append(0.1)
        qb_opp_corr.append(find_knn_corr(away_qb, away_dst, slate.site))
        correlations.append(qb_opp_corr)
        
        # OPP RB1
        print('OPP RB1')
        rb1_opp_corr = []
        rb1_opp_corr.append(find_opp_knn_corr(home_qb, away_rb1, slate.site))
        rb1_opp_corr.append(find_opp_knn_corr(home_rb1, away_rb1, slate.site))
        if home_rb2:
            rb1_opp_corr.append(find_opp_knn_corr(home_rb2, away_rb1, slate.site))
        if home_rb3:
            rb1_opp_corr.append(find_opp_knn_corr(home_rb3, away_rb1, slate.site))
        rb1_opp_corr.append(find_opp_knn_corr(home_wr1, away_rb1, slate.site))
        rb1_opp_corr.append(find_opp_knn_corr(home_wr2, away_rb1, slate.site))
        if home_wr3:
            rb1_opp_corr.append(find_opp_knn_corr(home_wr3, away_rb1, slate.site))
        if home_wr4:
            rb1_opp_corr.append(find_opp_knn_corr(home_wr4, away_rb1, slate.site))
        if home_wr5:
            rb1_opp_corr.append(find_opp_knn_corr(home_wr5, away_rb1, slate.site))
        rb1_opp_corr.append(find_opp_knn_corr(home_te1, away_rb1, slate.site))
        if home_te2:
            rb1_opp_corr.append(find_opp_knn_corr(home_te2, away_rb1, slate.site))
        rb1_opp_corr.append(-0.07)
        rb1_opp_corr.append(find_opp_knn_corr(home_dst, away_rb1, slate.site))
        rb1_opp_corr.append(find_knn_corr(away_qb, away_rb1, slate.site))
        rb1_opp_corr.append(1.0)  # self
        if away_rb2:
            rb1_opp_corr.append(find_knn_corr(away_rb1, away_rb2, slate.site))
        if away_rb3:
            rb1_opp_corr.append(find_knn_corr(away_rb1, away_rb3, slate.site))
        rb1_opp_corr.append(find_knn_corr(away_rb1, away_wr1, slate.site))
        rb1_opp_corr.append(find_knn_corr(away_rb1, away_wr2, slate.site))
        if away_wr3:
            rb1_opp_corr.append(find_knn_corr(away_rb1, away_wr3, slate.site))
        if away_wr4:
            rb1_opp_corr.append(find_knn_corr(away_rb1, away_wr4, slate.site))
        if away_wr5:
            rb1_opp_corr.append(find_knn_corr(away_rb1, away_wr5, slate.site))
        rb1_opp_corr.append(find_knn_corr(away_rb1, away_te1, slate.site))
        if away_te2:
            rb1_opp_corr.append(find_knn_corr(away_rb1, away_te2, slate.site))
        rb1_opp_corr.append(0.06)
        rb1_opp_corr.append(find_knn_corr(away_rb1, away_dst, slate.site))
        correlations.append(rb1_opp_corr)
        
        # OPP RB2
        print('OPP RB2')
        if away_rb2:
            rb2_opp_corr = []
            rb2_opp_corr.append(find_opp_knn_corr(home_qb, away_rb2, slate.site))
            rb2_opp_corr.append(find_opp_knn_corr(home_rb1, away_rb2, slate.site))
            if home_rb2:
                rb2_opp_corr.append(find_opp_knn_corr(home_rb2, away_rb2, slate.site))
            if home_rb3:
                rb2_opp_corr.append(find_opp_knn_corr(home_rb3, away_rb2, slate.site))
            rb2_opp_corr.append(find_opp_knn_corr(home_wr1, away_rb2, slate.site))
            rb2_opp_corr.append(find_opp_knn_corr(home_wr2, away_rb2, slate.site))
            if home_wr3:
                rb2_opp_corr.append(find_opp_knn_corr(home_wr3, away_rb2, slate.site))
            if home_wr4:
                rb2_opp_corr.append(find_opp_knn_corr(home_wr4, away_rb2, slate.site))
            if home_wr5:
                rb2_opp_corr.append(find_opp_knn_corr(home_wr5, away_rb2, slate.site))
            rb2_opp_corr.append(find_opp_knn_corr(home_te1, away_rb2, slate.site))
            if home_te2:
                rb2_opp_corr.append(find_opp_knn_corr(home_te2, away_rb2, slate.site))
            rb2_opp_corr.append(-0.08)
            rb2_opp_corr.append(find_opp_knn_corr(home_dst, away_rb2, slate.site))
            rb2_opp_corr.append(find_knn_corr(away_qb, away_rb2, slate.site))
            rb2_opp_corr.append(find_knn_corr(away_rb1, away_rb2, slate.site))
            rb2_opp_corr.append(1.0)  # self
            if away_rb3:
                rb2_opp_corr.append(find_knn_corr(away_rb2, away_rb3, slate.site))
            rb2_opp_corr.append(find_knn_corr(away_rb2, away_wr1, slate.site))
            rb2_opp_corr.append(find_knn_corr(away_rb2, away_wr2, slate.site))
            if away_wr3:
                rb2_opp_corr.append(find_knn_corr(away_rb2, away_wr3, slate.site))
            if away_wr4:
                rb2_opp_corr.append(find_knn_corr(away_rb2, away_wr4, slate.site))
            if away_wr5:
                rb2_opp_corr.append(find_knn_corr(away_rb2, away_wr5, slate.site))
            rb2_opp_corr.append(find_knn_corr(away_rb2, away_te1, slate.site))
            if away_te2:
                rb2_opp_corr.append(find_knn_corr(away_rb2, away_te2, slate.site))
            rb2_opp_corr.append(0.06)
            rb2_opp_corr.append(find_knn_corr(away_rb2, away_dst, slate.site))
            correlations.append(rb2_opp_corr)
        
        # OPP RB3
        print('OPP RB3')
        if away_rb3:
            rb3_opp_corr = []
            rb3_opp_corr.append(find_opp_knn_corr(home_qb, away_rb3, slate.site))
            rb3_opp_corr.append(find_opp_knn_corr(home_rb1, away_rb3, slate.site))
            rb3_opp_corr.append(find_opp_knn_corr(home_rb2, away_rb3, slate.site))
            if home_rb3:
                rb3_opp_corr.append(find_opp_knn_corr(home_rb3, away_rb3, slate.site))
            rb3_opp_corr.append(find_opp_knn_corr(home_wr1, away_rb3, slate.site))
            rb3_opp_corr.append(find_opp_knn_corr(home_wr2, away_rb3, slate.site))
            if home_wr3:
                rb3_opp_corr.append(find_opp_knn_corr(home_wr3, away_rb3, slate.site))
            if home_wr4:
                rb3_opp_corr.append(find_opp_knn_corr(home_wr4, away_rb3, slate.site))
            if home_wr5:
                rb3_opp_corr.append(find_opp_knn_corr(home_wr5, away_rb3, slate.site))
            rb3_opp_corr.append(find_opp_knn_corr(home_te1, away_rb3, slate.site))
            if home_te2:
                rb3_opp_corr.append(find_opp_knn_corr(home_te2, away_rb3, slate.site))
            rb3_opp_corr.append(-0.09)
            rb3_opp_corr.append(find_opp_knn_corr(home_dst, away_rb3, slate.site))
            rb3_opp_corr.append(find_knn_corr(away_qb, away_rb3, slate.site))
            rb3_opp_corr.append(find_knn_corr(away_rb1, away_rb3, slate.site))
            if away_rb2:
                rb3_opp_corr.append(find_knn_corr(away_rb2, away_rb3, slate.site))
            rb3_opp_corr.append(1.0)  # self
            rb3_opp_corr.append(find_knn_corr(away_rb3, away_wr1, slate.site))
            rb3_opp_corr.append(find_knn_corr(away_rb3, away_wr2, slate.site))
            if away_wr3:
                rb3_opp_corr.append(find_knn_corr(away_rb3, away_wr3, slate.site))
            if away_wr4:
                rb3_opp_corr.append(find_knn_corr(away_rb3, away_wr4, slate.site))
            if away_wr5:
                rb3_opp_corr.append(find_knn_corr(away_rb3, away_wr5, slate.site))
            rb3_opp_corr.append(find_knn_corr(away_rb3, away_te1, slate.site))
            if away_te2:
                rb3_opp_corr.append(find_knn_corr(away_rb3, away_te2, slate.site))
            rb3_opp_corr.append(0.06)
            rb3_opp_corr.append(find_knn_corr(away_rb3, away_dst, slate.site))
            correlations.append(rb3_opp_corr)

        # OPP WR1
        print('OPP WR1')
        wr1_opp_corr = []
        wr1_opp_corr.append(find_opp_knn_corr(home_qb, away_wr1, slate.site))
        wr1_opp_corr.append(find_opp_knn_corr(home_rb1, away_wr1, slate.site))
        if home_rb2:
            wr1_opp_corr.append(find_opp_knn_corr(home_rb2, away_wr1, slate.site))
        if home_rb3:
            wr1_opp_corr.append(find_opp_knn_corr(home_rb3, away_wr1, slate.site))
        wr1_opp_corr.append(find_opp_knn_corr(home_wr1, away_wr1, slate.site))
        wr1_opp_corr.append(find_opp_knn_corr(home_wr2, away_wr1, slate.site))
        if home_wr3:
            wr1_opp_corr.append(find_opp_knn_corr(home_wr3, away_wr1, slate.site))
        if home_wr4:
            wr1_opp_corr.append(find_opp_knn_corr(home_wr4, away_wr1, slate.site))
        if home_wr5:
            wr1_opp_corr.append(find_opp_knn_corr(home_wr5, away_wr1, slate.site))
        wr1_opp_corr.append(find_opp_knn_corr(home_te1, away_wr1, slate.site))
        if home_te2:
            wr1_opp_corr.append(find_opp_knn_corr(home_te2, away_wr1, slate.site))
        wr1_opp_corr.append(0.01)
        wr1_opp_corr.append(find_opp_knn_corr(home_dst, away_wr1, slate.site))
        wr1_opp_corr.append(find_knn_corr(away_qb, away_wr1, slate.site))
        wr1_opp_corr.append(find_knn_corr(away_rb1, away_wr1, slate.site))
        if away_rb2:
            wr1_opp_corr.append(find_knn_corr(away_rb2, away_wr1, slate.site))
        if away_rb3:
            wr1_opp_corr.append(find_knn_corr(away_rb3, away_wr1, slate.site))
        wr1_opp_corr.append(1.0)  # self
        wr1_opp_corr.append(find_knn_corr(away_wr1, away_wr2, slate.site))
        if away_wr3:
            wr1_opp_corr.append(find_knn_corr(away_wr1, away_wr3, slate.site))
        if away_wr4:
            wr1_opp_corr.append(find_knn_corr(away_wr1, away_wr4, slate.site))
        if away_wr5:
            wr1_opp_corr.append(find_knn_corr(away_wr1, away_wr5, slate.site))
        wr1_opp_corr.append(find_knn_corr(away_wr1, away_te1, slate.site))
        if away_te2:
            wr1_opp_corr.append(find_knn_corr(away_wr1, away_te2, slate.site))
        wr1_opp_corr.append(0.05)
        wr1_opp_corr.append(find_knn_corr(away_wr1, away_dst, slate.site))
        correlations.append(wr1_opp_corr)

        # OPP WR2
        print('OPP WR2')
        wr2_opp_corr = []
        wr2_opp_corr.append(find_opp_knn_corr(home_qb, away_wr2, slate.site))
        wr2_opp_corr.append(find_opp_knn_corr(home_rb1, away_wr2, slate.site))
        if home_rb2:
            wr2_opp_corr.append(find_opp_knn_corr(home_rb2, away_wr2, slate.site))
        if home_rb3:
            wr2_opp_corr.append(find_opp_knn_corr(home_rb3, away_wr2, slate.site))
        wr2_opp_corr.append(find_opp_knn_corr(home_wr1, away_wr2, slate.site))
        wr2_opp_corr.append(find_opp_knn_corr(home_wr2, away_wr2, slate.site))
        if home_wr3:
            wr2_opp_corr.append(find_opp_knn_corr(home_wr3, away_wr2, slate.site))
        if home_wr4:
            wr2_opp_corr.append(find_opp_knn_corr(home_wr4, away_wr2, slate.site))
        if home_wr5:
            wr2_opp_corr.append(find_opp_knn_corr(home_wr5, away_wr2, slate.site))
        wr2_opp_corr.append(find_opp_knn_corr(home_te1, away_wr2, slate.site))
        if home_te2:
            wr2_opp_corr.append(find_opp_knn_corr(home_te2, away_wr2, slate.site))
        wr2_opp_corr.append(0.07)
        wr2_opp_corr.append(find_opp_knn_corr(home_dst, away_wr2, slate.site))
        wr2_opp_corr.append(find_knn_corr(away_qb, away_wr2, slate.site))
        wr2_opp_corr.append(find_knn_corr(away_rb1, away_wr2, slate.site))
        if away_rb2:
            wr2_opp_corr.append(find_knn_corr(away_rb2, away_wr2, slate.site))
        if away_rb3:
            wr2_opp_corr.append(find_knn_corr(away_rb3, away_wr2, slate.site))
        wr2_opp_corr.append(find_knn_corr(away_wr1, away_wr2, slate.site))
        wr2_opp_corr.append(1.0)  # self
        if away_wr3:
            wr2_opp_corr.append(find_knn_corr(away_wr2, away_wr3, slate.site))
        if away_wr4:
            wr2_opp_corr.append(find_knn_corr(away_wr2, away_wr4, slate.site))
        if away_wr5:
            wr2_opp_corr.append(find_knn_corr(away_wr2, away_wr5, slate.site))
        wr2_opp_corr.append(find_knn_corr(away_wr2, away_te1, slate.site))
        if away_te2:
            wr2_opp_corr.append(find_knn_corr(away_wr2, away_te2, slate.site))
        wr2_opp_corr.append(0.00)
        wr2_opp_corr.append(find_knn_corr(away_wr2, away_dst, slate.site))
        correlations.append(wr2_opp_corr)
        
        # OPP WR3
        print('OPP WR3')
        if away_wr3:
            wr3_opp_corr = []
            wr3_opp_corr.append(find_opp_knn_corr(home_qb, away_wr3, slate.site))
            wr3_opp_corr.append(find_opp_knn_corr(home_rb1, away_wr3, slate.site))
            if home_rb2:
                wr3_opp_corr.append(find_opp_knn_corr(home_rb2, away_wr3, slate.site))
            if home_rb3:
                wr3_opp_corr.append(find_opp_knn_corr(home_rb3, away_wr3, slate.site))
            wr3_opp_corr.append(find_opp_knn_corr(home_wr1, away_wr3, slate.site))
            wr3_opp_corr.append(find_opp_knn_corr(home_wr2, away_wr3, slate.site))
            if home_wr3:
                wr3_opp_corr.append(find_opp_knn_corr(home_wr3, away_wr3, slate.site))
            if home_wr4:
                wr3_opp_corr.append(find_opp_knn_corr(home_wr4, away_wr3, slate.site))
            if home_wr5:
                wr3_opp_corr.append(find_opp_knn_corr(home_wr5, away_wr3, slate.site))
            wr3_opp_corr.append(find_opp_knn_corr(home_te1, away_wr3, slate.site))
            if home_te2:
                wr3_opp_corr.append(find_opp_knn_corr(home_te2, away_wr3, slate.site))
            wr3_opp_corr.append(-0.01)
            wr3_opp_corr.append(find_opp_knn_corr(home_dst, away_wr3, slate.site))
            wr3_opp_corr.append(find_knn_corr(away_qb, away_wr3, slate.site))
            wr3_opp_corr.append(find_knn_corr(away_rb1, away_wr3, slate.site))
            if away_rb2:
                wr3_opp_corr.append(find_knn_corr(away_rb2, away_wr3, slate.site))
            if away_rb3:
                wr3_opp_corr.append(find_knn_corr(away_rb3, away_wr3, slate.site))
            wr3_opp_corr.append(find_knn_corr(away_wr1, away_wr3, slate.site))
            wr3_opp_corr.append(find_knn_corr(away_wr2, away_wr3, slate.site))
            wr3_opp_corr.append(1.0)  # self
            if away_wr4:
                wr3_opp_corr.append(find_knn_corr(away_wr3, away_wr4, slate.site))
            if away_wr5:
                wr3_opp_corr.append(find_knn_corr(away_wr3, away_wr5, slate.site))
            wr3_opp_corr.append(find_knn_corr(away_wr3, away_te1, slate.site))
            if away_te2:
                wr3_opp_corr.append(find_knn_corr(away_wr3, away_te2, slate.site))
            wr3_opp_corr.append(0.00)
            wr3_opp_corr.append(find_knn_corr(away_wr3, away_dst, slate.site))
            correlations.append(wr3_opp_corr)
        
        # OPP WR4
        print('OPP WR4')
        if away_wr4:
            wr4_opp_corr = []
            wr4_opp_corr.append(find_opp_knn_corr(home_qb, away_wr4, slate.site))
            wr4_opp_corr.append(find_opp_knn_corr(home_rb1, away_wr4, slate.site))
            if home_rb2:
                wr4_opp_corr.append(find_opp_knn_corr(home_rb2, away_wr4, slate.site))
            if home_rb3:
                wr4_opp_corr.append(find_opp_knn_corr(home_rb3, away_wr4, slate.site))
            wr4_opp_corr.append(find_opp_knn_corr(home_wr1, away_wr4, slate.site))
            wr4_opp_corr.append(find_opp_knn_corr(home_wr2, away_wr4, slate.site))
            if home_wr3:
                wr4_opp_corr.append(find_opp_knn_corr(home_wr3, away_wr4, slate.site))
            if home_wr4:
                wr4_opp_corr.append(find_opp_knn_corr(home_wr4, away_wr4, slate.site))
            if home_wr5:
                wr4_opp_corr.append(find_opp_knn_corr(home_wr5, away_wr4, slate.site))
            wr4_opp_corr.append(find_opp_knn_corr(home_te1, away_wr4, slate.site))
            if home_te2:
                wr4_opp_corr.append(find_opp_knn_corr(home_te2, away_wr4, slate.site))
            wr4_opp_corr.append(-0.01)
            wr4_opp_corr.append(find_opp_knn_corr(home_dst, away_wr4, slate.site))
            wr4_opp_corr.append(find_knn_corr(away_qb, away_wr4, slate.site))
            wr4_opp_corr.append(find_knn_corr(away_rb1, away_wr4, slate.site))
            if away_rb2:
                wr4_opp_corr.append(find_knn_corr(away_rb2, away_wr4, slate.site))
            if away_rb3:
                wr4_opp_corr.append(find_knn_corr(away_rb3, away_wr4, slate.site))
            wr4_opp_corr.append(find_knn_corr(away_wr1, away_wr4, slate.site))
            wr4_opp_corr.append(find_knn_corr(away_wr2, away_wr4, slate.site))
            if away_wr3:
                wr4_opp_corr.append(find_knn_corr(away_wr3, away_wr4, slate.site))
            wr4_opp_corr.append(1.0)  # self
            if away_wr5:
                wr4_opp_corr.append(find_knn_corr(away_wr4, away_wr5, slate.site))
            wr4_opp_corr.append(find_knn_corr(away_wr4, away_te1, slate.site))
            if away_te2:
                wr4_opp_corr.append(find_knn_corr(away_wr4, away_te2, slate.site))
            wr4_opp_corr.append(0.01)
            wr4_opp_corr.append(find_knn_corr(away_wr4, away_dst, slate.site))
            correlations.append(wr4_opp_corr)
        
        # OPP WR5
        print('OPP WR5')
        if away_wr5:
            wr5_opp_corr = []
            wr5_opp_corr.append(find_opp_knn_corr(home_qb, away_wr5, slate.site))
            wr5_opp_corr.append(find_opp_knn_corr(home_rb1, away_wr5, slate.site))
            if home_rb2:
                wr5_opp_corr.append(find_opp_knn_corr(home_rb2, away_wr5, slate.site))
            if home_rb3:
                wr5_opp_corr.append(find_opp_knn_corr(home_rb3, away_wr5, slate.site))
            wr5_opp_corr.append(find_opp_knn_corr(home_wr1, away_wr5, slate.site))
            wr5_opp_corr.append(find_opp_knn_corr(home_wr2, away_wr5, slate.site))
            if home_wr3:
                wr5_opp_corr.append(find_opp_knn_corr(home_wr3, away_wr5, slate.site))
            if home_wr4:
                wr5_opp_corr.append(find_opp_knn_corr(home_wr4, away_wr5, slate.site))
            if home_wr5:
                wr5_opp_corr.append(find_opp_knn_corr(home_wr5, away_wr5, slate.site))
            wr5_opp_corr.append(find_opp_knn_corr(home_te1, away_wr5, slate.site))
            if home_te2:
                wr5_opp_corr.append(find_opp_knn_corr(home_te2, away_wr5, slate.site))
            wr5_opp_corr.append(-0.01)
            wr5_opp_corr.append(find_opp_knn_corr(home_dst, away_wr5, slate.site))
            wr5_opp_corr.append(find_knn_corr(away_qb, away_wr5, slate.site))
            wr5_opp_corr.append(find_knn_corr(away_rb1, away_wr5, slate.site))
            if away_rb2:
                wr5_opp_corr.append(find_knn_corr(away_rb2, away_wr5, slate.site))
            if away_rb3:
                wr5_opp_corr.append(find_knn_corr(away_rb3, away_wr5, slate.site))
            wr5_opp_corr.append(find_knn_corr(away_wr1, away_wr5, slate.site))
            wr5_opp_corr.append(find_knn_corr(away_wr2, away_wr5, slate.site))
            if away_wr3:
                wr5_opp_corr.append(find_knn_corr(away_wr3, away_wr5, slate.site))
            if away_wr4:
                wr5_opp_corr.append(find_knn_corr(away_wr4, away_wr5, slate.site))
            wr5_opp_corr.append(1.0)  # self
            wr5_opp_corr.append(find_knn_corr(away_wr5, away_te1, slate.site))
            if away_te2:
                wr5_opp_corr.append(find_knn_corr(away_wr5, away_te2, slate.site))
            wr5_opp_corr.append(0.00)
            wr5_opp_corr.append(find_knn_corr(away_wr5, away_dst, slate.site))
            correlations.append(wr5_opp_corr)

        # OPP TE1
        print('OPP TE1')
        te1_opp_corr = []
        te1_opp_corr.append(find_opp_knn_corr(home_qb, away_te1, slate.site))
        te1_opp_corr.append(find_opp_knn_corr(home_rb1, away_te1, slate.site))
        if home_rb2:
            te1_opp_corr.append(find_opp_knn_corr(home_rb2, away_te1, slate.site))
        if home_rb3:
            te1_opp_corr.append(find_opp_knn_corr(home_rb3, away_te1, slate.site))
        te1_opp_corr.append(find_opp_knn_corr(home_wr1, away_te1, slate.site))
        te1_opp_corr.append(find_opp_knn_corr(home_wr2, away_te1, slate.site))
        if home_wr3:
            te1_opp_corr.append(find_opp_knn_corr(home_wr3, away_te1, slate.site))
        if home_wr4:
            te1_opp_corr.append(find_opp_knn_corr(home_wr4, away_te1, slate.site))
        if home_wr5:
            te1_opp_corr.append(find_opp_knn_corr(home_wr5, away_te1, slate.site))
        te1_opp_corr.append(find_opp_knn_corr(home_te1, away_te1, slate.site))
        if home_te2:
            te1_opp_corr.append(find_opp_knn_corr(home_te2, away_te1, slate.site))
        te1_opp_corr.append(0.00)
        te1_opp_corr.append(find_opp_knn_corr(home_dst, away_te1, slate.site))
        te1_opp_corr.append(find_knn_corr(away_qb, away_te1, slate.site))
        te1_opp_corr.append(find_knn_corr(away_rb1, away_te1, slate.site))
        if away_rb2:
            te1_opp_corr.append(find_knn_corr(away_rb2, away_te1, slate.site))
        if away_rb3:
            te1_opp_corr.append(find_knn_corr(away_rb3, away_te1, slate.site))
        te1_opp_corr.append(find_knn_corr(away_wr1, away_te1, slate.site))
        te1_opp_corr.append(find_knn_corr(away_wr2, away_te1, slate.site))
        if away_wr3:
            te1_opp_corr.append(find_knn_corr(away_wr3, away_te1, slate.site))
        if away_wr4:
            te1_opp_corr.append(find_knn_corr(away_wr4, away_te1, slate.site))
        if away_wr5:
            te1_opp_corr.append(find_knn_corr(away_wr5, away_te1, slate.site))
        te1_opp_corr.append(1.0)  # self
        if away_te2:
            te1_opp_corr.append(find_knn_corr(away_te1, away_te2, slate.site))
        te1_opp_corr.append(0.05)
        te1_opp_corr.append(find_knn_corr(away_te1, away_dst, slate.site))
        correlations.append(te1_opp_corr)

        # OPP TE2
        print('OPP TE2')
        if away_te2:
            te2_opp_corr = []
            te2_opp_corr.append(find_opp_knn_corr(home_qb, away_te2, slate.site))
            te2_opp_corr.append(find_opp_knn_corr(home_rb1, away_te2, slate.site))
            if home_rb2:
                te2_opp_corr.append(find_opp_knn_corr(home_rb2, away_te2, slate.site))
            if home_rb3:
                te2_opp_corr.append(find_opp_knn_corr(home_rb3, away_te2, slate.site))
            te2_opp_corr.append(find_opp_knn_corr(home_wr1, away_te2, slate.site))
            te2_opp_corr.append(find_opp_knn_corr(home_wr2, away_te2, slate.site))
            if home_wr3:
                te2_opp_corr.append(find_opp_knn_corr(home_wr3, away_te2, slate.site))
            if home_wr4:
                te2_opp_corr.append(find_opp_knn_corr(home_wr4, away_te2, slate.site))
            if home_wr5:
                te2_opp_corr.append(find_opp_knn_corr(home_wr5, away_te2, slate.site))
            te2_opp_corr.append(find_opp_knn_corr(home_te1, away_te2, slate.site))
            if home_te2:
                te2_opp_corr.append(find_opp_knn_corr(home_te2, away_te2, slate.site))
            te2_opp_corr.append(0.00)
            te2_opp_corr.append(find_opp_knn_corr(home_dst, away_te2, slate.site))
            te2_opp_corr.append(find_knn_corr(away_qb, away_te2, slate.site))
            te2_opp_corr.append(find_knn_corr(away_rb1, away_te2, slate.site))
            if away_rb2:
                te2_opp_corr.append(find_knn_corr(away_rb2, away_te2, slate.site))
            if away_rb3:
                te2_opp_corr.append(find_knn_corr(away_rb3, away_te2, slate.site))
            te2_opp_corr.append(find_knn_corr(away_wr1, away_te2, slate.site))
            te2_opp_corr.append(find_knn_corr(away_wr2, away_te2, slate.site))
            if away_wr3:
                te2_opp_corr.append(find_knn_corr(away_wr3, away_te2, slate.site))
            if away_wr4:
                te2_opp_corr.append(find_knn_corr(away_wr4, away_te2, slate.site))
            if away_wr5:
                te2_opp_corr.append(find_knn_corr(away_wr5, away_te2, slate.site))
            te2_opp_corr.append(find_knn_corr(away_te1, away_te2, slate.site))
            te2_opp_corr.append(1.0)  # self
            te2_opp_corr.append(0.04)
            te2_opp_corr.append(find_knn_corr(away_te2, away_dst, slate.site))
            correlations.append(te2_opp_corr)

        # OPP K
        print('OPP K')
        k_opp_corr = []
        k_opp_corr.append(-0.03)
        k_opp_corr.append(-0.07)
        if away_rb2:
            k_opp_corr.append(-0.08)
        if away_rb3:
            k_opp_corr.append(-0.09)
        k_opp_corr.append(0.01)
        k_opp_corr.append(0.07)
        if away_wr3:
            k_opp_corr.append(-0.01)
        if away_wr4:
            k_opp_corr.append(-0.01)
        if away_wr5:
            k_opp_corr.append(-0.01)
        k_opp_corr.append(0.0)
        if away_te2:
            k_opp_corr.append(0.0)
        k_opp_corr.append(-0.05)
        k_opp_corr.append(-0.33)
        k_opp_corr.append(0.1)
        k_opp_corr.append(0.06)
        if home_rb2:
            k_opp_corr.append(0.06)
        if home_rb3:
            k_opp_corr.append(0.06)
        k_opp_corr.append(0.05)
        k_opp_corr.append(0)
        if home_wr3:
            k_opp_corr.append(0.0)
        if home_wr4:
            k_opp_corr.append(0.01)
        if home_wr5:
            k_opp_corr.append(0)
        k_opp_corr.append(0.05)
        if home_te2:
            k_opp_corr.append(0.04)
        k_opp_corr.append(1.0)
        k_opp_corr.append(0.13)
        correlations.append(k_opp_corr)

        # OPP DST
        print('OPP DST')
        dst_opp_corr = []
        dst_opp_corr.append(find_opp_knn_corr(home_qb, away_dst, slate.site))
        dst_opp_corr.append(find_opp_knn_corr(home_rb1, away_dst, slate.site))
        if home_rb2:
            dst_opp_corr.append(find_opp_knn_corr(home_rb2, away_dst, slate.site))
        if home_rb3:
            dst_opp_corr.append(find_opp_knn_corr(home_rb3, away_dst, slate.site))
        dst_opp_corr.append(find_opp_knn_corr(home_wr1, away_dst, slate.site))
        dst_opp_corr.append(find_opp_knn_corr(home_wr2, away_dst, slate.site))
        if home_wr3:
            dst_opp_corr.append(find_opp_knn_corr(home_wr3, away_dst, slate.site))
        if home_wr4:
            dst_opp_corr.append(find_opp_knn_corr(home_wr4, away_dst, slate.site))
        if home_wr5:
            dst_opp_corr.append(find_opp_knn_corr(home_wr5, away_dst, slate.site))
        dst_opp_corr.append(find_opp_knn_corr(home_te1, away_dst, slate.site))
        if home_te2:
            dst_opp_corr.append(find_opp_knn_corr(home_te2, away_dst, slate.site))
        dst_opp_corr.append(-0.33)
        dst_opp_corr.append(find_opp_knn_corr(home_dst, away_dst, slate.site))
        dst_opp_corr.append(find_knn_corr(away_qb, away_dst, slate.site))
        dst_opp_corr.append(find_knn_corr(away_rb1, away_dst, slate.site))
        if away_rb2:
            dst_opp_corr.append(find_knn_corr(away_rb2, away_dst, slate.site))
        if away_rb3:
            dst_opp_corr.append(find_knn_corr(away_rb3, away_dst, slate.site))
        dst_opp_corr.append(find_knn_corr(away_wr1, away_dst, slate.site))
        dst_opp_corr.append(find_knn_corr(away_wr2, away_dst, slate.site))
        if away_wr3:
            dst_opp_corr.append(find_knn_corr(away_wr3, away_dst, slate.site))
        if away_wr4:
            dst_opp_corr.append(find_knn_corr(away_wr4, away_dst, slate.site))
        if away_wr5:
            dst_opp_corr.append(find_knn_corr(away_wr5, away_dst, slate.site))
        dst_opp_corr.append(find_knn_corr(away_te1, away_dst, slate.site))
        if away_te2:
            dst_opp_corr.append(find_knn_corr(away_te2, away_dst, slate.site))
        dst_opp_corr.append(0.13)
        dst_opp_corr.append(1.0)  # self
        correlations.append(dst_opp_corr)

        A = pd.DataFrame(correlations)
        print(A)
        find_symmetric(A)
        # assert (isPD(A))
        # A.to_csv(f'data/sample_corr.csv')
        print(pd.DataFrame(utils.nearcorr(A)))
        # B = nearestPD(A)
        # assert (isPD(B))
        # print(B)
        # C = pd.DataFrame(get_near_psd(A))
        # print(C)
