




class Surveys:
    def __init__(self, model):
        self.model = model
        self.characters = model.characters

        self.survey_objects = ["property", "age"]

    # 筛选信息，重整数据结构
    def filter_data(self):
        self.data = []
        for character in self.characters:


        