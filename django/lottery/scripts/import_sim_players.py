import numpy as np
import pandas as pd
import random
import requests
import socket   

from nfl_sims import models


def run():
    models.Player.objects.all().delete()

    df_players = pd.read_csv('data/Justin Freeman - nfl_players.csv')
    player_instances = [
        models.Player(
            id=record['id'],
            draftkings_name=record['draftkings_name'],
            fanduel_name=record['fanduel_name'],
            yahoo_name=record['yahoo_name'],
            draftkings_player_id=record['draftkings_player_id'],
            fanduel_player_id=record['fanduel_player_id'],
            yahoo_player_id=record['yahoo_player_id'],
        ) for record in df_players.to_dict('records')
    ]
    
    models.Player.objects.bulk_create(player_instances)

    print(f'{models.Player.objects.all().count()} players created.')