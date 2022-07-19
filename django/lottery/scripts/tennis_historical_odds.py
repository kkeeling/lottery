import math
import requests

import numpy as np
import pandas as pd

from tennis import models

def get_name(x):
    parts = x.split(" ")

    s = f'{parts[-1]}'
    z = 1

    if parts[-2] == 'Van' or parts[-2] == 'De':
        s = f'{parts[-2]} {parts[-1]}'
        z = 2

    for index, p in enumerate(parts):
        if index < len(parts) - z:
            s += f' {p[0]}.'
    # s += '.'

    return s

def calc_american_odds(x):
    if math.isnan(x): 
        return None
    if x >= 2:
        return (x - 1) * 100
    return round(-100/(x-1))

def run():
    years = [
        '2022',
        '2021',
        '2020',
        '2019',
        '2018',
    ]
    atp_frames = []
    wta_frames = []

    for year in years:
        url = f'http://www.tennis-data.co.uk/{year}/{year}.xlsx'
        r = requests.get(url)
        open('temp.xls', 'wb').write(r.content)
        df_odds = pd.read_excel('temp.xls', usecols=[
            'Date', 
            'Winner', 
            'Loser', 
            'WRank',
            'LRank',
            'W1', 
            'L1', 
            'W2',
            'L2',
            'W3',
            'L3',
            'W4',
            'L4',
            'W5',
            'L5',
            'Wsets',
            'Lsets',
            'PSW',
            'PSL'
        ])
        df_odds['PSW'] = df_odds['PSW'].map(lambda x: calc_american_odds(x))
        df_odds['PSL'] = df_odds['PSL'].map(lambda x: calc_american_odds(x))
        df_odds['id'] = df_odds['Date'].map(lambda x: x.strftime('%m/%Y')) + '-' + df_odds['WRank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_odds['Winner'] + '-' + df_odds['LRank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_odds['Loser']
        # df_odds.set_index('id', inplace=True)
        df_odds.drop(columns=[
            'Date', 
            'Winner', 
            'Loser',
            'WRank',
            'LRank'
        ], axis=1, inplace=True)

        matches = models.Match.objects.filter(
            tourney_date__year=year,
            winner__tour='atp',
        ).exclude(
            w_bpSaved__isnull=True
        )
        df_matches = pd.DataFrame.from_records(matches.values(
            'tourney_id',
            'tourney_name',
            'surface',
            'tourney_date',
            'winner_name',
            'loser_name',
            'winner_rank',
            'loser_rank',
            'w_bpSaved',
            'w_bpFaced',
            'l_bpSaved',
            'l_bpFaced',
        ))

        df_matches['winner'] = df_matches['winner_name'].map(lambda x: get_name(x))
        df_matches['loser'] = df_matches['loser_name'].map(lambda x: get_name(x))
        df_matches['wBreaks'] = df_matches['w_bpFaced'] - df_matches['w_bpSaved']
        df_matches['lBreaks'] = df_matches['l_bpFaced'] - df_matches['l_bpSaved']
        df_matches['id'] = df_matches['tourney_date'].map(lambda x: x.strftime('%m/%Y')) + '-' + df_matches['winner_rank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_matches['winner'] + '-' + df_matches['loser_rank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_matches['loser']
        # df_matches.set_index('id', inplace=True)
        df_matches.drop(columns=[
            'w_bpSaved', 
            'w_bpFaced', 
            'l_bpSaved', 
            'l_bpFaced',
            'winner_rank',
            'loser_rank',
            'winner_name',
            'loser_name'
        ], axis=1, inplace=True)

        df_merged = df_matches.merge(df_odds, how='inner', on='id')
        df_merged['wGames'] = df_merged['W1'] + df_merged['W2'] + df_merged['W3'].map(lambda x: 0 if math.isnan(x) else x) + df_merged['W4'].map(lambda x: 0 if math.isnan(x) else x) + df_merged['W5'].map(lambda x: 0 if math.isnan(x) else x)
        df_merged['lGames'] = df_merged['L1'] + df_merged['L2'] + df_merged['L3'].map(lambda x: 0 if math.isnan(x) else x) + df_merged['L4'].map(lambda x: 0 if math.isnan(x) else x) + df_merged['L5'].map(lambda x: 0 if math.isnan(x) else x)


        # with pd.ExcelWriter('data/test.xlsx') as writer:
        #     pd.concat([df_merged]).to_excel(writer, sheet_name='matches')

        break
        # atp_frames.append(df_odds)

    # for year in years:
    #     url = f'http://www.tennis-data.co.uk/{year}w/{year}.xlsx'
    #     r = requests.get(url)
    #     open('temp.xls', 'wb').write(r.content)
    #     df_odds = pd.read_excel('temp.xls')
    #     wta_frames.append(df_odds)

