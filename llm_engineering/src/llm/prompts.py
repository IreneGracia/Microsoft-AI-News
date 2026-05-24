"""
All system prompts and prompt-building functions live here.

Design principles:
- System prompts are stable → cache them (prompt cache hit = 90% cost reduction)
- User messages carry the variable context (articles, query)
- Every answer must cite its source — enforced in the prompt
- Tone adapts to user profile (executive vs technical)
"""
from __future__ import annotations

from src.models import Article, UserProfile, TonePreference, DigestArticle


# ---------------------------------------------------------------------------
# Newsletter generation
# ---------------------------------------------------------------------------

NEWSLETTER_SYSTEM_PROMPT = """You are MAI — Microsoft's AI-powered Tech Intelligence assistant.
Your job is to write personalized tech news digests for Microsoft employees.

RULES — follow every one without exception:
1. Every claim must be followed by an inline citation: [Source Name](URL)
2. Never invent facts. If the article doesn't say it, don't write it.
3. Be concise: each article summary is 2–3 sentences maximum.
4. Rank articles by business relevance to the reader's role and interests.
5. No filler phrases ("In today's fast-paced world...", "As we all know...").
6. No SEO-style repetition. One key insight per article.
7. If multiple articles cover the same story, say so and summarize once.
8. Output valid JSON matching the schema provided in the user message.
"""

NEWSLETTER_EXECUTIVE_ADDENDUM = """
TONE: Executive/Strategic. Assume the reader is a senior decision-maker.
- Lead with business impact and strategic implications.
- Skip implementation details unless they affect strategy.
- Use plain English, no acronyms without explanation.
"""

NEWSLETTER_TECHNICAL_ADDENDUM = """
TONE: Technical. Assume the reader is an engineer or technical PM.
- Include technical specifics: model names, API changes, benchmark numbers.
- Highlight implementation considerations and developer impact.
- Acronyms are fine.
"""


def build_newsletter_user_message(
    articles: list[Article],
    user: UserProfile,
    top_n: int = 6,
) -> str:
    tone_note = ""
    if user.tone == TonePreference.EXECUTIVE:
        tone_note = "Write for an executive audience — strategic impact only."
    elif user.tone == TonePreference.TECHNICAL:
        tone_note = "Write for a technical audience — include implementation details."

    articles_block = "\n\n".join(
        f"[ARTICLE {i+1}]\nTitle: {a.title}\nSource: {a.source}\nURL: {a.url}\n"
        f"Published: {a.published_at.strftime('%Y-%m-%d')}\n\nContent:\n{a.content[:800]}"
        for i, a in enumerate(articles)
    )

    return f"""USER PROFILE:
- Name: {user.name}
- Role: {user.role}
- Interests: {', '.join(i.value for i in user.interests)}
- Companies tracking: {', '.join(user.companies_to_track) or 'None specified'}
- {tone_note}

TASK:
1. Select the {top_n} most relevant articles for this user from the list below.
2. Rank them from most to least relevant (rank 1 = most important).
3. For each, write a 2-3 sentence personalized summary with inline citations.
4. Write a 1-sentence personalized intro for the digest.

Return a JSON object with this exact schema:
{{
  "intro": "<personalized opening>",
  "articles": [
    {{
      "rank": 1,
      "title": "<original title>",
      "url": "<original url>",
      "source": "<source name>",
      "summary": "<2-3 sentence summary with inline citation>",
      "reason": "<1 sentence: why this is relevant to this user>"
    }},
    ...
  ]
}}

ARTICLES TO PROCESS:
{articles_block}
"""


def build_newsletter_system_prompt(user: UserProfile) -> str:
    base = NEWSLETTER_SYSTEM_PROMPT
    if user.tone == TonePreference.EXECUTIVE:
        return base + NEWSLETTER_EXECUTIVE_ADDENDUM
    elif user.tone == TonePreference.TECHNICAL:
        return base + NEWSLETTER_TECHNICAL_ADDENDUM
    return base


# ---------------------------------------------------------------------------
# Chatbot
# ---------------------------------------------------------------------------

CHATBOT_SYSTEM_PROMPT = """You are MAI — Microsoft's AI Tech Intelligence assistant.
You help Microsoft employees explore and understand the latest technology news.

CAPABILITIES:
- Answer questions about recent tech news grounded in your retrieved context.
- Compare stories, companies, and technologies.
- Explain technical concepts clearly.
- Surface connections between different news items.

RULES — follow every one without exception:
1. Ground every answer in the provided news context. Cite sources inline: [Source](URL).
2. If the context doesn't contain enough information, say so clearly. Do not hallucinate.
3. If asked about something outside the retrieved articles, say you don't have current information on that topic.
4. Be conversational but precise. Prefer bullet points for multi-part answers.
5. When comparing technologies or companies, be balanced and factual.
6. Never express political opinions. Stick to technology facts.
7. Keep answers focused: 3-5 sentences for simple questions, structured lists for complex ones.
"""


def build_chat_user_message(
    query: str,
    retrieved_articles: list[Article],
    conversation_history: list[dict],
) -> str:
    context_block = "\n\n".join(
        f"[{i+1}] {a.title}\nSource: {a.source} | {a.url}\n{a.content[:600]}"
        for i, a in enumerate(retrieved_articles)
    )

    return f"""RETRIEVED CONTEXT (use only these sources for your answer):
{context_block}

USER QUESTION: {query}
"""


def build_chat_messages(
    query: str,
    retrieved_articles: list[Article],
    conversation_history: list[dict],
) -> list[dict]:
    """
    Build the messages array for the chat API call.
    Conversation history is prepended; the new user message contains the retrieved context.
    This means the context is injected fresh each turn — it's always current.
    """
    messages = list(conversation_history)
    messages.append({
        "role": "user",
        "content": build_chat_user_message(query, retrieved_articles, conversation_history),
    })
    return messages
