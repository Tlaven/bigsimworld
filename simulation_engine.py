import random
import database
import re
import time
import json
import data_statistics
from Generate_random_names import RandomUtil



class Character:
    def __init__(self, id, name, age, gender, occupation):
        self.id = id
        self.name = name
        self.age = age
        self.gender = gender
        self.occupation = int(occupation)
        self.relations = {}

    def next_year(self):
        if self.age < 0:return 'died'
        self.age+=1
        
    def die(self):
        self.age = -1

class Event:
    def __init__(self, events=[], time=0, characters=0, effect=0,died_characters=0):
        self.events = events
        self.time = time
        self.characters = characters
        self.effect = effect
        self.died_characters = died_characters
        self.adults = [character for _,character in self.characters.items() if 20 <= character.age < 60]
        self.married_adults = [adult for adult in self.adults if "spouse" in adult.relations]
        self.unmarried_adults = [adult for adult in self.adults if not "spouse" in adult.relations]

    
    def establish_marriage_relations(self):
        males = [adult for adult in self.unmarried_adults if adult.gender == '男']
        females = [adult for adult in self.unmarried_adults if adult.gender == '女']
        
        # 尝试随机配对男性和女性
        for male in males:
            if females != [] and random.random() < 0.2:  # 20%的概率建立婚姻关系
                female = random.choice(females)
                females.remove(female)
                male.relations["spouse"] = female.id
                female.relations["spouse"] = male.id
                print(female.name,male.name,"spouse")
                    
    def childbirth(self):
        females = [adult for adult in self.married_adults if adult.gender == '女' and 20 < adult.age <45]
        for female in females:
            if random.random() < 0.1:
                name,gender = RandomUtil().random_name_str()
                id=len(self.characters)+len(self.died_characters)+1
                character = Character(id=id,name=name,age=0,gender=gender,occupation=female.occupation*random.uniform(0.6, 1.5))
                self.characters[id] = character
                self.characters[id].relations["mother"] = female.id
                self.characters[id].relations["father"] = female.relations["spouse"]
                self.characters[female.id].relations["child"] = id
                self.characters[female.relations["spouse"]].relations["child"] = id
                print(name,"birth")
                
    def die(self):
        temp_dict = {}
        for id,character in self.characters.items():
            probability=0
            if character.age > 70:probability = (character.age-70)*0.005
            if random.random() < 0.001 + probability:
                print(character.name,"die")
                character.die()
                if "spouse" in character.relations:
                    spouse = character.relations["spouse"]
                    self.characters[spouse].relations["former_spouse"] = []
                    self.characters[spouse].relations["former_spouse"].append(self.characters[spouse].relations.pop("spouse"))
                temp_dict[id] = character
        self.died_characters.update(temp_dict)
        for id,_ in temp_dict.items():del self.characters[id]
        
                

class SimulationEngine:
    def __init__(self):
        self.conn = database.create_connection()
        self.years = int(re.findall(r'\d+', self.conn.cursor().execute("SELECT * FROM sqlite_sequence;").fetchall()[-1][0])[0])
        
        self.characters=self.create_characters(database.read_sqlite_data(number=self.years,conn=self.conn),database.read_relationships(number=self.years,conn=self.conn))
        self.died_characters={}
        self.view_data()
        #self.run_simulation()
        #self.end_simulation()

    # 创建一个函数来创建多个Character对象
    def create_characters(self,individual_list,relationships_list):
        characters = {}
        for character_data in individual_list:
            if character_data[2] >= 0:
                character = Character(*character_data)
                characters[character.id] = character
        for relation in relationships_list:
            characters[relation['person1_id']-1].relations[relation['relationship_type']] = relation['person2_id']
            characters[relation['person2_id']-1].relations[relation['relationship_type']] = relation['person1_id']
        self.conn.close()
        return characters

    def view_data(self):
        self.visualization_data = {"individual_list": [{"name": character.name,"age": character.age,"gender": character.gender,"wealth": character.occupation} for _,character in self.characters.items()]}
        wealth_distribution = data_statistics.Wealth_distribution_statistics(self.visualization_data)
        # 从字典中提取键和值，分别形成两个列表
        xAxis_data = list(wealth_distribution.keys())
        series_data = list(wealth_distribution.values())
        chart_options = {
            "title": {"text": 'Wealth Distribution'},
            "tooltip": {},
            "legend": {"data": ['Wealth']},
            "xAxis": {'type': 'category',"data": xAxis_data},
            "yAxis": { 'type': 'value'},
            "series": [
                {
                    "name": 'Wealth',
                    "type": "bar",
                    "data": series_data
                }
            ]
        }
        self.visualization_data["chart_options"] = chart_options


    def run_simulation(self):
        """运行模拟的主要循环"""
        print(f'第{self.years}年开始')
        
        # 在这里，你可以设置模拟的周期，例如每年调用一次establish_marriage_relations
        
        for _ in range(10000):  # 假设模拟10年
            print(f"Year: {self.years}")
            event = Event(characters=self.characters,died_characters=self.died_characters)
            self.characters = event.characters
            self.view_data()
            event.establish_marriage_relations()
            event.childbirth()
            event.die()
            for _,character in self.characters.items():character.next_year()
            self.years+=1
            
            print(f"存活：{len(self.characters)}  死亡：{len(self.died_characters)}")
            yield f"data: {json.dumps(self.visualization_data)}\n\n".encode('utf-8')
            time.sleep(1)

            # 在这里，你可以添加其他模拟逻辑，如生孩子、人物老化等
            # ...
            # 你还可以在这里保存模拟的状态，例如每年结束时的数据库快照

    def end_simulation(self):
        """模拟的结束需要的操作"""
        conn = database.create_connection()
        database.initialize_db(number=self.years,conn=conn)

        for character in self.characters:
            person = {
        'name': character.name,
        'age': character.age,
        'gender': character.gender,
        'wealth': character.occupation
    }

            database.insert_character_data(person,number=self.years,conn=conn)
            for relationship_type,id in character.relations.items():
                database.insert_relationship_data(character.id, id, relationship_type,number=self.years,conn=conn)
            
        conn.close()


if __name__ == "__main__":
    engine = SimulationEngine()
    engine.run_simulation()