import datetime
import math
import numpy
import pandas
import sqlalchemy
import uuid

from random import random

from django.conf import settings
from django.db.models import Q, Sum

from tennis.models import Alias

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

    def find_player_id(player_name):
        alias = Alias.find_alias(player_name, 'pinnacle')
        
        if alias and alias.player:
            return alias.player.player_id
        return None

    url = 'https://5j7her7vt4.execute-api.us-east-1.amazonaws.com/dev/'
    df_pinn = pandas.read_csv(url)

    # get the matchups
    df_matchup = df_pinn.iloc[:,[1,2,3,4,6]]
    df_matchup['home_player_id'] = df_matchup['home_participant'].map(lambda x: find_player_id(x))
    df_matchup['away_player_id'] = df_matchup['away_participant'].map(lambda x: find_player_id(x))
    df_matchup['start_time'] = df_matchup['start_time'].map(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M'))
    df_matchup = df_matchup.set_index(df_matchup['id'])
    df_matchup.drop(['id'], axis=1, inplace=True)

    upsert_df(df=df_matchup, table_name='tennis_pinnaclematch', engine=engine)

    # get the odds
    df_odds = df_pinn.iloc[:, [1,7,8,9,10,11,12,13,14,15,16]]
    df_odds['create_at'] = datetime.datetime.now()
    df_odds['match_id'] = df_odds['id']
    df_odds['home_price'] = df_odds['home_moneyline']
    df_odds['away_price'] = df_odds['away_moneyline']
    df_odds['home_spread'] = df_odds['home_spread_games']
    df_odds['away_spread'] = df_odds['away_spread_games']
    df_odds.drop([
        'id',
        'home_spread_sets',
        'away_spread_sets',
        'over_sets',
        'under_sets',
        'home_moneyline',
        'away_moneyline',
        'home_spread_games',
        'away_spread_games',
        'over_games',
        'under_games',
    ], axis=1, inplace=True)

    df_odds.to_sql('tennis_pinnaclematchodds', engine, if_exists='append', index=False, chunksize=1000)
