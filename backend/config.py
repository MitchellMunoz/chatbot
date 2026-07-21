from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, URL

load_dotenv()
PSQL_USER = os.getenv("PSQL_USER")
PSQL_PW = os.getenv("PSQL_PW")
PSQL_HOST = os.getenv("PSQL_HOST")
PSQL_DATABASE = os.getenv("PSQL_DATABASE")
PSQL_PORT = int(os.getenv("PSQL_PORT"))

MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
MYSQL_PORT = os.getenv("MYSQL_PORT")
