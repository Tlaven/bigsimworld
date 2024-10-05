from functools import partial
from collections import deque

class LaterDeque:
    """
    使用 deque 实现的延迟任务队列，任务按添加顺序执行。
    """
    
    def __init__(self) -> None:
        self.later_deque = deque()  # 初始化一个 FIFO 队列

    def add_later(self, func, *args, **kwargs):
        """
        添加函数及其参数，使用 partial 封装后存储到队列中。
        """
        self.later_deque.append(partial(func, *args, **kwargs))

    def run_later(self):
        """
        逐个执行队列中的所有函数，直到队列为空。
        """
        while self.later_deque:  # 使用 len() 来检查队列是否为空
            try:
                func = self.later_deque.popleft()  # 从队列左侧获取任务并移除
                func()  # 执行延迟的函数
            except Exception as e:
                print(f"Error executing {func}: {e}")  # 捕获并处理异常

    def __len__(self):
        """返回待执行函数的数量"""
        return len(self.later_deque)  # 使用 len() 来获取队列大小



class ThresholdList(list):
    def __init__(self, threshold, callback, *args):
        super().__init__(*args)
        self.threshold = threshold
        self.callback = callback

    def append(self, object):
        super().append(object)
        if len(self) >= self.threshold:
            self.callback(self)
            self.clear()


if __name__ == '__main__':
    # 定义一个简单的回调函数
    def on_reach_threshold(container):
        print("已达到阈值！", container)
    # 创建一个ThresholdList实例，当元素数量达到5时执行回调函数
    threshold_list = ThresholdList(5, on_reach_threshold)

    # 添加元素
    for i in range(6):
        threshold_list.append(i)