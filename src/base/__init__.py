import os
from .table import create_table


if not os.path.exists('data/characters.db'):
    create_table()
