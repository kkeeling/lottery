import numpy as np
import pandas as pd
import seaborn as sns
from fitter import Fitter, get_common_distributions, get_distributions

from nfl import models


def run():
    dataset = pd.read_csv("/opt/lottery/data/qbs_actuals.csv")
    dataset.head()
    dataset.info()
    
    diffs = dataset["actual"].values
    f = Fitter(
        diffs,
        distributions=[
            'gamma',
            'lognorm',
            "skewnorm",
        ]
    )
    f.fit()
    f.summary()   
    print(f.get_best(method = 'sumsquare_error'))
