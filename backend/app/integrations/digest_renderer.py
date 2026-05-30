"""
Render a Digest ORM row + its DigestItems into HTML for email + in-app view.

Deliberately tiny — string-based, no Jinja2 template file to lug around.
Frontend Dev 2 owns the proper HTML email template work; this is the
minimum to demonstrate the loop closes (digest generated → email sent →
user receives something they can read).

Mirror endpoint `GET /me/digests/{id}?format=html` uses the same renderer
so what the user reads in-app matches what they got in the email.
"""

from __future__ import annotations

import html as _html

from app.models import Article, Digest, DigestItem


# Minimal inline CSS so it survives email-client mangling. Outlook is the
# canonical reason this can't be a normal stylesheet.
_STYLE = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; color: #1f2328; line-height: 1.5; max-width: 640px; margin: 0 auto; padding: 24px; }
h1 { font-size: 1.4rem; border-bottom: 1px solid #d0d7de; padding-bottom: 8px; }
h2 { font-size: 1.05rem; margin-top: 24px; }
.item { margin-top: 24px; padding-top: 16px; border-top: 1px solid #eaeef2; }
.item:first-of-type { border-top: 0; }
.meta { font-size: 0.85rem; color: #57606a; }
a { color: #0969da; text-decoration: none; }
.footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid #d0d7de; font-size: 0.8rem; color: #57606a; }
""".strip()


def render_html(digest: Digest, items_with_articles: list[tuple[DigestItem, Article]]) -> str:
    """
    Build the HTML body for `digest`.

    `items_with_articles` is pre-joined to avoid lazy-loading inside the
    template — caller fetches once with eager-loaded articles, we render.
    """
    when = digest.generated_at.strftime("%A, %d %B %Y")

    item_blocks: list[str] = []
    for item, article in items_with_articles:
        title = _html.escape(article.title or "(untitled)")
        url = _html.escape(article.url or "#")
        source = _html.escape(article.source.name if article.source else "Source")
        summary = _html.escape(item.summary or "")
        item_blocks.append(
            f"""
            <div class="item">
              <h2><a href="{url}">{title}</a></h2>
              <div class="meta">{source}</div>
              <p>{summary}</p>
            </div>
            """.strip()
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Your digest — {when}</title>
<style>{_STYLE}</style>
</head>
<body>
  <h1>Your tech intelligence digest</h1>
  <div class="meta">{when}</div>
  {"".join(item_blocks) if item_blocks else "<p>No new items this cycle.</p>"}
  <div class="footer">
    You're receiving this because you subscribed in MAI News.
    Manage your preferences at <a href="#">your dashboard</a>.
  </div>
</body>
</html>
""".strip()


def render_subject(digest: Digest, item_count: int) -> str:
    """One-line subject. Kept short — email clients truncate."""
    when = digest.generated_at.strftime("%a %d %b")
    if item_count == 0:
        return f"Your digest — {when} (no new items)"
    return f"Your digest — {when} ({item_count} stor{'y' if item_count == 1 else 'ies'})"
