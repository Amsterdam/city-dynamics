import configparser
import argparse
import logging
import json
import requests
import time
import pandas as pd
import numpy as np

from scipy.stats import rankdata
from functools import reduce
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from datetime import date, datetime, timedelta

config_auth = configparser.RawConfigParser()
config_auth.read('auth.conf')

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def get_conn(dbConfig):
    POSTGRES_URL = URL(
        drivername='postgresql',
        username=config_auth.get(dbConfig, 'user'),
        password=config_auth.get(dbConfig, 'password'),
        host=config_auth.get(dbConfig, 'host'),
        port=config_auth.get(dbConfig, 'port'),
        database=config_auth.get(dbConfig, 'dbname')
    )
    conn = create_engine(POSTGRES_URL)
    return conn


def datetime_range(start, end, delta):
    current = start
    if not isinstance(delta, timedelta):
        delta = timedelta(**delta)
    while current < end:
        yield current
        current += delta


def min_max(x):
    x = np.array(x)
    x = (x - min(x)) / (max(x) - min(x))
    return x


def normalize(x):
    x = rankdata(x)
    return min_max(x)


def normalize_data(df, cols):
    df = df.groupby(['vollcode', 'timestamp'])[cols].mean().reset_index()
    for col in cols:
        new_col = col + '_normalized'
        df[new_col] = df.groupby(['timestamp'])[col].transform(normalize)

    return df


def import_verblijversindex(sql_query, conn):
    verblijversindex = pd.read_sql(sql=sql_query.format('VERBLIJVERSINDEX'), con=conn)
    verblijversindex = verblijversindex[['wijk', 'oppervlakte_m2']]
    verblijversindex.rename(columns={'wijk': 'vollcode', 'oppervlakte_m2': 'verblijversindex'}, inplace=True)
    verblijversindex = verblijversindex[['vollcode', 'verblijversindex']]
    return verblijversindex


def import_google(sql_query, conn):
    def read_table(sql_query, conn):
        df = pd.read_sql(sql=sql_query, con=conn)
        df['timestamp'] = df.timestamp.dt.round('60min')
        df = df[['place_id', 'vollcode', 'timestamp', 'live', 'historical']]
        return df

    # read raw data
    google_octnov = read_table(sql_query.format('google_with_bc'), conn=conn)
    google_dec = read_table(sql_query.format('google_dec_with_bc'), conn=conn)
    google = pd.concat([google_octnov, google_dec])
    del google_octnov, google_dec

    # historical weekpatroon
    google['weekday'] = [ts.weekday() for ts in google.timestamp]
    google['hour'] = [ts.hour for ts in google.timestamp]
    google_week = google.groupby(['weekday', 'hour', 'vollcode', 'place_id'])['historical'].mean().reset_index()
    google_week = google.groupby(['vollcode', 'weekday', 'hour'])['historical'].mean().reset_index()

    # live data
    google_live = google[['place_id', 'vollcode', 'timestamp', 'live']]
    google_live = google_live.groupby(['vollcode', 'timestamp'])['live'].mean().reset_index()
    google_live['weekday'] = [ts.weekday() for ts in google_live.timestamp]
    google_live['hour'] = [ts.hour for ts in google_live.timestamp]

    # column names
    google_live.rename(columns={'live': 'google_live'}, inplace=True)
    google_week.rename(columns={'historical': 'google_week'}, inplace=True)

    return google_week, google_live


def import_gvb(sql_query, conn, haltes):
    def read_table(sql_query, conn):
        df = pd.read_sql(sql=sql_query, con=conn)
        df['timestamp'] = df.timestamp.dt.round('60min')
        df['weekday'] = [ts.weekday() for ts in df.timestamp]
        df['hour'] = [ts.hour for ts in df.timestamp]
        df = df[['halte', 'incoming', 'weekday', 'hour', 'lat', 'lon', 'vollcode']]
        return df

    # read raw
    gvb = read_table(sql_query.format('gvb_with_bc'), conn=conn)

    # hele stad over tijd
    indx = gvb.halte.isin(haltes)
    gvb_stad = gvb.loc[indx, :]
    gvb_stad = gvb_stad.groupby(['weekday', 'hour'])['incoming'].sum().reset_index()

    # per buurt
    gvb_buurt = gvb.loc[np.logical_not(indx), :]
    gvb_buurt = gvb_buurt.groupby(['vollcode', 'weekday', 'hour'])['incoming'].sum().reset_index()

    # column names
    gvb_stad.rename(columns={'incoming': 'gvb_stad'}, inplace=True)
    gvb_buurt.rename(columns={'incoming': 'gvb_buurt'}, inplace=True)

    return gvb_stad, gvb_buurt


def import_tellus(sql_query, conn, vollcodes):
    df = pd.read_sql(sql=sql_query.format('tellus_with_bc'), con=conn)
    df['timestamp'] = df.timestamp.dt.round('60min')
    df = df[['meetwaarde', 'timestamp', 'vollcode']]
    df['meetwaarde'] = df.meetwaarde.astype(int)
    df = df.groupby('timestamp')['meetwaarde'].sum().reset_index()

    # add all vollcodes per timestamp
    vc_ts = [(vc, ts) for vc in vollcodes for ts in df.timestamp.unique()]
    vc_ts = pd.DataFrame({
        'vollcode': [x[0] for x in vc_ts],
        'timestamp': [x[1] for x in vc_ts]
        })
    df = pd.merge(df, vc_ts, on='timestamp', how='outer')

    # column names
    df.rename(columns={'meetwaarde': 'tellus'}, inplace=True)

    return df


# def merge_datasets(**kwargs):

#     with_timestamp = [kwargs[dname] for dname in kwargs.keys() if 'timestamp' in kwargs[dname].columns]
#     drukte = reduce(lambda x, y: pd.merge(x, y, on = ['timestamp', 'vollcode'], how='outer'), with_timestamp)
#     print(drukte.shape)
#     return reduce(lambda x, y: pd.merge(**kwargs, on = ['timestamp', 'vollcode'], how='outer'), data)
# merge_datasets(tellus=tellus, google_live=google_live, google_week=google_week, gvb_buurt=gvb_buurt, gvb_stad=gvb_stad)

def complete_ts_vollcode(data, vollcodes):
    # get list of timestamps
    start = np.min(data.timestamp)
    end = np.max(data.timestamp)
    timestamps = pd.date_range(start=start, end=end, freq='H')

    # create new dataframe
    ts_vc = [(ts, vc) for ts in data.timestamp for vc in vollcodes]
    mind = pd.DataFrame({
        'timestamp': [x[0] for x in ts_vc],
        'vollcode': [x[1] for x in ts_vc]
        })

    # merge data
    data = pd.merge(mind, data, on=['timestamp', 'vollcode'], how='outer')

    # fill in missing weekdays and hours
    data['weekday'] = [ts.weekday() for ts in data.timestamp]
    data['hour'] = [ts.hour for ts in data.timestamp]

    return data


def weighted_mean(data, cols, weights):
    # create numpy array with right columns
    x = np.array(data.loc[:, cols])

    # calculate weight matrix
    n_weights = len(weights)
    weights = np.array(weights * len(x)).reshape(len(x), n_weights)
    weights[np.isnan(x)] = 0

    # calculate overall index
    wmean = np.array(x * weights)
    wmean = np.nanmean(wmean, axis=1) / weights.sum(axis=1)

    return wmean


def main():
    # create connection
    conn = get_conn(dbConfig=args.dbConfig[0])

    # base call
    sql_query = """ SELECT * FROM "{}" """

    # read buurtcodes
    buurtcodes = pd.read_sql(sql=sql_query.format('buurtcombinatie'), con=conn)

    # verblijversindex
    log.debug('verblijversindex')
    verblijversindex = import_verblijversindex(sql_query=sql_query, conn=conn)

    # read google weekly pattern and live data
    google_week, google_live = import_google(sql_query, conn)

    # read GVB overall city and neighborhood-specific patterns
    haltes = list(pd.read_csv('metro_or_train.csv', sep=',')['station'])
    gvb_stad, gvb_buurt = import_gvb(sql_query, conn, haltes)

    # read tellus for city centre neighborhoods
    vollcodes_centrum = [bc for bc in buurtcodes.vollcode.unique() if 'A' in bc]
    tellus = import_tellus(sql_query, conn, vollcodes_centrum)

    # merge datasets
    log.debug('merge datasets')
    # google_live
    # goovle_week
    # gvb_stad
    # gvb_buurt
    # tellus

    # merge data with timestamps
    drukte = google_live.copy()

    # filter on october onwards
    drukte = drukte.loc[drukte['timestamp'] >= '2017-10-01 00:00:00', :]

    # fill in missing timestamp-vollcode combinations
    all_vollcodes = [bc for bc in buurtcodes.vollcode.unique()]
    drukte = complete_ts_vollcode(data=drukte, vollcodes=all_vollcodes)

    # add google historical
    drukte = pd.merge(drukte, google_week, on=['vollcode', 'weekday', 'hour'], how='outer')

    # add gvb buurt
    drukte = pd.merge(drukte, gvb_buurt, on=['vollcode', 'weekday', 'hour'], how='outer')

    # add verblijversindex
    drukte = pd.merge(drukte, verblijversindex, on='vollcode', how='outer')

    # add buurtcode information
    # drukte = pd.merge(drukte, buurtcodes, on='vollcode', how='left')

    log.debug('calculating overall index')

    # define weights, have to be in same order als columns!
    cols = ['google_live', 'google_week', 'gvb_buurt', 'verblijversindex']
    drukte = normalize_data(df=drukte, cols=cols)
    weights = [0.3, 0.3, 0.2, 0.2]
    normalized_cols = [col + '_normalized' for col in cols]
    drukte['drukte_index'] = weighted_mean(data=drukte, cols=normalized_cols, weights=weights)

    # drop obsolete columns
    drukte.drop(cols, axis=1, inplace=True)

    # write to db
    log.debug('writing data to db')
    drukte.to_sql(name='drukteindex', con=conn, index=True, if_exists='replace')
    conn.execute('ALTER TABLE "drukteindex" ADD PRIMARY KEY ("index")')
    log.debug('Done you are awesome <3')


if __name__ == '__main__':
    desc = "Calculate index."
    log.debug(desc)
    parser = argparse.ArgumentParser(desc)
    parser.add_argument('dbConfig', type=str, help='database config settings: dev or docker', nargs=1)
    args = parser.parse_args()
    main()
