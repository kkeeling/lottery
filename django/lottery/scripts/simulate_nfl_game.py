import math
import mcerp
import numpy as np
import pandas as pd
import scipy
import traceback

from nfl import models


def run():
    N = 10000

    r_df = pd.read_csv('data/r.csv', index_col=0)
    c_target = r_df.to_numpy()
    r0 = [0] * c_target.shape[0]
    mv_norm = scipy.stats.multivariate_normal(mean=r0, cov=c_target)
    rand_Nmv = mv_norm.rvs(N) 
    rand_U = scipy.stats.norm.cdf(rand_Nmv)

    
    # c = scipy.linalg.cholesky(r_df, lower=True)

    slate = models.Slate.objects.filter(week__slate_year=2021, week__num=5, site='fanduel').order_by('?')[0]

    for game in slate.games.all():
        try:
            home_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_home_players().values_list('id', flat=True))
            away_players = models.SlatePlayerProjection.objects.filter(slate_player__id__in=game.get_away_players().values_list('id', flat=True))

            home_qb = home_players.filter(slate_player__site_pos='QB').order_by('-projection', '-slate_player__salary')[0]
            home_rb1 = home_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[0]
            home_rb2 = home_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[1]
            home_wr1 = home_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[0]
            home_wr2 = home_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[1]
            home_wr3 = home_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[2]
            home_te = home_players.filter(slate_player__site_pos='TE').order_by('-projection', '-slate_player__salary')[0]
            home_dst = home_players.filter(slate_player__site_pos='D').order_by('-projection', '-slate_player__salary')[0]

            away_qb = away_players.filter(slate_player__site_pos='QB').order_by('-projection', '-slate_player__salary')[0]
            away_rb1 = away_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[0]
            away_rb2 = away_players.filter(slate_player__site_pos='RB').order_by('-projection', '-slate_player__salary')[1]
            away_wr1 = away_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[0]
            away_wr2 = away_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[1]
            away_wr3 = away_players.filter(slate_player__site_pos='WR').order_by('-projection', '-slate_player__salary')[2]
            away_te = away_players.filter(slate_player__site_pos='TE').order_by('-projection', '-slate_player__salary')[0]
            away_dst = away_players.filter(slate_player__site_pos='D').order_by('-projection', '-slate_player__salary')[0]

            home_qb_rv = scipy.stats.gamma((float(home_qb.projection)/float(home_qb.stdev))**2, scale=(float(home_qb.stdev)**2)/float(home_qb.projection))
            home_rb1_rv = scipy.stats.gamma((float(home_rb1.projection)/float(home_rb1.stdev))**2, scale=(float(home_rb1.stdev)**2)/float(home_rb1.projection))
            home_rb2_rv = scipy.stats.gamma((float(home_rb2.projection)/float(home_rb2.stdev))**2, scale=(float(home_rb2.stdev)**2)/float(home_rb2.projection))
            home_wr1_rv = scipy.stats.gamma((float(home_wr1.projection)/float(home_wr1.stdev))**2, scale=(float(home_wr1.stdev)**2)/float(home_wr1.projection))
            home_wr2_rv = scipy.stats.gamma((float(home_wr2.projection)/float(home_wr2.stdev))**2, scale=(float(home_wr2.stdev)**2)/float(home_wr2.projection))
            home_wr3_rv = scipy.stats.gamma((float(home_wr3.projection)/float(home_wr3.stdev))**2, scale=(float(home_wr3.stdev)**2)/float(home_wr3.projection))
            home_te_rv = scipy.stats.gamma((float(home_te.projection)/float(home_te.stdev))**2, scale=(float(home_te.stdev)**2)/float(home_te.projection))
            home_dst_rv = scipy.stats.gamma((float(home_dst.projection)/float(home_dst.stdev))**2, scale=(float(home_dst.stdev)**2)/float(home_dst.projection))
            away_qb_rv = scipy.stats.gamma((float(away_qb.projection)/float(away_qb.stdev))**2, scale=(float(away_qb.stdev)**2)/float(away_qb.projection))
            away_rb1_rv = scipy.stats.gamma((float(away_rb1.projection)/float(away_rb1.stdev))**2, scale=(float(away_rb1.stdev)**2)/float(away_rb1.projection))
            away_rb2_rv = scipy.stats.gamma((float(away_rb2.projection)/float(away_rb2.stdev))**2, scale=(float(away_rb2.stdev)**2)/float(away_rb2.projection))
            away_wr1_rv = scipy.stats.gamma((float(away_wr1.projection)/float(away_wr1.stdev))**2, scale=(float(away_wr1.stdev)**2)/float(away_wr1.projection))
            away_wr2_rv = scipy.stats.gamma((float(away_wr2.projection)/float(away_wr2.stdev))**2, scale=(float(away_wr2.stdev)**2)/float(away_wr2.projection))
            away_wr3_rv = scipy.stats.gamma((float(away_wr3.projection)/float(away_wr3.stdev))**2, scale=(float(away_wr3.stdev)**2)/float(away_wr3.projection))
            away_te_rv = scipy.stats.gamma((float(away_te.projection)/float(away_te.stdev))**2, scale=(float(away_te.stdev)**2)/float(away_te.projection))
            away_dst_rv = scipy.stats.gamma((float(away_dst.projection)/float(away_dst.stdev))**2, scale=(float(away_dst.stdev)**2)/float(away_dst.projection))

            rand_home_qb = home_qb_rv.ppf(rand_U[:, 0])
            rand_home_rb1 = home_rb1_rv.ppf(rand_U[:, 1])
            rand_home_rb2 = home_rb2_rv.ppf(rand_U[:, 2])
            rand_home_wr1 = home_wr1_rv.ppf(rand_U[:, 3])
            rand_home_wr2 = home_wr2_rv.ppf(rand_U[:, 4])
            rand_home_wr3 = home_wr3_rv.ppf(rand_U[:, 5])
            rand_home_te = home_te_rv.ppf(rand_U[:, 6])
            rand_home_dst = home_dst_rv.ppf(rand_U[:, 7])
            rand_away_qb = away_qb_rv.ppf(rand_U[:, 8])
            rand_away_rb1 = away_rb1_rv.ppf(rand_U[:, 9])
            rand_away_rb2 = away_rb2_rv.ppf(rand_U[:, 10])
            rand_away_wr1 = away_wr1_rv.ppf(rand_U[:, 11])
            rand_away_wr2 = away_wr2_rv.ppf(rand_U[:, 12])
            rand_away_wr3 = away_wr3_rv.ppf(rand_U[:, 13])
            rand_away_te = away_te_rv.ppf(rand_U[:, 14])
            rand_away_dst = away_dst_rv.ppf(rand_U[:, 15])
            
            df_scores = pd.DataFrame([
                rand_home_qb,
                rand_home_rb1,
                rand_home_rb2,
                rand_home_wr1,
                rand_home_wr2,
                rand_home_wr3,
                rand_home_te,
                rand_home_dst,
                rand_away_qb,
                rand_away_rb1,
                rand_away_rb2,
                rand_away_wr1,
                rand_away_wr2,
                rand_away_wr3,
                rand_away_te,
                rand_away_dst,
            ])

            df_scores.to_csv(f'data/{game.slate}-{game.game.away_team} @ {game.game.home_team}.csv')
        except:
            traceback.print_exc()