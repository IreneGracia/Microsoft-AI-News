# Feature → Endpoint Map

## F1 — Employee registration

User signs in with their Microsoft identity; the backend provisions a `User` row on first login. Built against any Entra ID tenant — for development this can be a **free standalone tenant** created from [entra.microsoft.com](https://entra.microsoft.com) (no Azure subscription, no credit card; see [backend/.env.example](../backend/.env.example) for setup steps).

| Method | Path | What it does |
|---|---|---|
| `GET` | `/auth/login` | Starts the OAuth 2.0 / OIDC flow. Generates a CSRF `state` and a PKCE `code_verifier`, stashes both in HttpOnly cookies (path `/api/v1/auth`, 10-min TTL), and `302`-redirects the browser to Entra's `/authorize`. |
| `GET` | `/auth/callback` | OAuth redirect target. Verifies `state` against the cookie (constant-time compare), exchanges the auth `code` at Entra's `/token` endpoint via MSAL (which validates the ID token signature against Entra's JWKS), provisions the `User` row on first login, mints the app's own JWT, and `302`-redirects to `FRONTEND_URL/#access_token=<jwt>`. The token rides in the URL fragment so it stays out of server access logs. |
| `POST` | `/auth/dev-login` | Dev-only shortcut: provisions a deterministic dev user, seeds demo data, returns `{ access_token, token_type, expires_in, user }` as JSON. Returns `404` when `ENV != dev`. |
| `GET` | `/me` | Returns the authenticated user (id, email, display name). Requires `Authorization: Bearer <jwt>`. Used by the frontend to confirm "am I logged in?" and gate the registration vs. app shell. |

Implementation notes:

- The OAuth flow lives in [backend/app/auth/entra.py](../backend/app/auth/entra.py) (MSAL `ConfidentialClientApplication`) and is wired into the router at [backend/app/routers/auth.py](../backend/app/routers/auth.py).
- The frontend extracts the JWT from the URL fragment on load, stores it (memory or `localStorage`), removes it from the URL via `history.replaceState`, then attaches it as `Authorization: Bearer <jwt>` on every API call.
- The same `User` row shape is used regardless of which login path created it — `entra_oid` is a placeholder UUID for `/auth/dev-login` users, and the real Entra `oid` for real users.

---

## F2 — Preferences UI (topics, tags, sources, frequency, tone, length)

Reads the multi-dimensional tag taxonomy, the source registry, and the user's current preferences; writes new preferences.

| Method | Path | What it does |
|---|---|---|
| `GET` | `/tags` | Gives back the **master list of every label the app uses** — the categories users pick in their preferences and that articles get tagged with. The labels are split into six groups (`topic`, `business`, `regulation_policy`, `regional`, `role`, `seniority`), and this endpoint returns all six in one response. **What you get back:** one JSON object — each key is a group name, each group holds a list of labels, and every label has a `slug` (the short code the app stores, e.g. `artificial_intelligence_ml`) and a `label` (the readable name shown to the user, e.g. `Artificial Intelligence & ML`). Shape: `{ "topic": [ {slug, label}, … ], "business": [ … ], … }`. **What it's used for:** (1) the sign-up and preferences screens call it to build the lists of options the user ticks — the topic chips, the role choices, the region chips, and so on (each screen just reads the group it needs out of the response); (2) it is the list of *allowed* values — when a user saves their preferences the server checks every choice against it, and the data team tags articles using the same slugs. The list almost never changes (it is loaded from [sources.json](../sources.json) by [seed.py](../backend/app/seed.py) when the app starts), so the response is cached for 24 hours. |
| `GET` | `/sources` | Lists available sources from the registry: `id`, `name`, `category`, `source_type`, `region`, `content_quality`. Powers the source-muting picker in preferences. Optional filters: `?region=`, `?category=`. Backed by [sources.json](../sources.json). |
| `GET` | `/me/preferences` | Returns the caller's current preferences: selected topics, business tags, regulation tags, regions, role, muted sources, frequency, delivery day/hour, tone, length, language. |
| `PUT` | `/me/preferences` | Replaces the caller's preferences. Validates every tag slug against the taxonomy and every source id against the registry; rejects unknown values. |

When the frontend renders the preferences screen it calls **both** `/tags` and `GET /me/preferences`: `/tags` draws every chip (all the options that exist), and `GET /me/preferences` says which of those chips should appear already ticked and what the frequency / tone / length controls should be set to. `/tags` is the list of choices; `GET /me/preferences` is the user's current answers; `PUT /me/preferences` saves new answers.

---

## F3 — Email digest generation

The digest itself is produced by a background worker (not a public endpoint). The API only exposes **reads** of past digests for end users; writes happen via direct DB access from the digest worker (D1).

The worker is triggered on a schedule by an **internal webhook** that lives under `/api/v1/internal/*`. The scheduler is **GitHub Actions cron** ([.github/workflows/digest-cron.yml](../.github/workflows/digest-cron.yml)) — free, no card needed, fires the webhook once a day.

| Method | Path | What it does |
|---|---|---|
| `GET` | `/me/digests` | Lists the caller's past digests, newest first. Cursor-paginated (`?cursor=...&limit=...`). Returns summary metadata only (id, generated_at, item_count). |
| `POST` | `/internal/run-digest-worker` | **Infrastructure-only.** Triggers one run of the digest worker. Authenticated by `Authorization: Bearer <WORKER_SHARED_SECRET>` — not a user JWT. Returns 503 when the secret is unconfigured (closed-by-default). Hidden from OpenAPI (`include_in_schema=False`) so the frontend client doesn't surface it. Called by GitHub Actions cron; idempotent — the worker skips users who already have a digest for today. |

> The worker logic lives in [backend/app/workers/digest_worker.py](../backend/app/workers/digest_worker.py); the webhook entry point is [backend/app/routers/internal.py](../backend/app/routers/internal.py).

---

## F4 — Chatbot: grounded Q&A with citations

Conversational interface for news exploration. Each user message returns an LLM answer with article citations.

| Method | Path | What it does |
|---|---|---|
| `POST` | `/me/sessions` | Starts a brand-new conversation — the "New chat" button. Creates an empty chat session owned by the caller and returns its `session_id`, which the frontend uses in every later message call. |
| `GET` | `/me/sessions` | Lists all of the caller's existing conversations, cursor-paginated. Powers the sidebar of past chats the user switches between. |
| `GET` | `/me/sessions/{session_id}` | Opens one specific conversation — returns the session together with its full message history, so clicking a chat in the sidebar loads the whole back-and-forth. |
| `POST` | `/me/sessions/{session_id}/messages` | Sends a user message; runs retrieval + LLM; returns the assistant reply **with citations** (each citation has `article_id`, title, source, url). This is the core grounded-answer endpoint. |
| `GET` | `/me/sessions/{session_id}/messages` | Fetches a conversation's history in **pages** (cursor-paginated, 50 turns at a time) instead of all at once. Same content as `GET /me/sessions/{id}`, but for very long chats where one big response would be slow — lets the frontend load older messages on demand as the user scrolls up. |
| `DELETE` | `/me/sessions/{session_id}` | Removes a conversation entirely — deletes the session and all its messages together (the user clearing a chat from their sidebar). Messages cascade-delete with the session, so nothing is left orphaned. |

Citations resolve to articles via:

| Method | Path | What it does |
|---|---|---|
| `GET` | `/articles/{article_id}` | Returns the article (title, source, url, published_at, extract). The chatbot UI uses this to expand a citation into a preview card. |
| `GET` | `/articles/{article_id}/source` | Redirects to the **original publisher URL**. Keeps users tied to the source of truth (grounding requirement from the capstone brief). |

---

## F5 — Preferences edit + unsubscribe

Editing prefs uses the same `PUT /me/preferences` as F2. Unsubscribe = stop receiving digests, which today means deleting the account (the worker filters out users with no row). Logout is separate and doesn't affect delivery.

| Method | Path | What it does |
|---|---|---|
| `PUT` | `/me/preferences` | Update preferences (also the path for changing cadence / muting sources). |
| `DELETE` | `/me` | Deletes the caller's account and all dependent rows (sessions, feedback, digests). Returns `204`. |
| `POST` | `/auth/logout` | Returns `204`. Bearer-token auth is stateless, so logout is the frontend forgetting its JWT; the server defensively clears any leftover oauth cookies but holds no per-user session. Does **not** unsubscribe — the user keeps receiving digests until they hit `DELETE /me`. |

---

## F6 — Feedback signal (thumbs up/down) *(maybe — to consider implementation)*

One signal per `(user, digest, article)`. A second POST overwrites the previous signal (idempotent).

| Method | Path | What it does |
|---|---|---|
| `POST` | `/me/digests/{digest_id}/feedback` | Records a thumbs up/down for one article inside one digest. Body: `{ article_id, signal: "up" \| "down" }`. Returns `204`. Validates that the article actually appeared in the digest so feedback can't be forged against unrelated articles. |

---

## Auxiliary endpoints (not feature-mapped)

| Method | Path | What it does |
|---|---|---|
| `GET` | `/health/live` | Liveness probe — returns immediately. For container orchestrator. |
| `GET` | `/health/ready` | Readiness probe — confirms DB is reachable before declaring ready. |

---

## Endpoint summary (one-liner per route)

```
GET    /api/v1/auth/login                              F1   Start SSO
GET    /api/v1/auth/callback                           F1   SSO callback — provisions user on first login
POST   /api/v1/auth/logout                             F5   Clear session cookie
POST   /api/v1/auth/dev-login                          F1   Dev shortcut (disabled in prod)

GET    /api/v1/me                                      F1   Current user
DELETE /api/v1/me                                      F5   Delete account
GET    /api/v1/me/preferences                          F2   Read preferences
PUT    /api/v1/me/preferences                          F2/F5  Update preferences (topics/tags/sources/freq/tone/length)

GET    /api/v1/tags                                    F2   Full multi-dimensional tag taxonomy (drives all preference chips)
GET    /api/v1/sources                                 F2   Source registry (id/name/category/region/source_type)

GET    /api/v1/articles/{id}                           F4   Article detail (for citation expansion)
GET    /api/v1/articles/{id}/source                    F4   Redirect to original publisher URL

GET    /api/v1/me/digests                              F3   List past digests
POST   /api/v1/me/digests/{id}/feedback                F6   Thumbs up/down on one item

POST   /api/v1/me/sessions                             F4   Create chat session
GET    /api/v1/me/sessions                             F4   List chat sessions
GET    /api/v1/me/sessions/{id}                        F4   Get session + history
DELETE /api/v1/me/sessions/{id}                        F4   Delete session
GET    /api/v1/me/sessions/{id}/messages               F4   Paginated message history
POST   /api/v1/me/sessions/{id}/messages               F4   Send message — LLM answer + citations

GET    /api/v1/health/live                             —    Liveness probe
GET    /api/v1/health/ready                            —    Readiness probe

POST   /api/v1/internal/run-digest-worker              F3   [INFRA] Trigger digest worker (shared-secret auth; GH Actions cron)
```
