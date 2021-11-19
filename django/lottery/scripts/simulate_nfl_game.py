import math
import numpy as np
import pandas as pd
import scipy
import traceback

from nfl import models


def run():
    r_df = pd.read_csv('data/nfl_correl_matrix_no_k_test.csv', index_col=0)
    c = scipy.linalg.cholesky(r_df)

    slate = models.Slate.objects.filter(week__slate_year=2021, week__num=5, site='fanduel').order_by('?')[0]

    for game in [slate.games.all()[4]]:
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

            t = []

            home_qb_scores = []
            home_rb1_scores = []
            home_rb2_scores = []
            home_wr1_scores = []
            home_wr2_scores = []
            home_wr3_scores = []
            home_te_scores = []
            home_dst_scores = []

            away_qb_scores = []
            away_rb1_scores = []
            away_rb2_scores = []
            away_wr1_scores = []
            away_wr2_scores = []
            away_wr3_scores = []
            away_te_scores = []
            away_dst_scores = []

            for _ in range(0, 10000):
                # x = [
                #     np.random.gamma((float(home_qb.projection)/float(home_qb.stdev))**2, (float(home_qb.stdev)**2)/float(home_qb.projection)),
                #     np.random.gamma((float(home_rb1.projection)/float(home_rb1.stdev))**2, (float(home_rb1.stdev)**2)/float(home_rb1.projection)),
                #     np.random.gamma((float(home_rb2.projection)/float(home_rb2.stdev))**2, (float(home_rb2.stdev)**2)/float(home_rb2.projection)),
                #     np.random.gamma((float(home_wr1.projection)/float(home_wr1.stdev))**2, (float(home_wr1.stdev)**2)/float(home_wr1.projection)),
                #     np.random.gamma((float(home_wr2.projection)/float(home_wr2.stdev))**2, (float(home_wr2.stdev)**2)/float(home_wr2.projection)),
                #     np.random.gamma((float(home_wr3.projection)/float(home_wr3.stdev))**2, (float(home_wr3.stdev)**2)/float(home_wr3.projection)),
                #     np.random.gamma((float(home_te.projection)/float(home_te.stdev))**2, (float(home_te.stdev)**2)/float(home_te.projection)),
                #     np.random.gamma((float(home_dst.projection)/float(home_dst.stdev))**2, (float(home_dst.stdev)**2)/float(home_dst.projection)),
                #     np.random.gamma((float(away_qb.projection)/float(away_qb.stdev))**2, (float(away_qb.stdev)**2)/float(away_qb.projection)),
                #     np.random.gamma((float(away_rb1.projection)/float(away_rb1.stdev))**2, (float(away_rb1.stdev)**2)/float(away_rb1.projection)),
                #     np.random.gamma((float(away_rb2.projection)/float(away_rb2.stdev))**2, (float(away_rb2.stdev)**2)/float(away_rb2.projection)),
                #     np.random.gamma((float(away_wr1.projection)/float(away_wr1.stdev))**2, (float(away_wr1.stdev)**2)/float(away_wr1.projection)),
                #     np.random.gamma((float(away_wr2.projection)/float(away_wr2.stdev))**2, (float(away_wr2.stdev)**2)/float(away_wr2.projection)),
                #     np.random.gamma((float(away_wr3.projection)/float(away_wr3.stdev))**2, (float(away_wr3.stdev)**2)/float(away_wr3.projection)),
                #     np.random.gamma((float(away_te.projection)/float(away_te.stdev))**2, (float(away_te.stdev)**2)/float(away_te.projection)),
                #     np.random.gamma((float(away_dst.projection)/float(away_dst.stdev))**2, (float(away_dst.stdev)**2)/float(away_dst.projection)),
                # ]

                x = [
                    scipy.stats.foldnorm.rvs(2.286320653446043, loc=0.009521750045927459, scale=0.43647078822917096, size=1)[0] * float(home_qb.projection),
                    scipy.stats.gengamma.rvs(0.8569512382187675, 1.7296589884149502, loc=0.1696436245041962, scale=1.0034840685805952, size=1)[0] * float(home_rb1.projection),
                    scipy.stats.gengamma.rvs(0.8569512382187675, 1.7296589884149502, loc=0.1696436245041962, scale=1.0034840685805952, size=1)[0] * float(home_rb2.projection),
                    scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(home_wr1.projection),
                    scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(home_wr2.projection),
                    scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(home_wr3.projection),
                    scipy.stats.beta.rvs(1.3211694111775993, 8.619168174695513, loc=0.05324597661516427, scale=7.141266442024949, size=1)[0] * float(home_te.projection),
                    scipy.stats.burr12.rvs(35.758034183278085, 0.4498053645571314, loc=-11.318659107435849, scale=11.704623152048967, size=1)[0] * float(home_dst.projection),
                    scipy.stats.foldnorm.rvs(2.286320653446043, loc=0.009521750045927459, scale=0.43647078822917096, size=1)[0] * float(away_qb.projection),
                    scipy.stats.gengamma.rvs(0.8569512382187675, 1.7296589884149502, loc=0.1696436245041962, scale=1.0034840685805952, size=1)[0] * float(away_rb1.projection),
                    scipy.stats.gengamma.rvs(0.8569512382187675, 1.7296589884149502, loc=0.1696436245041962, scale=1.0034840685805952, size=1)[0] * float(away_rb2.projection),
                    scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(away_wr1.projection),
                    scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(away_wr2.projection),
                    scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(away_wr3.projection),
                    scipy.stats.beta.rvs(1.3211694111775993, 8.619168174695513, loc=0.05324597661516427, scale=7.141266442024949, size=1)[0] * float(away_te.projection),
                    scipy.stats.burr12.rvs(35.758034183278085, 0.4498053645571314, loc=-11.318659107435849, scale=11.704623152048967, size=1)[0] * float(away_dst.projection),
                ]

                # x = [
                #     scipy.stats.skewnorm.rvs(1.4132959978590718, loc=float(home_qb.projection), scale=float(home_qb.stdev)),
                #     scipy.stats.gengamma.rvs(0.8569512382187675, 1.7296589884149502, loc=0.1696436245041962, scale=1.0034840685805952, size=1)[0] * float(home_rb1.projection),
                #     scipy.stats.gengamma.rvs(0.8569512382187675, 1.7296589884149502, loc=0.1696436245041962, scale=1.0034840685805952, size=1)[0] * float(home_rb2.projection),
                #     scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(home_wr1.projection),
                #     scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(home_wr2.projection),
                #     scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(home_wr3.projection),
                #     scipy.stats.beta.rvs(1.3211694111775993, 8.619168174695513, loc=0.05324597661516427, scale=7.141266442024949, size=1)[0] * float(home_te.projection),
                #     scipy.stats.burr12.rvs(35.758034183278085, 0.4498053645571314, loc=-11.318659107435849, scale=11.704623152048967, size=1)[0] * float(home_dst.projection),
                #     scipy.stats.skewnorm.rvs(1.4132959978590718, loc=float(away_qb.projection), scale=float(away_qb.stdev)),
                #     scipy.stats.gengamma.rvs(0.8569512382187675, 1.7296589884149502, loc=0.1696436245041962, scale=1.0034840685805952, size=1)[0] * float(away_rb1.projection),
                #     scipy.stats.gengamma.rvs(0.8569512382187675, 1.7296589884149502, loc=0.1696436245041962, scale=1.0034840685805952, size=1)[0] * float(away_rb2.projection),
                #     scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(away_wr1.projection),
                #     scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(away_wr2.projection),
                #     scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=1)[0] * float(away_wr3.projection),
                #     scipy.stats.beta.rvs(1.3211694111775993, 8.619168174695513, loc=0.05324597661516427, scale=7.141266442024949, size=1)[0] * float(away_te.projection),
                #     scipy.stats.burr12.rvs(35.758034183278085, 0.4498053645571314, loc=-11.318659107435849, scale=11.704623152048967, size=1)[0] * float(away_dst.projection),
                # ]

                y = np.dot(c, x)
                home_qb_scores.append(y[0])
                home_rb1_scores.append(y[1])
                home_rb2_scores.append(y[2])
                home_wr1_scores.append(y[3])
                home_wr2_scores.append(y[4])
                home_wr3_scores.append(y[5])
                home_te_scores.append(y[6])
                home_dst_scores.append(y[7])
                away_qb_scores.append(y[8])
                away_rb1_scores.append(y[9])
                away_rb2_scores.append(y[10])
                away_wr1_scores.append(y[11])
                away_wr2_scores.append(y[12])
                away_wr3_scores.append(y[13])
                away_te_scores.append(y[14])
                away_dst_scores.append(y[15])

                t.append(y.sum())

            print(f'{game}, Total = {game.game_total()}, Median FPTS = {np.median(t)}')

            df_scores = pd.DataFrame([
                home_qb_scores,
                home_rb1_scores,
                home_rb2_scores,
                home_wr1_scores,
                home_wr2_scores,
                home_wr3_scores,
                home_te_scores,
                home_dst_scores,
                away_qb_scores,
                away_rb1_scores,
                away_rb2_scores,
                away_wr1_scores,
                away_wr2_scores,
                away_wr3_scores,
                away_te_scores,
                away_dst_scores,
            ])

            df_scores.to_csv(f'data/{game.slate}-{game.game.away_team} @ {game.game.home_team}.csv')
        except:
            traceback.print_exc()