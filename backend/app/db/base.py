"""SQLAlchemy declarative base shared by all modules."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models in the platform."""
    pass
