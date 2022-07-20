import itertools
import time

import numpy
import pandas

from nascar import models

def run():
    build = models.SlateBuild.objects.get(id=1)
    start = time.time()
    slate_lineups = build.slate.possible_lineups.filter(total_salary__gte=49000).values_list('id', flat=True)
    field_lineups = build.field_lineups.all().values_list('id', flat=True)
    print(f'Getting lists took {time.time() - start}s. There are {slate_lineups.count()} possible lineups.')

    start = time.time()
    matchups  = list(itertools.product(slate_lineups, field_lineups))
    print(f'Matchups took {time.time() - start}s. There are {len(matchups)} matchups.')
