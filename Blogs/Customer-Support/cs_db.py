from sqlite3 import connect
import os
import pandas as pd
from pandas.core.frame import DataFrame
from contextlib import closing
from cs_util import Utility


class Database:
    def __init__(self):
        self.util = Utility()
        temp_path = self.util.get_temp_path()

        if not os.path.exists(temp_path):
            os.makedirs(temp_path)

    # This function creates anew SQLite database and imports content of .json files in the db
    def import_in_db(self, table_name: str, json_file_path: str):
        df = pd.read_json(json_file_path)
        with closing(connect(self.util.get_db_path())) as conn:
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            conn.close()

        #log_data(data=f"Table *{table_name}* created with {len(df)} rows.")

    def execute_query(self, query: str, params: list = None, not_found_message: str=''):
        '''
        This function executes provided SQL statement on SQLite database and returns records in json format
        '''

        with closing(connect(self.util.get_db_path())) as conn:
            df = pd.read_sql_query(sql=query, con=conn, params=params)

        if not df.empty:
            return df.to_json(orient='records')
        else:
            return not_found_message
        
    def import_all(self):

        data_path = self.util.get_data_path()

        self.import_in_db(table_name='customers', json_file_path=f'{data_path}/customers.json')
        self.import_in_db(table_name='orders', json_file_path=f'{data_path}/orders.json')
        self.import_in_db(table_name='transactions', json_file_path=f'{data_path}/transactions.json')
        self.import_in_db(table_name='refunds', json_file_path=f'{data_path}/refunds.json')