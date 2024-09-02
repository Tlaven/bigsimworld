import sqlite3
from sqlite3 import Error

DATABASE_NAME = 'simulations.db'

def create_connection():
    """ 创建一个数据库连接到 SQLite 数据库 """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        print(f'Successful connection with {DATABASE_NAME}')
    except Error as e:
        print(f'Error connecting to database: {e}')
    return conn

def initialize_db():
    """ 初始化数据库结构 """
    sql_create_simulations_table = """
    CREATE TABLE IF NOT EXISTS simulations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        parameters TEXT NOT NULL,
        results TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """

    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute(sql_create_simulations_table)
            conn.commit()
            print("Database initialized.")
        except Error as e:
            print(f'An error occurred while initializing the database: {e}')
        finally:
            conn.close()

def insert_simulation_data(data):
    """ 插入模拟数据到数据库 """
    sql = ''' INSERT INTO simulations(name, parameters, results)
              VALUES(?,?,?) '''
    conn = create_connection()
    if conn is not None:
        try:
            cur = conn.cursor()
            cur.execute(sql, data)
            conn.commit()
            print("Data inserted.")
            return cur.lastrowid
        except Error as e:
            print(f'An error occurred while inserting data: {e}')
        finally:
            conn.close()
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    initialize_db()
