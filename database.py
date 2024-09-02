import sqlite3
from sqlite3 import Error


def create_connection(DATABASE_NAME = "simulations.db"):
    """ 创建一个数据库连接到 SQLite 数据库 """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        #print(f"Successful connection with {DATABASE_NAME}")
    except Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def initialize_db(number=0,conn=create_connection()):
    """ 初始化数据库结构 """
    sql_create_characters_table = f"""
    CREATE TABLE IF NOT EXISTS characters{number}y (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        wealth INTEGER NOT NULL
    );
    """

    sql_create_relationships_table = f"""
    CREATE TABLE IF NOT EXISTS relationships{number}y (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person1_id INTEGER NOT NULL,
        person2_id INTEGER NOT NULL,
        relationship_type TEXT NOT NULL,
        FOREIGN KEY(person1_id) REFERENCES characters(id),
        FOREIGN KEY(person2_id) REFERENCES characters(id)
    );
    """

    if conn is not None:
        try:
            c = conn.cursor()
            c.execute(sql_create_characters_table)
            c.execute(sql_create_relationships_table)
            conn.commit()
            print("Database initialized.")
        except Error as e:
            print(f"An error occurred while initializing the database: {e}")


def insert_character_data(character,number=0,conn=create_connection()):
    """ 插入人物数据到数据库 """
    sql = f""" INSERT INTO characters{number}y(name, age, gender, wealth)
              VALUES(?,?,?,?) """
    
    if conn is not None:
        try:
            cur = conn.cursor()
            # 从character字典中提取数据
            cur.execute(sql, (character["name"], character["age"], character["gender"], character["wealth"]))
            conn.commit()
            #print("Character data inserted.")
            return cur.lastrowid
        except Error as e:
            print(f"An error occurred while inserting data: {e}")

    else:
        print("Error! Cannot create the database connection.")

def insert_relationship_data(person1_id, person2_id, relationship_type,number=0,conn=create_connection()):
    """ 插入人物关系数据到数据库 """
    sql = f""" INSERT INTO relationships{number}y(person1_id, person2_id, relationship_type)
              VALUES(?,?,?) """
    
    if conn is not None:
        try:
            cur = conn.cursor()
            cur.execute(sql, (person1_id, person2_id, relationship_type))
            conn.commit()
            #print("Relationship data inserted.")
            return cur.lastrowid
        except Error as e:
            print(f"An error occurred while inserting data: {e}")

    else:
        print("Error! Cannot create the database connection.")

def read_characters_data(number=0,conn=create_connection()):
    """
    读取数据库中的characters表，并格式化为指定的结构。
    """
    formatted_data = {"individual_list": []}
    
    
    if conn is not None:
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM characters{number}y")
            
            rows = cur.fetchall()
            for row in rows:
                formatted_data["individual_list"].append({
                    "title": f"{row[1]}",
                    "description": f" Age: {row[2]}, Gender: {row[3]}",
                    "status": f"Wealth: {row[4]}"  # Assuming all characters are "Completed"
                })
        except Error as e:
            print(f"An error occurred while reading data: {e}")

    else:
        print("Error! Cannot create the database connection.")
    
    return formatted_data

def read_sqlite_data(number=0,conn=create_connection()):
    
    # 执行查询
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM characters{number}y")
    
    # 获取所有结果
    results = cursor.fetchall()

    
    # 创建一个空的二维列表
    data = []
    
    # 将结果添加到二维列表中
    for row in results:
        data.append(row)
    
    # 返回二维列表和列名
    return data

def read_relationships(number=0,conn=create_connection()):
    
    # 执行查询
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM relationships{number}y")
    
    # 获取所有结果
    results = cursor.fetchall()
    
    # 创建一个空的列表来存储关系数据
    relationships = []
    
    # 将结果添加到列表中
    for row in results:
        relationships.append({
            "id": row[0],
            "person1_id": row[1],
            "person2_id": row[2],
            "relationship_type": row[3]
        })
    
    # 返回关系数据列表
    return relationships


# 使用示例
if __name__ == "__main__":
    initialize_db()
    # 插入一些示例数据
    # character_data = {
    #     "name": "Alice",
    #     "age": 30,
    #     "gender": "Female",
    #     "wealth": 50000
    # }
    # insert_character_data(character_data)
    
    # character_data = {
    #     "name": "Bob",
    #     "age": 25,
    #     "gender": "Male",
    #     "wealth": 40000
    # }
    # insert_character_data(character_data)
    
    # 读取并打印数据
    characters = read_sqlite_data()
    print(characters)

