import pandas as pd
import datetime as dt
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.optimize import minimize
from scipy import stats


def make_ER(price, rate):

    """
    :param price: pd.DataFrame containing the prices of the ticker
    :param rate: pd.Series containing the rate prices
    :return:
    """

    dates = price.index
    price_ER = pd.DataFrame(index=dates, columns=price.columns)
    price_ER.iloc[0] = 1.
    n = len(dates)

    rate = rate.reindex(dates).ffill()

    for i in range(1, n):
        price_ER.iloc[i] = price_ER.iloc[i-1] * (price.iloc[i] / price.iloc[i-1]
                                                 - rate.loc[dates[i-1]] * (dates[i] - dates[i-1]).days/ 36000.)

    return price_ER


def make_track(df_price, df_weight, tc=0):
    """
    :param df_price: a dataframe containing the prices of the underlyings used in the index, columns must be the names
    and the index are the dates
    :param df_weight: a dataframe containing the weight on the rebalancing dates of the track created
    :param tc: transaction cost, default is 0
    :return: a pandas series containing the track made from the composition in df_weight
    """

    index = df_price.index
    reweight_index = df_weight.index

    n = len(index)
    shares = (df_weight / df_price).iloc[0]
    cash = 1 - (shares * df_price.iloc[0]).sum() # add cash when weigh_sum <> 1 in ER
    value = np.ones(n)

    for i in range(1, len(index)):

        if index[i-1] in reweight_index:
            cost = tc * value[i-1] * np.abs(df_weight.loc[index[i-1]] - (shares * df_price.loc[index[i-1]])/value[i-1]).sum()
            value[i] = (shares * df_price.loc[index[i]]).sum() - cost + cash
            shares = df_weight.loc[index[i-1]] * value[i] / df_price.loc[index[i]]
            cash = value[i] - (shares * df_price.loc[index[i]]).sum()
        else: 
            value[i] = (shares * df_price.loc[index[i]]).sum() + cash

    return pd.DataFrame(index=index, data=value, columns=['Track'])


def ols_regression(df_y, df_x, sample_length: int, frequency: int, boundaries=(-np.inf, np.inf),
                   weight_sum=np.nan):

    index = df_y.index.copy()
    n, m = df_x.shape

    df_weight = pd.DataFrame(columns=df_x.columns)

    for i in range((n - sample_length)//frequency):

        start = index[i*frequency]
        end = index[i*frequency + sample_length]

        x = df_x.loc[start:end].values
        y = df_y.loc[start:end].values

        def loss(z):
            return np.sum(np.square(np.dot(x, z)-y))

        cons = ({'type': 'eq',
                 'fun': lambda z: np.sum(z) - weight_sum}) if not np.isnan(weight_sum) else ()
        bounds = [boundaries]*m
        z0 = np.zeros([m, 1])

        res = minimize(loss, z0, method='SLSQP', constraints=cons, bounds=bounds)

        df_weight.loc[end] = res.x

    return df_weight


def ols_regression_ER(df_y, df_x, sample_length: int, frequency: int, boundaries=(-np.inf, np.inf),
                     weight_sum=np.nan):
    """
        This regression can only be used in excess return as the weight sum does not equal 0

    :param df_y:
    :param df_x:
    :param sample_length:
    :param frequency:
    :param boundaries:
    :param weight_sum:
    :return:
    """

    index = df_y.index.copy()
    n, m = df_x.shape

    df_weight = pd.DataFrame(columns=df_x.columns)

    for i in range((n - sample_length)//frequency):

        start = index[i*frequency]
        end = index[i*frequency + sample_length]

        x = df_x.loc[start:end]
        std_x = x.std(axis=0).replace(0, np.nan)
        x = (x/std_x).replace(np.nan, 0).values

        y = df_y.loc[start:end]
        std_y = y.std(axis=0).replace(0, np.nan)
        y = (y/std_y).replace(np.nan, 0).values

        def loss(z):
            return np.sum((np.dot(x, z)-y)**2)

        cons = ({'type': 'eq',
                 'fun': lambda z: np.sum(z) - weight_sum}) if not np.isnan(weight_sum) else ()
        bounds = [boundaries]*m
        z0 = np.zeros([m, 1])

        res = minimize(loss, z0, method='SLSQP', constraints=cons, bounds=bounds)

        df_weight.loc[end] = std_y.iloc[0]*res.x/std_x

    return df_weight


def lasso_regression_ER(df_y, df_x, sample_length: int, frequency: int, lambda_:float, boundaries=(-np.inf, np.inf),
                        weight_sum=np.nan):
    """
        This regression can only be used in excess return as the weight sum does not equal 0

    :param df_y:
    :param df_x:
    :param sample_length:
    :param frequency:
    :param boundaries:
    :param weight_sum:
    :return:
    """

    index = df_y.index.copy()
    n, m = df_x.shape

    df_weight = pd.DataFrame(columns=df_x.columns)

    for i in range((n - sample_length) // frequency):
        start = index[i * frequency]
        end = index[i * frequency + sample_length]

        x = df_x.loc[start:end]
        std_x = x.std(axis=0).replace(0, np.nan)
        x = (x / std_x).replace(np.nan, 0).values

        y = df_y.loc[start:end]
        std_y = y.std(axis=0).replace(0, np.nan)
        y = (y / std_y).replace(np.nan, 0).values

        def loss(z):
            return np.sum((np.dot(x, z) - y)**2) + lambda_*n*np.sum(np.abs(z))

        cons = ({'type': 'eq',
                 'fun': lambda z: np.sum(z) - weight_sum}) if not np.isnan(weight_sum) else ()

        bounds = [boundaries] * m
        z0 = np.zeros([m, 1])

        res = minimize(loss, z0, method='SLSQP', constraints=cons, bounds=bounds)

        df_weight.loc[end] = std_y.iloc[0] * res.x / std_x

    return df_weight


def make_stats(df_price):
    df_return = df_price.pct_change().dropna()
    stats.describe(df_return)
    t_tstat, p_tstat = stats.ttest_rel(df_return.iloc[:,0], df_return.iloc[:, 1])  # T-test
    t_KS, p_KS = stats.ks_2samp(df_return.iloc[:,0], df_return.iloc[:, 1])  # KS -> p petit pas la meme distri
    tau, p_tau = stats.kendalltau(df_return.iloc[:,0], df_return.iloc[:, 1])  # Tau de Kendall

    return stats.describe(df_return),"t test: t = %g  p = %g" % (t_tstat, p_tstat), \
           "KS test: t = %g  p = %g" % (t_KS, p_KS), "KendallTau: t = %g  p = %g" % (tau, p_tau)


if __name__ == "__main__":
    sns.set()
    prices = pd.read_csv(r"financial_data/prices.csv", index_col=0, parse_dates=True, dayfirst=True)
    prices.index = pd.DatetimeIndex(prices.index)
    EU_rate = pd.read_csv(r"financial_data/EUR_rates.csv", index_col=0, parse_dates=True, dayfirst=True)['3M']

    mondays = pd.date_range(start=dt.date(2010, 1, 4), end=dt.date.today(), freq='7D')
    returns = prices.reindex(mondays).ffill().pct_change().dropna()

    sx5e = returns[["SX5E"]]
    bch = returns.drop("SX5E", axis=1)

    # Params
    sample = 52
    freq = 13

    weight = ols_regression(sx5e, bch, sample, freq, boundaries=(0, np.inf), weight_sum=1)
    prices_for_track = prices.loc[weight.index[0]:].drop("SX5E", axis=1)
    replication = make_track(prices_for_track, weight)

    df_res = prices.loc[weight.index[0]:][["SX5E"]]
    df_res["OLS Rui"] = replication
    df_res["OLS ER"] = make_ER(replication, EU_rate)

    df_res = df_res / df_res.iloc[0]
    df_res = df_res.bfill()

    df_res.plot(figsize=(10, 6))
    plt.show()


