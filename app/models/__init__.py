import os
from .table import create_table


if not os.path.relpath('bigsimworld/db.sqlite3'):
    create_table()
