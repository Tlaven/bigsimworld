import bisect

from app.utils.cache import py_cache



class SurveyManager:
    def __init__(self, model):
        self.model = model
        self.characters = model.characters

        self.survey_objects = ["wealth", "age"]

    def run(self):
        self.filter_data()
        age_distribution_data = self.age_distribution()
        wealth_distribution_data = self.wealth_distribution()
        py_cache["survey_data"] = {"age": age_distribution_data, "wealth": wealth_distribution_data}

    # 筛选信息，重整数据结构
    def filter_data(self):
        self.data = []
        self.characters_num = 0
        for character in self.characters.values():
            self.data.append([getattr(character, survey_object) for survey_object in self.survey_objects])
            self.characters_num += 1

        return self.data


    def age_distribution(self):
        age_distribution_data = [0] * 21
        age_boundaries = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
        age_labels = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", 
                      "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85-89", "90-94", "95-99", "100+"]
        for _, age in self.data:
            # 使用 bisect 根据年龄找到相应的区间
            index = bisect.bisect_right(age_boundaries, age)
            age_distribution_data[index] += 1
        
        return [age_labels, age_distribution_data]

    def wealth_distribution(self):
        wealths = sorted([individual[0] for individual in self.data])
        # 取前 1% 的财富分布，剩下的分20份, 计算数量按顺序放在字典中
        wealth_mains, wealth_maxs = wealths[:int(self.characters_num*0.99)], wealths[int(self.characters_num*0.99):]
        spacing = wealth_maxs[0] / 20
        age_distribution_data = [0] * 21
        wealth_boundaries = [i*spacing for i in range(1,21)]
        wealth_labels = [f"{i*spacing}-{(i + 1) * spacing}" for i in range(20)] + [f"{wealth_maxs[0]}+"]
        for wealth in wealth_mains:
            index = bisect.bisect_right(wealth_boundaries, wealth)
            age_distribution_data[index] += 1
        age_distribution_data[-1] += len(wealth_maxs)

        return [wealth_labels, age_distribution_data]


        