import os
from .table import create_table


if not os.path.exists('/db.sqlite3'):
    create_table()
