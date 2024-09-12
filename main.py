# from app.core.generation.human import generate_character, generate_characters
# from app.models.crud import insert_multiple_characters



# if __name__ == '__main__':
#     characters = generate_characters(100000)
#     insert_multiple_characters(characters)

from multiprocessing import Queue

q = Queue()

q.put('hello')

from app.models.processing import ProcessingDB

p = ProcessingDB()
p.daemon = True
p.start()

class DBQueue:
    def __init__(self):
        self.q = Queue()
        self.p = ProcessingDB()
        print('DBQueue started')
        self.p.db_insert_queue.put(1)

DBQueue()
