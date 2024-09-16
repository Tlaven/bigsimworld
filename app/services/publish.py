import time
from flask_sse import sse



def sse_publish(app, content):
    with app.app_context():
        sse.publish(content, type='data')

