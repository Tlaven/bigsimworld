import random
import string
from datetime import datetime
import database

DATABASE_NAME = 'simulations.db'

# ...（你的其他代码保持不变）

def generate_random_string(length=10):
    """生成随机字符串"""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

def generate_random_simulation_data():
    """生成随机的模拟数据"""
    name = f"Simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    parameters = generate_random_string(50)
    results = generate_random_string(50)
    return (name, parameters, results)

def test_insert_simulation_data():
    """测试插入模拟数据"""
    data = generate_random_simulation_data()
    print(data)
    database.insert_simulation_data(data)

if __name__ == '__main__':
    database.initialize_db()
    test_insert_simulation_data()