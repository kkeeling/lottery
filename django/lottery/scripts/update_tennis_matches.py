import datetime
import math
import numpy
import pandas
import sqlalchemy
import uuid

from random import random

from django.conf import settings
from django.db.models import Q, Sum

from tennis.models import Match

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

def get_name(x):
    parts = x.split(" ")

    s = f'{parts[-1]}'
    z = 1

    if parts[-2] == 'Van' or parts[-2] == 'De' or parts[-2] == 'Auger' or parts[-2] == 'Bautista' or parts[-2] == 'Carreno':
        s = f'{parts[-2]} {parts[-1]}'
        z = 2

    for index, p in enumerate(parts):
        if index < len(parts) - z:
            s += f' {p[0]}.'
    # s += '.'

    return s


def calc_american_odds(x):
    if x == 1:
        x = 1.0001
        
    if math.isnan(x): 
        return None
    if x >= 2:
        return (x - 1) * 100
    return round(-100/(x-1))


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

    ATP_ODDS_FILES = [
        'http://www.tennis-data.co.uk/2014/2014.xlsx',
        'http://www.tennis-data.co.uk/2015/2015.xlsx',
        'http://www.tennis-data.co.uk/2016/2016.xlsx',
        'http://www.tennis-data.co.uk/2017/2017.xlsx',
        'http://www.tennis-data.co.uk/2018/2018.xlsx',
        'http://www.tennis-data.co.uk/2019/2019.xlsx',
        'http://www.tennis-data.co.uk/2020/2020.xlsx',
        'http://www.tennis-data.co.uk/2021/2021.xlsx',
        'http://www.tennis-data.co.uk/2022/2022.xlsx',
        'http://www.tennis-data.co.uk/2023/2023.xlsx'
    ]

    WTA_ODDS_FILES = [
        'http://www.tennis-data.co.uk/2014w/2014.xlsx',
        'http://www.tennis-data.co.uk/2015w/2015.xlsx',
        'http://www.tennis-data.co.uk/2016w/2016.xlsx',
        'http://www.tennis-data.co.uk/2017w/2017.xlsx',
        'http://www.tennis-data.co.uk/2018w/2018.xlsx',
        'http://www.tennis-data.co.uk/2019w/2019.xlsx',
        'http://www.tennis-data.co.uk/2020w/2020.xlsx',
        'http://www.tennis-data.co.uk/2021w/2021.xlsx',
        'http://www.tennis-data.co.uk/2022w/2022.xlsx',
        'http://www.tennis-data.co.uk/2023w/2023.xlsx'
    ]

    Match.objects.all().delete()

    # ATP
    for index, m in enumerate(ATP_MATCH_FILES):
        print(m)
        df_matches = pandas.read_csv(m)
        df_matches['winner_id'] = df_matches['winner_id'].map(lambda x: f'atp-{x}')
        df_matches['loser_id'] = df_matches['loser_id'].map(lambda x: f'atp-{x}')
        df_matches['tourney_date'] = df_matches['tourney_date'].map(lambda x: datetime.datetime.strptime(str(x), '%Y%m%d'))
        df_matches['winner'] = df_matches['winner_name'].map(lambda x: get_name(x))
        df_matches['loser'] = df_matches['loser_name'].map(lambda x: get_name(x))
        df_matches['id'] = df_matches['tourney_date'].map(lambda x: x.strftime('%m/%Y')) + '-' + df_matches['winner_rank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_matches['winner'] + '-' + df_matches['loser_rank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_matches['loser']

        print(ATP_ODDS_FILES[index])
        df_odds = pandas.read_excel(ATP_ODDS_FILES[index])
        df_odds['winner_odds'] = df_odds['PSW'].map(lambda x: calc_american_odds(x))
        df_odds['loser_odds'] = df_odds['PSL'].map(lambda x: calc_american_odds(x))
        df_odds['id'] = df_odds['Date'].map(lambda x: x.strftime('%m/%Y')) + '-' + df_odds['WRank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_odds['Winner'] + '-' + df_odds['LRank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_odds['Loser']
        df_odds.drop(columns=[
            'ATP',
            'Location',
            'Tournament',
            'Date', 
            'Series',
            'Court',
            'Surface',
            'Round',
            'Best of',
            'Winner', 
            'Loser',
            'WRank',
            'LRank',
            'WPts',
            'LPts',
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
            'Comment',
            'B365W',
            'B365L',
            'PSW',
            'PSL',
            'MaxW',
            'MaxL',
            'AvgW',
            'AvgL'            
        ], axis=1, inplace=True)

        if 'EXW' in df_odds.columns:
            df_odds.drop(['EXW'], axis=1, inplace=True)

        if 'EXL' in df_odds.columns:
            df_odds.drop(['EXL'], axis=1, inplace=True)

        if 'LBW' in df_odds.columns:
            df_odds.drop(['LBW'], axis=1, inplace=True)

        if 'LBL' in df_odds.columns:
            df_odds.drop(['LBL'], axis=1, inplace=True)

        if 'SJW' in df_odds.columns:
            df_odds.drop(['SJW'], axis=1, inplace=True)

        if 'SJL' in df_odds.columns:
            df_odds.drop(['SJL'], axis=1, inplace=True)
        # print(df_odds)

        df_merged = df_matches.merge(df_odds, how='inner', on='id')
        df_merged.drop([
            'winner',
            'loser',
            'id'
        ], axis=1, inplace=True)
        # print(df_merged)

        df_merged.to_sql('tennis_match', engine, if_exists='append', index=False, chunksize=1000)
    
    # WTA
    for index, m in enumerate(WTA_MATCH_FILES):
        print(m)
        df_matches = pandas.read_csv(m)
        df_matches['winner_id'] = df_matches['winner_id'].map(lambda x: f'wta-{x}')
        df_matches['loser_id'] = df_matches['loser_id'].map(lambda x: f'wta-{x}')
        df_matches['tourney_date'] = df_matches['tourney_date'].map(lambda x: datetime.datetime.strptime(str(x), '%Y%m%d'))
        df_matches['winner'] = df_matches['winner_name'].map(lambda x: get_name(x))
        df_matches['loser'] = df_matches['loser_name'].map(lambda x: get_name(x))
        df_matches['id'] = df_matches['tourney_date'].map(lambda x: x.strftime('%m/%Y')) + '-' + df_matches['winner_rank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_matches['winner'] + '-' + df_matches['loser_rank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_matches['loser']

        print(WTA_ODDS_FILES[index])
        df_odds = pandas.read_excel(WTA_ODDS_FILES[index])
        df_odds['winner_odds'] = df_odds['PSW'].map(lambda x: calc_american_odds(x))
        df_odds['loser_odds'] = df_odds['PSL'].map(lambda x: calc_american_odds(x))
        df_odds['id'] = df_odds['Date'].map(lambda x: x.strftime('%m/%Y')) + '-' + df_odds['WRank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_odds['Winner'] + '-' + df_odds['LRank'].map(lambda x: str(int(x)) if not math.isnan(x) else 'NaN') + df_odds['Loser']
        df_odds.drop(columns=[
            'WTA',
            'Location',
            'Tournament',
            'Date', 
            'Tier',
            'Court',
            'Surface',
            'Round',
            'Best of',
            'Winner', 
            'Loser',
            'WRank',
            'LRank',
            'WPts',
            'LPts',
            'W1',
            'L1',
            'W2',
            'L2',
            'W3',
            'L3',
            'Wsets',
            'Lsets',
            'Comment',
            'B365W',
            'B365L',
            'PSW',
            'PSL',
            'MaxW',
            'MaxL',
            'AvgW',
            'AvgL'            
        ], axis=1, inplace=True)

        if 'EXW' in df_odds.columns:
            df_odds.drop(['EXW'], axis=1, inplace=True)

        if 'EXL' in df_odds.columns:
            df_odds.drop(['EXL'], axis=1, inplace=True)

        if 'LBW' in df_odds.columns:
            df_odds.drop(['LBW'], axis=1, inplace=True)

        if 'LBL' in df_odds.columns:
            df_odds.drop(['LBL'], axis=1, inplace=True)

        if 'SJW' in df_odds.columns:
            df_odds.drop(['SJW'], axis=1, inplace=True)

        if 'SJL' in df_odds.columns:
            df_odds.drop(['SJL'], axis=1, inplace=True)

        # print(df_odds)

        df_merged = df_matches.merge(df_odds, how='inner', on='id')
        df_merged.drop([
            'winner',
            'loser',
            'id'
        ], axis=1, inplace=True)
        # print(df_merged)

        df_merged.to_sql('tennis_match', engine, if_exists='append', index=False, chunksize=1000)

    for index, m in enumerate(Match.objects.all()):
        print(f'{index+1} out of {Match.objects.all().count()}')
        m.winner_dk = m.winner_dk_points
        m.winner_num_matches = m.get_winner_num_matches()
        m.winner_ace_rate = m.get_winner_ace_rate()
        m.winner_vace_rate = m.get_winner_v_ace_rate()
        m.winner_df_rate = m.get_winner_df_rate()
        m.winner_firstin_rate = m.get_winner_first_in_rate()
        m.winner_firstwon_rate = m.get_winner_first_won_rate()
        m.winner_secondwon_rate = m.get_winner_second_won_rate()
        m.winner_hold_rate = m.get_winner_hold_rate()
        m.winner_break_rate = m.get_winner_break_rate()
        m.loser_dk = m.loser_dk_points
        m.loser_num_matches = m.get_loser_num_matches()
        m.loser_ace_rate = m.get_loser_ace_rate()
        m.loser_vace_rate = m.get_loser_v_ace_rate()
        m.loser_df_rate = m.get_loser_df_rate()
        m.loser_firstin_rate = m.get_loser_first_in_rate()
        m.loser_firstwon_rate = m.get_loser_first_won_rate()
        m.loser_secondwon_rate = m.get_loser_second_won_rate()
        m.loser_hold_rate = m.get_loser_hold_rate()
        m.loser_break_rate = m.get_loser_break_rate()
        m.save()

    # for m in WTA_MATCH_FILES:
    #     print(m)
    #     df_matches = pandas.read_csv(m)
    #     df_matches['winner_id'] = df_matches['winner_id'].map(lambda x: f'wta-{x}')
    #     df_matches['loser_id'] = df_matches['loser_id'].map(lambda x: f'wta-{x}')
    #     df_matches['tourney_date'] = df_matches['tourney_date'].map(lambda x: datetime.datetime.strptime(str(x), '%Y%m%d'))
            
    #     df_matches.to_sql('tennis_match', engine, if_exists='append', index=False, chunksize=1000)
