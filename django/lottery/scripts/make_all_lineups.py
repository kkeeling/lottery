import itertools
import time

import numpy as np
import pandas as pd

def run():
    df_salaries = pd.read_csv('data/DKSalaries - 2022-06-24T144349.928.csv', index_col='ID')

    r = 6   

    start = time.time()
    combinations = list(itertools.combinations(df_salaries.index.to_list(), r))

    print(f'There are {len(combinations)} possible lineups. Calculation took {time.time() - start}s')

    start = time.time()
    df_lineups = pd.DataFrame(data=combinations)
    print(f'Dataframe took {time.time() - start}s')
    start = time.time()
    df_lineups['salary'] = df_lineups[0].map(lambda x: df_salaries.loc[x, 'Salary']) + df_lineups[1].map(lambda x: df_salaries.loc[x, 'Salary']) + df_lineups[2].map(lambda x: df_salaries.loc[x, 'Salary']) + df_lineups[3].map(lambda x: df_salaries.loc[x, 'Salary']) + df_lineups[4].map(lambda x: df_salaries.loc[x, 'Salary']) + df_lineups[5].map(lambda x: df_salaries.loc[x, 'Salary'])
    print(f'Salary took {time.time() - start}s')
    start = time.time()
    df_lineups = df_lineups[(df_lineups.salary <= 50000) & (df_lineups.salary >= 48000)]
    print(f'Filtering took {time.time() - start}s')
    print(df_lineups)
