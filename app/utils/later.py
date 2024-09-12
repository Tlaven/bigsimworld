from functools import partial

class LaterSet:
    def __init__(self) -> None:
        self.later_set = set()

    def add_later(self, func, *args, **kwargs):
        self.later_set.add(partial(func, *args, **kwargs))

    def run_later(self):
        for func in self.later_set:
            func()
        self.later_set.clear()

    def __len__(self):
        return len(self.later_set)

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