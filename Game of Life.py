import random
from mesa import Model, Agent
from mesa.space import MultiGrid
from mesa.time import SimultaneousActivation

class LifeAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.alive = random.choice([True, False])

    def step(self):
        live_neighbors = self.count_live_neighbors()
        if self.alive:
            if live_neighbors < 2 or live_neighbors > 3:
                self.alive = False
        else:
            if live_neighbors == 3:
                self.alive = True

    def count_live_neighbors(self):
        live_neighbors = 0
        for neighbor in self.model.grid.iter_neighbors(self.pos, moore=True):
            if neighbor.alive:
                live_neighbors += 1
        return live_neighbors

class LifeModel(Model):
    def __init__(self, width, height):
        self.grid = MultiGrid(width, height, torus=True)
        self.schedule = SimultaneousActivation(self)
        for x in range(width):
            for y in range(height):
                a = LifeAgent((x, y), self)
                self.grid.place_agent(a, (x, y))
                self.schedule.add(a)

    def step(self):
        self.schedule.step()

# 创建一个10x10的生命游戏模型
model = LifeModel(10, 10)

# 运行模型10个步骤
for i in range(10):
    model.step()
    print(f"Step {i+1}:")
    for agent in model.schedule.agents:
        if agent.alive:
            print("O", end=" ")
        else:
            print(".", end=" ")
        if agent.pos[1] >= model.grid.width - 1:
            print()

