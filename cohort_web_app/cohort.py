import os
import inflection
import sqlite3

import numpy   as np
import pandas  as pd
import seaborn as sns

import matplotlib.ticker   as mticker
import matplotlib.colors   as mcolors
import matplotlib.pyplot   as plt


from IPython.display import HTML
from IPython.display import Image
from operator        import attrgetter

from sqlalchemy import create_engine

from platform                import python_version
print('Versão da Linguagem Python Usada Neste Jupyter Notebook:', python_version())
# %%
def data_gathering(s3_path):
    
    data_raw = pd.read_csv(s3_path,
                               encoding='iso-8859-1',
                               low_memory=False)
    #drop extra column
    data_raw = data_raw.drop(columns = ['Unnamed: 8'], axis = 1)
    
    return data_raw

def data_cluster(conn):
    # get query
    query_collect = """
        SELECT
            customer_id,
            cluster
        from champions
    """
    
    df_clusters = pd.read_sql_query(query_collect, conn)
    
    return df_clusters

def data_cleaning(data_raw):
    
    ## rename columns
    cols_old = data_raw.columns
    
    snakecase = lambda x: inflection.underscore(x)
    col_news = list(map(snakecase, cols_old))
    
    data_raw.columns = col_news
    
    # separate NA's in two different dataframe, one with NAs and other without it
    df_missing = data_raw.loc[data_raw['customer_id'].isna(), :]
    df_not_missing = data_raw.loc[~data_raw['customer_id'].isna(), :]
    
    # create reference
    df_backup = pd.DataFrame( df_missing['invoice_no'].drop_duplicates().copy() )
    df_backup['customer_id'] = np.arange( 19000, 19000+len( df_backup ), 1) # Fillout NA stratety: creating customers_id to keep their behavior (25% of the database)
    
    # merge original with reference dataframe
    data_raw = pd.merge( data_raw, df_backup, on='invoice_no', how='left' )
    
    # coalesce 
    data_raw['customer_id'] = data_raw['customer_id_x'].combine_first( data_raw['customer_id_y'] )
    
    # drop extra columns
    data_raw = data_raw.drop( columns=['customer_id_x', 'customer_id_y'], axis=1 )
    
    ## Change Types
    # Transforme datatype of variable invoice_date to datetime
    data_raw['invoice_date'] = pd.to_datetime(data_raw['invoice_date'])
    
    data_raw['customer_id'] = data_raw['customer_id'].astype('int64')
    
    # === Numerical attributes ====
    data_raw = data_raw.loc[data_raw['unit_price'] >= 0.04, :]
    
    # === Categorical attributes ====
    #stock code
    data_raw = data_raw[~data_raw['stock_code'].isin( ['POST', 'D', 'DOT', 'M', 'S', 'AMAZONFEE', 'm', 'DCGSSBOY',
                                        'DCGSSGIRL', 'PADS', 'B', 'CRUK'] )]
    
    # description
    data_raw = data_raw.drop( columns='description', axis=1 )
    
    # country 
    data_raw = data_raw[~data_raw['country'].isin( ['European Community', 'Unspecified' ] ) ] #assuming this risk so we can use lat long parameters
    
    # bad customers
    data_raw = data_raw[~data_raw['customer_id'].isin([16446, 12346, 15098])]
    
    # quantity 
    df0_returns = data_raw.loc[data_raw['quantity'] < 0, :].copy() # considering negative quantity is equal returned items
    df0_purchases = data_raw.loc[data_raw['quantity'] >= 0, :].copy()
    
    return df0_purchases, df0_returns

def multi_invoices_percentage(df0_purchases):
    
    df_invoice_no = df0_purchases[['customer_id', 'invoice_no']].drop_duplicates().groupby('customer_id').count().reset_index().rename(columns = {'invoice_no': 'qty_invoice_no'})
    mult_invoices_perc = np.sum(df_invoice_no > 1) / df_invoice_no['customer_id'].nunique() * 100
    
    return mult_invoices_perc[1]

def data_feature_engineer(df0_purchases, df0_returns, df_clusters):
    
    #returned items
    df0_returns['quantity'] = df0_returns['quantity'] * -1
    df0_returns['gross_revenue'] = df0_returns['quantity'] * df0_returns['unit_price']
    
    #returns dataframe
    #merge with df_cluster
    df0_returns = pd.merge(df0_returns, df_clusters, how = 'left' ,on = 'customer_id') #returns dataframe
    df0_returns = df0_returns[['customer_id', 'invoice_no','gross_revenue', 'invoice_date', 'cluster']].groupby(['customer_id','invoice_no', 'invoice_date', 'cluster']).sum().reset_index()

    df0_returns['invoice_month'] = df0_returns['invoice_date'].dt.to_period('M')
    df0_returns['cohort'] = df0_returns.groupby('customer_id')['invoice_date'].transform('min').dt.to_period('M') 
    df0_returns['period_number'] = (df0_returns['invoice_month'] - df0_returns['cohort']).apply(attrgetter('n'))
    
    
    #purchases dataframe
    # Gross Revenue ( Faturamento ) quantity * price
    df0_purchases['gross_revenue'] = df0_purchases['quantity'] * df0_purchases['unit_price']
    
    #merge with df_cluster
    df0_purchases = pd.merge(df0_purchases, df_clusters, how = 'left' ,on = 'customer_id') #purchases dataframe
    df0_purchases = df0_purchases[['customer_id', 'invoice_no','gross_revenue', 'invoice_date', 'cluster']].groupby(['customer_id','invoice_no', 'invoice_date', 'cluster']).sum().reset_index()
    
    df0_purchases['invoice_month'] = df0_purchases['invoice_date'].dt.to_period('M')
    df0_purchases['cohort'] = df0_purchases.groupby('customer_id')['invoice_date'].transform('min').dt.to_period('M') 
    df0_purchases['period_number'] = (df0_purchases['invoice_month'] - df0_purchases['cohort']).apply(attrgetter('n'))
    
    return df0_purchases, df0_returns

def cohort_total_customers(df1_purchases): 
    df_cohort_purchases = df1_purchases[['customer_id','invoice_month','gross_revenue', 'cohort', 'period_number']].groupby(['cohort', 'invoice_month', 'period_number']).agg(qty_customers = ('customer_id', 'nunique'), gross_revenue = ('gross_revenue', 'sum')).reset_index()

    return df_cohort_purchases

def cohort_by_cluster(df, cluster):
    df_cohort_cluster = df[df['cluster']== cluster].copy()
    
    # creating cohort dataset
    df_cohort_cluster = df_cohort_cluster[['customer_id','invoice_month','gross_revenue', 'cohort', 'period_number']].groupby(['cohort', 'invoice_month', 'period_number']).agg(qty_customers = ('customer_id', 'nunique'), gross_revenue = ('gross_revenue', 'sum')).reset_index()

    return df_cohort_cluster

def retention_cohort(df):
    
    #retention cohort table
    cohort_pivot_retention = df.pivot_table(index = 'cohort',
                                     columns = 'period_number',
                                     values = 'qty_customers')
    # getting percentage values
    cohort_size_retention = cohort_pivot_retention.iloc[:,0]
    retention_matrix = cohort_pivot_retention.divide(cohort_size_retention, axis = 0)
    
    return cohort_pivot_retention, retention_matrix, cohort_size_retention

def revenue_cohort(df):
    #gross revenue cohort table
    cohort_pivot_revenue = df.pivot_table(index = 'cohort',
                                     columns = 'period_number',
                                     values = 'gross_revenue')
    
    # getting percentage values
    cohort_size_revenue = cohort_pivot_revenue.iloc[:,0]
    revenue_matrix = cohort_pivot_revenue.divide(cohort_size_revenue, axis = 0)
    
    return cohort_pivot_revenue, revenue_matrix, cohort_size_revenue

# %%
# main function
if __name__ == '__main__':

    ## parameters and constants
    # get AWS environmnet access keys
    AWS_ACCESS_KEY_ID     = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

    # path
    s3_path = 's3://mc-insiders-dataset/Ecommerce.csv'

    #db connection
    conn = create_engine('sqlite:///../data/champions_db.sqlite')

    df = data_gathering(s3_path)
    df_clusters = data_cluster(conn)

    df0_purchases, df0_returns = data_cleaning(df)

    multi_invoices = multi_invoices_percentage(df0_purchases)
    print(multi_invoices)

    df1_purchases, df1_returns = data_feature_engineer(df0_purchases, df0_returns, df_clusters)

    df_cohort_purchases = cohort_total_customers(df1_purchases)
    df_cohort_cluster = cohort_by_cluster(df1_purchases, 6)

    cohort_table_abs, cohort_table_perc, cohort_size = retention_cohort(df_cohort_purchases)
    cohort_table_abs, cohort_table_perc, cohort_size = revenue_cohort(df_cohort_purchases)

    cohort_table_abs, cohort_table_perc, cohort_size = retention_cohort(df_cohort_cluster)
    cohort_table_abs, cohort_table_perc, cohort_size = revenue_cohort(df_cohort_cluster)