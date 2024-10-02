
import bisect




class Surveys:
    def __init__(self, model):
        self.model = model
        self.characters = model.characters

        self.survey_objects = ["wealth", "age"]

    # 筛选信息，重整数据结构
    def filter_data(self):
        self.data = []
        self.characters_num = 0
        for character in self.characters:
            self.data.append([getattr(character, survey_object) for survey_object in self.survey_objects])
            self.characters_num += 1

        return self.data


    def age_distribution(self):
        self.age_distribution_data = {"0-4": 0, "5-9": 0, "10-14": 0, "15-19": 0, "20-24": 0, "25-29": 0, "30-34": 0, "35-39": 0, "40-44": 0, "45-49": 0, 
                                      "50-54": 0, "55-59": 0, "60-64": 0, "65-69": 0, "70-74": 0, "75-79": 0, "80-84": 0, "85-89": 0, "90-94": 0, "95-99": 0, "100+": 0}

        age_boundaries = [0, 4, 9, 14, 19, 24, 29, 34, 39, 44, 49, 54, 59, 64, 69, 74, 79, 84, 89, 94, 99, 100]
        age_labels = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", 
                      "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85-89", "90-94", "95-99", "100+"]
        for _, age in self.data:
            # 使用 bisect 根据年龄找到相应的区间
            index = bisect.bisect_right(age_boundaries, age)
            self.age_distribution_data[age_labels[index]] += 1
        
        return self.age_distribution_data

    def wealth_distribution(self):
        wealths = sorted([individual[0] for individual in self.data])
        # 取前 1% 的财富分布，剩下的分20份, 计算数量按顺序放在字典中
        wealth_mains, wealth_maxs = wealths[:int(self.characters_num*0.01)], wealths[int(self.characters_num*0.01):]
        spacing = wealth_maxs[0] / 20
        self.age_distribution_data = {f"{i*spacing}-{(i + 1) * spacing}" : 0 for i in range(20)}
        wealth_boundaries = [i*spacing for i in range(20)]
        for wealth in wealth_mains:
            index = bisect.bisect_right(wealth_boundaries, wealth)
            self.age_distribution_data[f"{wealth_maxs[index-1]}-{wealth}"] += 1
        self.age_distribution_data[f"{wealth_maxs[0]}+"] = len(wealth_maxs)

        return self.age_distribution_data


        