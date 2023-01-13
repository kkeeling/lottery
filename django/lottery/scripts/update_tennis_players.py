import datetime
import math
import numpy
import pandas
import sqlalchemy
import uuid

from random import random

from django.conf import settings
from django.db.models import Q, Sum

from tennis.models import Player, Alias

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

def run():
    user = settings.DATABASES['default']['USER']
    password = settings.DATABASES['default']['PASSWORD']
    database_name = settings.DATABASES['default']['NAME']
    database_url = 'postgresql://{user}:{password}@db:5432/{database_name}'.format(
        user=user,
        password=password,
        database_name=database_name,
    )

    engine = sqlalchemy.create_engine(database_url, echo=False)

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
    print(df_players)
        
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
    print(df_players)
        
    upsert_df(df=df_players, table_name='tennis_player', engine=engine)

