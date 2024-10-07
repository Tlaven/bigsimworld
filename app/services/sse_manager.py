# sse_manager.py
from flask_sse import sse
import time

from app.utils.cache import py_cache

class SSEManager:
    def __init__(self):
        self.clients = {}

    def subscribe(self, client_id):
        """订阅客户端"""
        if client_id not in self.clients:
            self.clients[client_id] = {'subscribe_time': time.time()}  # 存储该客户端的订阅信息

    def unsubscribe(self, client_id):
        """取消订阅客户端"""
        if client_id in self.clients:
            del self.clients[client_id]

    def publish(self, data, type='data', client_id=None):
        """发布数据到客户端"""
        try:
            if client_id:
                if self.clients.get(client_id):  # 该客户端已订阅
                    # 检查客户端是否在 30 秒内活跃
                    if self.clients[client_id]['subscribe_time'] + 30 < time.time():
                        self.unsubscribe(client_id)
                    else:
                        sse.publish(data, type=type, channel=client_id)
            else:
                for client in self.clients:
                    sse.publish(data, type=type, channel=client)
        except Exception as e:
            print(f"Error publishing data to client {client_id}: {e}")

    def send_initial_data(self, client_id):
        """发送初始数据给特定客户端"""
        data = py_cache.get("survey_data")
        self.publish(data, type='initial_data', client_id=client_id)

    def send_keepalive(self, client_id):
        """发送保持连接的通知"""
        if client_id in self.clients:
            self.clients[client_id]['subscribe_time'] = time.time()  # 更新客户端的订阅时间
            self.publish({'status': 'keepalive'}, type='keepalive', client_id=client_id)  # 可选的保持连接消息


sse_manager = SSEManager()
