from collections import deque

class ExecutionQueue:
    def __init__(self):
        self.execution_queue = deque()

    def enqueue(self, command):
        # 将命令（lambda 表达式或函数）添加到队列
        self.execution_queue.append(command)

    def execute_queued_commands(self):
        # 执行队列中的所有命令
        while self.execution_queue:
            command = self.execution_queue.popleft()
            command()

if __name__ == "__main__":
    # 创建 ExecutionQueue 实例
    execution_queue = ExecutionQueue()

    # 初始化一个空字典
    my_dict = {}

    # 使用 lambda 表达式添加键值对到字典中
    execution_queue.enqueue(lambda: my_dict.update({'key1': 'value1'}))
    execution_queue.enqueue(lambda: my_dict.update({'key2': 'value2'}))

    # 执行所有命令
    execution_queue.execute_queued_commands()

    # 查看结果
    print(my_dict)
