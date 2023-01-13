import csv
import datetime
import logging
import json
import math
import numpy
import os
import pandas
import requests
import scipy
import sqlalchemy
import sys
import time
import traceback
import uuid

from random import random

from celery import shared_task, chord, group, chain
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages.api import success
from django.db.models.aggregates import Count, Sum
from django.db.models import Q, F
from django.db import transaction

from configuration.models import BackgroundTask

from fanduel import models as fanduel_models
from yahoo import models as yahoo_models

from . import models
from . import optimize

from lottery.celery import app

logger = logging.getLogger(__name__)

ATP_MATCH_FILES = [
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1968.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1969.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1970.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1971.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1972.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1973.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1974.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1975.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1976.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1977.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1978.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1979.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1980.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1981.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1982.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1983.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1984.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1985.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1986.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1987.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1988.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1989.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1990.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1991.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1992.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1993.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1994.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1995.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1996.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1997.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1998.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1999.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2000.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2001.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2002.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2003.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2004.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2005.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2006.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2007.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2008.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2009.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2010.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2011.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2012.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2013.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2014.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2015.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2016.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2017.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2018.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2019.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2020.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2021.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2022.csv'
]

WTA_MATCH_FILES = [
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1968.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1969.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1970.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1971.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1972.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1973.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1974.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1975.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1976.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1977.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1978.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1979.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1980.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1981.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1982.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1983.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1984.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1985.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1986.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1987.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1988.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1989.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1990.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1991.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1992.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1993.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1994.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1995.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1996.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1997.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1998.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1999.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2000.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2001.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2002.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2003.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2004.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2005.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2006.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2007.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2008.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2009.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2010.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2011.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2012.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2013.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2014.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2015.csv',
    # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2016.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2017.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2018.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2019.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2020.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2021.csv',
    'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2022.csv'
]

user = settings.DATABASES['default']['USER']
password = settings.DATABASES['default']['PASSWORD']
database_name = settings.DATABASES['default']['NAME']
database_url = 'postgresql://{user}:{password}@db:5432/{database_name}'.format(
    user=user,
    password=password,
    database_name=database_name,
)

engine = sqlalchemy.create_engine(database_url, echo=False)


# ensures that tasks only run once at most!
@contextmanager
def lock_task(key, timeout=None):
    has_lock = False
    client = app.broker_connection().channel().client
    lock = client.lock(key, timeout=timeout)
    try:
        has_lock = lock.acquire(blocking=False)
        yield has_lock
    finally:
        if has_lock:
            lock.release()


def upsert_df(df: pandas.DataFrame, table_name: str, engine: sqlalchemy.engine.Engine):
    """Implements the equivalent of pandas.DataFrame.to_sql(..., if_exists='update')
    (which does not exist). Creates or updates the db records based on the
    dataframe records.
    Conflicts to determine update are based on the dataframes index.
    This will set primary keys on the table equal to the index names
    1. Create a temp table from the dataframe
    2. Insert/update from temp table into table_name
    Returns: True if successful
    """

    # If the table does not exist, we should just use to_sql to create it
    if not engine.execute(
        f"""SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE  table_schema = 'public'
            AND    table_name   = '{table_name}');
            """
    ).first()[0]:
        df.to_sql(table_name, engine)
        return True

    # If it already exists...
    temp_table_name = f"temp_{uuid.uuid4().hex[:6]}"
    df.to_sql(temp_table_name, engine, index=True)

    index = list(df.index.names)
    index_sql_txt = ", ".join([f'"{i}"' for i in index])
    columns = list(df.columns)
    headers = index + columns
    headers_sql_txt = ", ".join(
        [f'"{i}"' for i in headers]
    )  # index1, index2, ..., column 1, col2, ...

    # col1 = exluded.col1, col2=excluded.col2
    update_column_stmt = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in columns])

    # For the ON CONFLICT clause, postgres requires that the columns have unique constraint
    query_pk = f"""
    ALTER TABLE "{table_name}" ADD CONSTRAINT {table_name}_unique_constraint_for_upsert UNIQUE ({index_sql_txt});
    """
    try:
        engine.execute(query_pk)
    except Exception as e:
        # relation "unique_constraint_for_upsert" already exists
        if not 'unique_constraint_for_upsert" already exists' in e.args[0]:
            raise e

    # Compose and execute upsert query
    query_upsert = f"""
    INSERT INTO "{table_name}" ({headers_sql_txt}) 
    SELECT {headers_sql_txt} FROM "{temp_table_name}"
    ON CONFLICT ({index_sql_txt}) DO UPDATE 
    SET {update_column_stmt};
    """
    engine.execute(query_upsert)
    engine.execute(f'DROP TABLE "{temp_table_name}"')

    return True


@shared_task
def update_player_list_from_ta():
    atp_url = 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_players.csv'
    wta_url = 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_players.csv'

    # ATP
    df_players = pandas.read_csv(atp_url)

    df_players['first_name'] = df_players['name_first']
    df_players['last_name'] = df_players['name_last']
    df_players['tour'] = 'atp'
    df_players['player_id'] = df_players['player_id'].map(lambda x: f'atp-{x}')
    df_players['country'] = df_players['ioc']
    df_players = df_players.set_index(df_players['player_id'])
    df_players = df_players.drop([
        'name_first',
        'name_last',
        'ioc',
        'height',
        'dob',
        'wikidata_id',
        'player_id'
    ], axis=1)
        
    upsert_df(df=df_players, table_name='tennis_player', engine=engine)

    # WTA
    df_players = pandas.read_csv(wta_url)

    df_players['first_name'] = df_players['name_first']
    df_players['last_name'] = df_players['name_last']
    df_players['tour'] = 'wta'
    df_players['player_id'] = df_players['player_id'].map(lambda x: f'wta-{x}')
    df_players['country'] = df_players['ioc']
    df_players = df_players.set_index(df_players['player_id'])
    df_players = df_players.drop([
        'name_first',
        'name_last',
        'ioc',
        'height',
        'dob',
        'wikidata_id',
        'player_id'
    ], axis=1)
        
    upsert_df(df=df_players, table_name='tennis_player', engine=engine)


@shared_task
def update_matches_from_ta():
    ATP_MATCH_FILES = [
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1968.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1969.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1970.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1971.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1972.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1973.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1974.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1975.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1976.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1977.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1978.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1979.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1980.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1981.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1982.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1983.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1984.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1985.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1986.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1987.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1988.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1989.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1990.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1991.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1992.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1993.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1994.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1995.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1996.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1997.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1998.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_1999.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2000.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2001.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2002.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2003.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2004.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2005.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2006.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2007.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2008.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2009.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2010.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2011.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2012.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2013.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2014.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2015.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2016.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2017.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2018.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2019.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2020.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2021.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2022.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2023.csv'
    ]

    WTA_MATCH_FILES = [
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1968.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1969.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1970.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1971.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1972.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1973.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1974.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1975.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1976.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1977.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1978.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1979.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1980.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1981.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1982.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1983.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1984.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1985.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1986.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1987.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1988.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1989.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1990.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1991.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1992.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1993.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1994.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1995.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1996.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1997.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1998.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_1999.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2000.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2001.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2002.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2003.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2004.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2005.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2006.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2007.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2008.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2009.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2010.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2011.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2012.csv',
        # 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2013.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2014.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2015.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2016.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2017.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2018.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2019.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2020.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2021.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2022.csv',
        'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2023.csv'
    ]

    models.Match.objects.all().delete()

    # ATP
    for m in ATP_MATCH_FILES:
        df_matches = pandas.read_csv(m)
        df_matches['winner_id'] = df_matches['winner_id'].map(lambda x: f'atp-{x}')
        df_matches['loser_id'] = df_matches['loser_id'].map(lambda x: f'atp-{x}')
        df_matches['tourney_date'] = df_matches['tourney_date'].map(lambda x: datetime.datetime.strptime(str(x), '%Y%m%d'))
            
        df_matches.to_sql('tennis_match', engine, if_exists='append', index=False, chunksize=1000)

    # WTA
    for m in WTA_MATCH_FILES:
        df_matches = pandas.read_csv(m)
        df_matches['winner_id'] = df_matches['winner_id'].map(lambda x: f'wta-{x}')
        df_matches['loser_id'] = df_matches['loser_id'].map(lambda x: f'wta-{x}')
        df_matches['tourney_date'] = df_matches['tourney_date'].map(lambda x: datetime.datetime.strptime(str(x), '%Y%m%d'))
            
        df_matches.to_sql('tennis_match', engine, if_exists='append', index=False, chunksize=1000)


@shared_task
def get_pinn_odds(task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        update_time = datetime.datetime.now()
        matchup_url = 'https://guest.api.arcadia.pinnacle.com/0.1/sports/33/matchups'
        odds_url = 'https://guest.api.arcadia.pinnacle.com/0.1/sports/33/markets/straight?primaryOnly=false'
        headers = {
            'authority': 'guest.api.arcadia.pinnacle.com',
            'pragma': 'no-cache',
            'cache-control': 'no-cache',
            'accept': 'application/json',
            'x-device-uuid': '00f06d96-7d7dd505-45d4f32f-23672660',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36',
            'x-api-key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R',
            'content-type': 'application/json',
            'sec-gpc': '1',
            'origin': 'https://www.pinnacle.com',
            'sec-fetch-site': 'same-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://www.pinnacle.com/',
            'accept-language': 'en-US,en;q=0.9',
        }        
        response = requests.get(matchup_url, headers=headers)
        
        matchups = response.json()
        for matchup in matchups:
            if matchup.get('parent') == None and 'special' not in matchup:
                try:
                    match = models.PinnacleMatch.objects.get(id=matchup.get('id'))
                except models.PinnacleMatch.DoesNotExist:
                    match = models.PinnacleMatch.objects.create(
                        id=matchup.get('id'),
                        event=matchup.get('league').get('name'),
                        home_participant=matchup.get('participants')[0].get('name'),
                        away_participant=matchup.get('participants')[1].get('name'),
                        start_time=datetime.datetime.strptime(matchup.get('startTime'), '%Y-%m-%dT%H:%M:%SZ')
                    )

        response = requests.get(odds_url, headers=headers)
        odds_list = response.json()
        for odds in odds_list:
            if odds.get('type') == 'moneyline' and odds.get('period') == 0:
                try:
                    match = models.PinnacleMatch.objects.get(id=odds.get('matchupId'))
                    (pinnacle_odds, _) = models.PinnacleMatchOdds.objects.get_or_create(
                        match=match,
                        create_at=update_time
                    )
                    pinnacle_odds.home_price=odds.get('prices')[0].get('price')
                    pinnacle_odds.away_price=odds.get('prices')[1].get('price')
                    pinnacle_odds.save()
                except models.PinnacleMatch.DoesNotExist:
                    pass
            elif odds.get('type') == 'spread' and odds.get('period') == 0:
                try:
                    match = models.PinnacleMatch.objects.get(id=odds.get('matchupId'))
                    (pinnacle_odds, _) = models.PinnacleMatchOdds.objects.get_or_create(
                        match=match,
                        create_at=update_time
                    )
                    if pinnacle_odds.home_spread == 0.0:
                        pinnacle_odds.home_spread=odds.get('prices')[0].get('points')
                        pinnacle_odds.away_spread=odds.get('prices')[1].get('points')
                        pinnacle_odds.save()
                except models.PinnacleMatch.DoesNotExist:
                    pass

        task.status = 'success'
        task.content = 'Pinnacle odds updated.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem finding matches for slate: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def find_slate_matches(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        slate.find_matches()

        task.status = 'success'
        task.content = f'{slate.matches.all().count()} matches found'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem finding matches for slate: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def process_slate_players(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        
        with open(slate.salaries.path, mode='r') as salaries_file:
            csv_reader = csv.DictReader(salaries_file)

            success_count = 0
            missing_players = []

            for row in csv_reader:
                if slate.site == 'draftkings':
                    player_id = row['ID']
                    player_name = row['Name']
                    player_salary = int(row['Salary'])
                else:
                    raise Exception(f'{slate.site} is not supported yet.')

                alias = models.Alias.find_alias(player_name, slate.site)
                
                if alias is not None:
                    try:
                        slate_player = models.SlatePlayer.objects.get(
                            slate=slate,
                            slate_player_id=player_id
                        )
                    except models.SlatePlayer.DoesNotExist:
                        slate_player = models.SlatePlayer(
                            slate=slate,
                            slate_player_id=player_id
                        )

                    slate_player.name = alias.get_alias(slate.site)
                    slate_player.salary = player_salary
                    slate_player.player = alias.player
                    slate_player.save()

                    success_count += 1
                else:
                    missing_players.append(player_name)

        task.status = 'success'
        task.content = '{} players have been successfully added to {}.'.format(success_count, str(slate)) if len(missing_players) == 0 else '{} players have been successfully added to {}. {} players could not be identified.'.format(success_count, str(slate), len(missing_players))
        task.link = '/admin/tennis/missingalias/' if len(missing_players) > 0 else None
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem processing slate players: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def simulate_match(match_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        slate_match = models.SlateMatch.objects.get(id=match_id)
        favorite, odds = slate_match.match.favorite
        if odds > 0:
            fav_implied_win_pct = 100/(100+odds)
        else:
            fav_implied_win_pct = -odds/(-odds+100)

        fav_prob_lookup = models.WinRateLookup.objects.get(implied_odds=round(fav_implied_win_pct, 2))
        dog_prob_lookup = models.WinRateLookup.objects.get(implied_odds=round(1.0 - fav_implied_win_pct, 2))

        if slate_match.tour == 'wta':
            fav_prob = fav_prob_lookup.wta_odds
        else:
            if slate_match.best_of == 3:
                fav_prob = fav_prob_lookup.atp3_odds
            else:
                fav_prob = fav_prob_lookup.atp5_odds

        w_vals = numpy.random(1, size=(1000))

        task.status = 'success'
        task.content = f'Simulation of {slate_match} complete.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem simulating {slate_match}: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def calculate_target_scores(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        all_scores = numpy.array(
            [
                p.sim_scores for p in models.SlatePlayerProjection.objects.filter(
                    slate_player__slate=slate
                )
            ]
        )

        n = 8
        df_scores = pandas.DataFrame(all_scores, dtype=float)
        top_scores = df_scores.max(axis = 0)
        target_scores = [df_scores[c].nlargest(n).values[n-1] for c in df_scores.columns]

        slate.top_score = numpy.mean(top_scores.to_list())
        slate.target_score = numpy.mean(target_scores)
        slate.save()
        
        task.status = 'success'
        task.content = f'Target scores calculated'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating target scores: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def calculate_slate_structure(slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        chord(
            [find_optimal_for_sim.s(slate.id, i) for i in range(0, 10000)],
            complile_sim_optimals.s(slate_id, task_id)
        )()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating slate structure: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def find_optimal_for_sim(slate_id, sim_iteration):
    slate = models.Slate.objects.get(id=slate_id)
    optimal = optimize.find_optimal_from_sims(
        slate.site,
        models.SlatePlayerProjection.objects.filter(slate_player__slate=slate),
        sim_iteration=sim_iteration
    )[0]
    return [p.id for p in optimal.players]


@shared_task
def complile_sim_optimals(results, slate_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        slate = models.Slate.objects.get(id=slate_id)
        df_opt = pandas.DataFrame(results)
        
        # s_0 = df_opt[0].value_counts()
        # s_1 = df_opt[1].value_counts()
        # s_2 = df_opt[2].value_counts()
        # s_3 = df_opt[3].value_counts()
        # s_4 = df_opt[4].value_counts()
        # s_5 = df_opt[5].value_counts()
        
        # print(s_0)
        # print(s_1)
        # print(s_2)
        # print(s_3)
        # print(s_4)
        # print(s_5)

        for projection in models.SlatePlayerProjection.objects.filter(slate_player__slate=slate):
            count = 0
            try:
                count += df_opt[0].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[1].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[2].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[3].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[4].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            try:
                count += df_opt[5].value_counts()[projection.slate_player.slate_player_id]
            except KeyError:
                pass

            print(f'{projection.slate_player}: {count}')
            projection.optimal_exposure = count / 10000
            projection.save()
                
        task.status = 'success'
        task.content = f'Slate structure calculated'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating slate structure: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def build_lineups(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)
        lineups = optimize.optimize(build.slate.site, models.SlatePlayerProjection.objects.filter(slate_player__slate=build.slate), build.configuration, build.total_lineups * build.configuration.lineup_multiplier)

        for lineup in lineups:
            if build.slate.site == 'draftkings':
                lineup = models.SlateBuildLineup.objects.create(
                    build=build,
                    player_1=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[0].id, slate_player__slate=build.slate),
                    player_2=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[1].id, slate_player__slate=build.slate),
                    player_3=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[2].id, slate_player__slate=build.slate),
                    player_4=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[3].id, slate_player__slate=build.slate),
                    player_5=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[4].id, slate_player__slate=build.slate),
                    player_6=models.SlatePlayerProjection.objects.get(slate_player__slate_player_id=lineup.players[5].id, slate_player__slate=build.slate),
                    total_salary=lineup.salary_costs
                )
                # lineup = models.SlateBuildLineup.objects.create(
                #     build=build,
                #     player_1=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[0].name, slate_player__slate=build.slate),
                #     player_2=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[1].name, slate_player__slate=build.slate),
                #     player_3=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[2].name, slate_player__slate=build.slate),
                #     player_4=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[3].name, slate_player__slate=build.slate),
                #     player_5=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[4].name, slate_player__slate=build.slate),
                #     player_6=models.SlatePlayerProjection.objects.get(slate_player__name=lineup.players[5].name, slate_player__slate=build.slate),
                #     total_salary=lineup.spent()
                # )
                lineup.implied_win_pct = lineup.player_1.implied_win_pct * lineup.player_2.implied_win_pct * lineup.player_3.implied_win_pct * lineup.player_4.implied_win_pct * lineup.player_5.implied_win_pct * lineup.player_6.implied_win_pct
                lineup.save()

                lineup.simulate()
            else:
                raise Exception(f'{build.slate.site} is not available for building yet.')
        
        task.status = 'success'
        task.content = f'{build.lineups.all().count()} lineups created.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem building lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def clean_lineups(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)

        ordered_lineups = build.lineups.all().order_by(f'-{build.configuration.clean_lineups_by}')
        ordered_lineups.filter(id__in=ordered_lineups.values_list('pk', flat=True)[int(build.total_lineups):]).delete()
        
        task.status = 'success'
        task.content = 'Lineups cleaned.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem cleaning lineups: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def calculate_exposures(build_id, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)

        # Task implementation goes here
        build = models.SlateBuild.objects.get(id=build_id)
        players = models.SlatePlayerProjection.objects.filter(
            slate_player__slate=build.slate
        )

        for player in players:
            exposure, _ = models.SlateBuildPlayerExposure.objects.get_or_create(
                build=build,
                player=player
            )
            exposure.exposure = build.lineups.filter(
                Q(
                    Q(player_1=player) | 
                    Q(player_2=player) | 
                    Q(player_3=player) | 
                    Q(player_4=player) | 
                    Q(player_5=player) | 
                    Q(player_6=player)
                )
            ).count() / build.lineups.all().count()
            exposure.save()
        
        task.status = 'success'
        task.content = 'Exposures calculated.'
        task.save()
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem calculating exposures: {e}'
            task.save()

        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))


@shared_task
def export_build_for_upload(build_id, result_path, result_url, task_id):
    task = None

    try:
        try:
            task = BackgroundTask.objects.get(id=task_id)
        except BackgroundTask.DoesNotExist:
            time.sleep(0.2)
            task = BackgroundTask.objects.get(id=task_id)
        build = models.SlateBuild.objects.get(pk=build_id)

        with open(result_path, 'w') as temp_csv:
            build_writer = csv.writer(temp_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            build_writer.writerow(['P', 'P', 'P', 'P', 'P', 'P'])

            lineups = build.lineups.all()

            for lineup in lineups:
                if build.slate.site == 'draftkings':
                    row = [
                        f'{lineup.player_1.name} ({lineup.player_1.slate_player.slate_player_id})',
                        f'{lineup.player_2.name} ({lineup.player_2.slate_player.slate_player_id})',
                        f'{lineup.player_3.name} ({lineup.player_3.slate_player.slate_player_id})',
                        f'{lineup.player_4.name} ({lineup.player_4.slate_player.slate_player_id})',
                        f'{lineup.player_5.name} ({lineup.player_5.slate_player.slate_player_id})',
                        f'{lineup.player_6.name} ({lineup.player_6.slate_player.slate_player_id})'
                    ]
                else:
                    raise Exception('{} is not a supported dfs site.'.format(build.slate.site)) 

                build_writer.writerow(row)

        task.status = 'download'
        task.content = result_url
        task.save()
        
    except Exception as e:
        if task is not None:
            task.status = 'error'
            task.content = f'There was a problem generating your export {e}'
            task.save()
        logger.error("Unexpected error: " + str(sys.exc_info()[0]))
        logger.exception("error info: " + str(sys.exc_info()[1]) + "\n" + str(sys.exc_info()[2]))

