"""
SQLAlchemy declarative base.

Every ORM model in app/models/ inherits from `Base`. Keeping the base in
its own module avoids circular imports: models import `Base` from here,
and elsewhere we can iterate `Base.metadata.tables` for migrations / table
creation without importing every model.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """The root class for all ORM models. Don't add fields here."""
    pass
