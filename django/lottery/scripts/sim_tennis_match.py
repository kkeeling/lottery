import datetime
import numpy
import pandas
import math
import time

from random import random

from django.db.models import Q, Sum

from tennis import models


def run():
    slate = models.Slate.objects.get(id=35)
    match_id = slate.matches.all()[0].id

    start = time.time()
    slate_match = models.SlateMatch.objects.get(id=match_id)
    favorite, fav_odds = slate_match.match.favorite
    if fav_odds > 0:
        fav_implied_win_pct = 100/(100+fav_odds)
    else:
        fav_implied_win_pct = -fav_odds/(-fav_odds+100)

    underdog, dog_odds = slate_match.match.underdog
    if dog_odds > 0:
        dog_implied_win_pct = 100/(100+dog_odds)
    else:
        dog_implied_win_pct = -dog_odds/(-dog_odds+100)

    fav_prob_lookup = models.WinRateLookup.objects.get(implied_odds=round(fav_implied_win_pct, 2))
    dog_prob_lookup = models.WinRateLookup.objects.get(implied_odds=round(dog_implied_win_pct, 2))

    if slate_match.tour == 'wta':
        fav_prob = fav_prob_lookup.wta_odds
    else:
        if slate_match.best_of == 3:
            fav_prob = fav_prob_lookup.atp3_odds
        else:
            fav_prob = fav_prob_lookup.atp5_odds

    w_vals = numpy.random.random_sample((1000,))

    df_sim = pandas.DataFrame(w_vals, columns=['pval'])
    df_sim['winner'] = favorite if df_sim['pval'] <= fav_prob else underdog
    
    print(f'  Simulation took took {time.time() - start}s')
    print(df_sim)
