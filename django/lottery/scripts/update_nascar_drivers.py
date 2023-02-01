import datetime
import math
import numpy
import pandas
import requests
import sqlalchemy
import uuid

from random import random

from django.conf import settings
from django.db.models import Q, Sum

from nascar.models import Driver, Alias

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

    url = 'https://cf.nascar.com/cacher/drivers.json'
    r = requests.get(url)

    if r.status_code >= 300:
        r.raise_for_status()

    # print(r.json().get('response'))
    df_drivers = pandas.DataFrame(r.json().get('response'))
    df_drivers.drop_duplicates(subset=['Nascar_Driver_ID'], inplace=True)
    df_drivers['nascar_driver_id'] = df_drivers['Nascar_Driver_ID']
    df_drivers['driver_id'] = df_drivers['Driver_ID']
    df_drivers['first_name'] = df_drivers['First_Name']
    df_drivers['last_name'] = df_drivers['Last_Name']
    df_drivers['full_name'] = df_drivers['Full_Name']
    df_drivers['badge'] = df_drivers['Badge']
    df_drivers['badge_image'] = df_drivers['Badge_Image']
    df_drivers['manufacturer_image'] = df_drivers['Manufacturer']
    df_drivers['team'] = df_drivers['Team']
    df_drivers['driver_image'] = df_drivers['Image']
    df_drivers = df_drivers.set_index(df_drivers['nascar_driver_id'])
    
    df_drivers.drop([
        'nascar_driver_id',
        'Nascar_Driver_ID',
        'Driver_ID',
        'Driver_Series',
        'First_Name',
        'Last_Name',
        'Full_Name',
        'Series_Logo',
        'Short_Name',
        'Description',
        'DOB',
        'DOD',
        'Hometown_City',
        'Crew_Chief',
        'Hometown_State',
        'Hometown_Country',
        'Rookie_Year_Series_1',
        'Rookie_Year_Series_2',
        'Rookie_Year_Series_3',
        'Hobbies',
        'Children',
        'Twitter_Handle',
        'Residing_City',
        'Residing_State',
        'Residing_Country',
        'Badge',
        'Badge_Image',
        'Manufacturer',
        'Manufacturer_Small',
        'Team',
        'Image',
        'Image_Small',
        'Image_Transparent',
        'SecondaryImage',
        'Firesuit_Image',
        'Firesuit_Image_Small',
        'Career_Stats',
        'Driver_Page',
        'Age',
        'Rank',
        'Points',
        'Points_Behind',
        'No_Wins',
        'Poles',
        'Top5',
        'Top10',
        'Laps_Led',
        'Stage_Wins',
        'Playoff_Points',
        'Playoff_Rank',
        'Integrated_Sponsor_Name',
        'Integrated_Sponsor',
        'Integrated_Sponsor_URL',
        'Silly_Season_Change',
        'Silly_Season_Change_Description'
    ], axis=1, inplace=True)
    print(df_drivers)
        
    upsert_df(df=df_drivers, table_name='nascar_driver', engine=engine)

