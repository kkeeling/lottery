import numpy as np
import pandas as pd
import sqlalchemy
import time

from django.conf import settings
from tennis import models


def run():
    models.WinRateLookup.objects.all().delete()

    df_lookup = pd.read_excel(
        'data/Odds Lookup Tennis.xlsx',
        sheet_name='Win Results'
    )

    start = time.time()
    user = settings.DATABASES['default']['USER']
    password = settings.DATABASES['default']['PASSWORD']
    database_name = settings.DATABASES['default']['NAME']
    database_url = 'postgresql://{user}:{password}@db:5432/{database_name}'.format(
        user=user,
        password=password,
        database_name=database_name,
    )
    engine = sqlalchemy.create_engine(database_url, echo=False)
    df_lookup.to_sql('tennis_winratelookup', engine, if_exists='append', index=False)
    print(f'Write win lookups to db took {time.time() - start}s')
