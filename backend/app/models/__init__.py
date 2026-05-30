"""
Re-export ORM models so callers can do:

    from app.models import User, Preferences, Article, ...

And so `Base.metadata.create_all()` sees every model (imports here register
the tables on the metadata object).
"""

from app.models.chat import ChatSession, ChatTurn
from app.models.content import Article, ArticleTag, Source, Tag
from app.models.digest import Digest, DigestItem, Feedback
from app.models.kv_state import KvState
from app.models.user import Preferences, User

__all__ = [
    "User",
    "Preferences",
    "Tag",
    "Source",
    "Article",
    "ArticleTag",
    "Digest",
    "DigestItem",
    "Feedback",
    "ChatSession",
    "ChatTurn",
    "KvState",
]
