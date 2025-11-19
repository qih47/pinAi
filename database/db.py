# pinAi/database/db.py
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!"
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)
