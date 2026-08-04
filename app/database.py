from sqlalchemy import URL, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker 
from config import (
    PSQL_USER,
    PSQL_PW,
    PSQL_HOST,
    PSQL_PORT,
    PSQL_DATABASE,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_DATABASE,
)

class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


url_pg = URL.create(
    drivername="postgresql+psycopg",
    username=PSQL_USER,
    password=PSQL_PW,
    host=PSQL_HOST,
    port=PSQL_PORT,
    database=PSQL_DATABASE,
)

engine_pg = create_engine(url_pg)
PgSession = sessionmaker(engine_pg)


url_mysql = URL.create(
    drivername="mysql+pymysql",
    username=MYSQL_USER,
    password=MYSQL_PASSWORD,
    host=MYSQL_HOST,
    port=int(MYSQL_PORT),
    database=MYSQL_DATABASE,
)

engine_mysql = create_engine(url_mysql)
MySQLSession = sessionmaker(engine_mysql)
