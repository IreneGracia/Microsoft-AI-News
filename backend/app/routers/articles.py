"""
/articles/{id} — citation resolution + click-through (docs/api.md §3.6).

`GET /articles/{id}` returns the metadata frontend needs to render a
citation hover/expand. `GET /articles/{id}/source` 302s to the original
URL — we don't proxy article bodies (compliance: we don't host the
content).
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.errors import problem
from app.models import Article, User
from app.models.content import ArticleTag
from app.schemas.content import ArticleOut

router = APIRouter(prefix="/articles", tags=["articles"])


def _to_out(article: Article) -> ArticleOut:
    """Flatten the ORM row + relationships into the wire shape."""
    # Group the multi-dimensional tags by dimension: {dimension: [slug, ...]}.
    tags_by_dim: dict[str, list[str]] = {}
    for t in article.tags:
        tags_by_dim.setdefault(t.dimension, []).append(t.slug)
    return ArticleOut(
        id=article.id,
        title=article.title,
        source=article.source.name if article.source else "",
        url=article.url,
        published_at=article.published_at,
        author=article.author,
        extract=article.extract,
        image_url=article.image_url,
        topics=tags_by_dim.get("topic", []),
        tags=tags_by_dim,
    )


@router.get("", response_model=list[ArticleOut])
def list_articles(
    topics: str | None = Query(default=None, description="Comma-separated topic slugs"),
    limit: int = Query(default=24, ge=1, le=100),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ArticleOut]:
    """
    List recent articles, optionally filtered by topic tags.
    Used by the frontend home screen to show real headlines.
    """
    q = db.query(Article).filter(Article.published_at.isnot(None))

    if topics:
        topic_list = [t.strip() for t in topics.split(",") if t.strip()]
        if topic_list:
            tagged_ids = (
                db.query(ArticleTag.article_id)
                .filter(
                    ArticleTag.dimension == "topic",
                    ArticleTag.slug.in_(topic_list),
                )
                .subquery()
            )
            q = q.filter(Article.id.in_(tagged_ids))

    articles = q.order_by(Article.published_at.desc()).limit(limit).all()
    return [_to_out(a) for a in articles]


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(
    article_id: str,
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ArticleOut:
    article = db.get(Article, article_id)
    if article is None:
        raise problem(status=404, title="Article not found")
    return _to_out(article)


@router.get("/{article_id}/source")
def get_article_source(
    article_id: str,
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    302 to the original URL. Logging the click-through is left to a
    future middleware (it's a ranking signal Data Engineer 2 wants).
    """
    article = db.get(Article, article_id)
    if article is None:
        raise problem(status=404, title="Article not found")
    return RedirectResponse(url=article.url, status_code=302)
