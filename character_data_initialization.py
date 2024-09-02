import random
import database
from Generate_random_names import RandomUtil


def generate_random_person():
    # 假设我们已经有了一个函数来生成随机名字
    name,gender = RandomUtil().random_name_str()  # 这里应该调用实际的随机姓名生成函数

    age = random.randint(0, 80)
    
    
    # 财富可以假设一个正态分布
    mean_wealth = 50000  # 假设平均财富为50000
    std_deviation = 20000  # 标准差为20000
    wealth = int(random.gauss(mean_wealth, std_deviation))
    if wealth < 0:
        wealth = 0  # 最小财富不能为负数
    
    return {
        "name": name,
        "age": age,
        "gender": gender,
        "wealth": wealth
    }

if __name__ == "__main__":
    conn = database.create_connection()
    database.initialize_db(conn=conn)
    personList = []
    for _ in range(100):
        person = generate_random_person()
        personList.append(person)
        database.insert_character_data(person,conn=conn)
    conn.close()
    print(personList)

    