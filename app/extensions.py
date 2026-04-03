"""Extension singletons — instantiated without an app so they can be imported anywhere."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


limiter = Limiter(key_func=get_remote_address)
flask_session = Session()

# SQLAlchemy engine and session — configured in create_app()
db_engine = None
DbSession = None
