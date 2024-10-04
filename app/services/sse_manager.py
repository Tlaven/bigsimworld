# sse_manager.py
from flask_sse import sse
import time

from app.utils.cache import py_cache


class SSEManager:
    def __init__(self):
        self.clients = {}

    def subscribe(self, client_id):
        if client_id not in self.clients:
            self.clients[client_id] = []  # 存储该客户端的订阅信息

    def unsubscribe(self, client_id):
        if client_id in self.clients:
            del self.clients[client_id]
            print(f"client {client_id} unsubscribed")

    def publish(self, data,type='data', client_id=None):
        if client_id:
            sse.publish(data, type=type, channel=client_id)
        else:
            for client in self.clients:
                sse.publish(data, type=type, channel=client)

    def send_initial_data(self, client_id):
        data = py_cache.get("survey_data")
        self.publish(data, type='initial_data', client_id=client_id)
        print(data)


sse_manager = SSEManager()
