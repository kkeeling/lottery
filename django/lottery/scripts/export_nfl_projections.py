import numpy as np
import pandas as pd
import random
import requests
import socket   

from django.db.models import Prefetch, Q

from nfl import models


def run():
    slate_players = models.SlatePlayer.objects.filter(
        slate__week__slate_year=2021,
        slate__site='fanduel',
        slate__is_main_slate=True
    ).prefetch_related(
        Prefetch('raw_projections', queryset=models.SlatePlayerRawProjection.objects.filter(projection_site='4for4'), to_attr='four4four')
    ).prefetch_related(
        Prefetch('raw_projections', queryset=models.SlatePlayerRawProjection.objects.filter(projection_site='awesemo'), to_attr='awesemo')
    ).prefetch_related(
        Prefetch('raw_projections', queryset=models.SlatePlayerRawProjection.objects.filter(projection_site='etr'), to_attr='etr')
    ).prefetch_related(
        Prefetch('raw_projections', queryset=models.SlatePlayerRawProjection.objects.filter(projection_site='tda'), to_attr='tda')
    ).prefetch_related(
        Prefetch('raw_projections', queryset=models.SlatePlayerRawProjection.objects.filter(projection_site='rg'), to_attr='rg')
    ).prefetch_related(
        Prefetch('raw_projections', queryset=models.SlatePlayerRawProjection.objects.filter(projection_site='sabersim'), to_attr='sabersim')
    ).order_by('slate__week__num', 'site_pos', 'name')

    df = pd.DataFrame(data={
        'week': [s.slate.week.num for s in slate_players],
        'player': [s.name for s in slate_players],
        'pos': [s.site_pos for s in slate_players],
        '4for4': [s.four4four[0].projection if len(s.four4four) > 0 else None for s in slate_players],
        'etr': [s.etr[0].projection if len(s.etr) > 0 else None for s in slate_players],
        'awesemo': [s.awesemo[0].projection if len(s.awesemo) > 0 else None for s in slate_players],
        'tda': [s.tda[0].projection if len(s.tda) > 0 else None for s in slate_players],
        'rg': [s.rg[0].projection if len(s.rg) > 0 else None for s in slate_players],
        'sabersim': [s.sabersim[0].projection if len(s.sabersim) > 0 else None for s in slate_players],
        'actual': [s.fantasy_points for s in slate_players]
    })

    df.to_csv('data/2021_site_projections_fanduel.csv')