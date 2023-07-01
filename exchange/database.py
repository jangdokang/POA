import sqlite3
import traceback
import os
from pathlib import Path

current_file_direcotry = os.path.dirname(os.path.realpath(__file__))
parent_directory = Path(current_file_direcotry).parent

class Database:
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, database_url: str = f"{parent_directory}/store.db"):
        cls = type(self)
        if not hasattr(cls, "_init"):
            self.database_url = database_url
            self.con = sqlite3.connect(self.database_url)
            self.cursor = self.con.cursor()
            cls._init = True

    def close(self):
        self.con.close()

    def excute(self, query: str, value: dict | tuple):
        self.cursor.execute(query, value)
        self.con.commit()

    def excute_many(self, query: str, values: list[dict | tuple]):
        self.cursor.executemany(query, values)
        self.con.commit()

    def fetch_one(self, query: str, value: dict | tuple):
        self.cursor.execute(query, value)
        return self.cursor.fetchone()

    def fetch_all(self, query: str, value: dict | tuple):
        self.cursor.execute(query, value)
        return self.cursor.fetchall()

    def set_auth(self, exchange, access_token, access_token_token_expired):
        query = """
        INSERT INTO auth (exchange, access_token, access_token_token_expired)
        VALUES (:exchange, :access_token, :access_token_token_expired)
        ON CONFLICT(exchange) DO UPDATE SET
        access_token=excluded.access_token,
        access_token_token_expired=excluded.access_token_token_expired;
        """
        return self.excute(query, {"exchange": exchange, "access_token": access_token, "access_token_token_expired": access_token_token_expired})

    def get_auth(self, exchange):
        query = """
        SELECT access_token, access_token_token_expired FROM auth WHERE exchange = :exchange;
        """
        return self.fetch_one(query, {"exchange": exchange})

    def clear_auth(self):
        self.set_auth("KIS1", "nothing", "nothing")
        self.set_auth("KIS2", "nothing", "nothing")
        self.set_auth("KIS3", "nothing", "nothing")
        self.set_auth("KIS4", "nothing", "nothing")

    def init_db(self):
        query = """
        CREATE TABLE IF NOT EXISTS auth (
            exchange TEXT PRIMARY KEY,
            access_token TEXT,
            access_token_token_expired TEXT
        );
        """
        self.excute(query, {})
        # self.clear_auth()


db = Database()
# print(os.path.realpath(__file__))
# print(os.getcwd())
# print(os.path.dirname(os.path.realpath(__file__)))
try:
    db.init_db()
except Exception as e:
    print(traceback.format_exc())
