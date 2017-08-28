# -*- coding: utf-8 -*-
"""
Created on 2017-8-24

@author: cheng.li
"""

import numpy as np
import pandas as pd
import copy
from sklearn.linear_model import LinearRegression
from alphamind.api import *
from PyFin.api import *
from matplotlib import pyplot as plt

plt.style.use('ggplot')

'''
Settings:

universe     - zz500
neutralize   - all industries
benchmark    - zz500
base factors - all the risk styles
quantiles    - 5
start_date   - 2012-01-01
end_date     - 2017-08-01
re-balance   - 1 week
training     - every 4 week
'''

engine = SqlEngine('postgresql+psycopg2://postgres:A12345678!@10.63.6.220/alpha')
universe = Universe('zz500', ['zz500'])
neutralize_risk = industry_styles
alpha_factors = ['RVOL', 'EPS', 'CFinc1', 'BDTO', 'VAL', 'GREV',
                 'ROEDiluted']  # ['BDTO', 'RVOL', 'CHV', 'VAL', 'CFinc1'] # risk_styles
benchmark = 905
n_bins = 5
frequency = '1w'
batch = 4
start_date = '2012-01-01'
end_date = '2017-08-31'

'''
fetch data from target data base and do the corresponding data processing
'''

data_package = fetch_data_package(engine,
                                  alpha_factors=alpha_factors,
                                  start_date=start_date,
                                  end_date=end_date,
                                  frequency=frequency,
                                  universe=universe,
                                  benchmark=benchmark,
                                  batch=batch,
                                  neutralized_risk=neutralize_risk,
                                  pre_process=[winsorize_normal, standardize],
                                  post_process=[standardize],
                                  warm_start=20)

'''
training phase: using Linear - regression from scikit-learn
'''

train_x = data_package['train']['x']
train_y = data_package['train']['y']

dates = sorted(train_x.keys())

model = LinearRegression(fit_intercept=False)
model_df = pd.Series()

for train_date in dates:
    x = train_x[train_date]
    y = train_y[train_date]

    model.fit(x, y)
    model_df.loc[train_date] = copy.deepcopy(model)
    print('trade_date: {0} training finished'.format(train_date))

'''
predicting phase: using trained model on the re-balance dates
'''

predict_x = data_package['predict']['x']
settlement = data_package['settlement']

# final_res = np.zeros((len(dates), n_bins))
#
# for i, predict_date in enumerate(dates):
#     model = model_df[predict_date]
#     x = predict_x[predict_date]
#     benchmark_w = settlement[settlement.trade_date == predict_date]['weight'].values
#     realized_r = settlement[settlement.trade_date == predict_date]['dx'].values
#
#     predict_y = model.predict(x)
#
#     res = er_quantile_analysis(predict_y,
#                                n_bins,
#                                dx_return=realized_r,
#                                benchmark=benchmark_w)
#
#     final_res[i] = res / benchmark_w.sum()
#     print('trade_date: {0} predicting finished'.format(train_date))
#
# last_date = advanceDateByCalendar('china.sse', dates[-1], frequency)
#
# df = pd.DataFrame(final_res, index=dates[1:] + [last_date])
# df.sort_index(inplace=True)
# df.cumsum().plot()
# plt.title('Risk style factors model training with Linear Regression from 2012 - 2017')
# plt.show()

'''
predicting phase: using trained model on the re-balance dates (optimizing with risk neutral)
'''

industry_dummies = pd.get_dummies(settlement['industry_code'].values)
final_res = np.zeros(len(dates))

for i, predict_date in enumerate(dates):
    model = model_df[predict_date]
    x = predict_x[predict_date]
    cons = Constraints()
    index = settlement.trade_date == predict_date
    benchmark_w = settlement[index]['weight'].values
    realized_r = settlement[index]['dx'].values
    industry_names = settlement[index]['industry'].values
    is_tradable = settlement[index]['isOpen'].values
    ind_exp = industry_dummies[index]

    risk_tags = ind_exp.columns
    cons.add_exposure(risk_tags, ind_exp.values)
    benchmark_exp = benchmark_w @ ind_exp.values

    for k, name in enumerate(risk_tags):
        cons.set_constraints(name, benchmark_exp[k], benchmark_exp[k])

    predict_y = model.predict(x)
    weights, analysis = er_portfolio_analysis(predict_y,
                                              industry_names,
                                              realized_r,
                                              constraints=cons,
                                              detail_analysis=True,
                                              benchmark=benchmark_w,
                                              is_tradable=is_tradable)

    final_res[i] = analysis['er']['total'] / benchmark_w.sum()

last_date = advanceDateByCalendar('china.sse', dates[-1], frequency)

df = pd.Series(final_res, index=dates[1:] + [last_date])
df.sort_index(inplace=True)
df.cumsum().plot()
plt.title('Risk style factors model training with Linear Regression from 2012 - 2017')
plt.show()

