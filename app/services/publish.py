from threading import Thread
import time
from flask_sse import sse



# Thread function to push real-time time with millisecond precision
def publish_time(app, content):
    time.sleep(3)  # 等待 1 秒，确保 SSE 连接成功
    with app.app_context():
        while True:
            print(content)
            content = content.get('simulation_step/s')
            sse.publish({"time1": content}, type='data')
            print(content)
            time.sleep(1)  # 每 100 毫秒推送一次

def thread_publish(app, content):
    # 启动后台线程
    thread = Thread(target=publish_time, args=(app, content))
    thread.daemon = True  # 设置为守护线程，主程序退出时线程也退出
    thread.start()