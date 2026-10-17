# Nexus

> A community-driven forum / Q&A platform.

Nexus lets people create and join communities, share text, link, image, and poll posts, and discuss them in nested comment threads. Voting drives both content ranking (hot/top feeds) and user karma, while follows, direct messages, and notifications keep members connected. Communities are self-governed: creators appoint moderators who manage flairs, handle reports, ban users, and pin posts.

The project is split into two independent applications: a Django REST Framework backend exposing a versioned JSON API (`/api/v1/`) secured with JWT, and a React single-page app that consumes it. Everything runs on PostgreSQL — including full-text search — and ships with Docker images and a production compose stack.

## Features

**Content & Communities**
- Communities with membership roles (admin / moderator / member), icons, and NSFW flags
- Four post kinds: text, link, image (with upload validation), and poll
- Post flairs (per-community, managed by mods), sticky/pinned posts, NSFW tagging
- Nested comment trees with inline replies and `@username` mention autocomplete
- Markdown editor with server-rendered, sanitized preview; links keep only absolute `http(s)`/`mailto`, site-root (`/…`) and `#…` targets (anything else renders as plain text) and always carry `rel="nofollow noopener noreferrer ugc"`
- Post drafts — debounced autosave to localStorage with restore/discard

**Voting & Feeds**
- Up/down voting on posts and comments with optimistic UI and rollback
- User karma (post + comment) kept in sync via signals, plus a `recalculate_karma` management command
- Home feed (joined communities), Following feed, Popular/All feeds for anonymous visitors
- `new` / `top` / `hot` sorting, NSFW filtering, pagination

**Social**
- Follow system with followers/following lists
- Direct messages: conversations, read receipts (✓ / ✓✓), unread counters
- Notifications (comment, reply, mention, follow, DM, mod action) with bell dropdown, inbox page, and 30s polling
- User blocking — cuts DMs and follows both ways, suppresses notifications
- Public user profiles with karma badges, post/comment tabs, and profile editing

**Discovery**
- Full-text search (PostgreSQL `SearchVector` + GIN, ranked with `SearchRank`) across posts, communities, and people
- Trending widgets: most active communities and top posts of the last 24h (cached)
- Karma leaderboard (top users, cached)
- Server-rendered Open Graph pages so shared links unfurl in Discord/WhatsApp/Twitter

**Moderation**
- Generic reporting (posts, comments, users) with a 24h per-target rate limit
- Mod panel: report queue (resolve/dismiss), community bans, moderator assignment, pin/remove actions
- Community settings editable by admins: icon, description, NSFW flag
- AutoMod: per-community keyword list that holds matching posts for approval
- Mod action audit log — every pin, ban, approval, and report decision is recorded

**Platform**
- JWT auth (SimpleJWT) with refresh rotation and blacklist, register/login/logout
- Password reset and email verification flows (console backend in dev, SMTP via env)
- Account settings: NSFW preference, password change, account deactivation
- Interface language picker (EN/TR via i18next); Turkish coverage is partial, full coverage is tracked for M6
- Uploaded images are automatically downscaled (avatars 512px, post images 1920px)
- Rate throttling per scope (auth, write, vote), pagination, and permission classes throughout

## Tech Stack

| Layer    | Technology |
|----------|------------|
| Backend  | Python, Django, Django REST Framework, SimpleJWT |
| Database | PostgreSQL (full-text search, GIN indexes) |
| Frontend | React 19 (Vite, TypeScript), React Router, Redux Toolkit, TailwindCSS 4 |
| Testing  | pytest + pytest-cov (backend), Vitest + React Testing Library (frontend) |
| Tooling  | ruff (lint + format), ESLint |
| Deploy   | Docker (gunicorn + WhiteNoise, nginx SPA + API proxy), docker-compose |

## Project Structure

```
backend/    Django project — config/ (settings, urls) + apps/ (users, communities,
            posts, comments, votes, messaging, notifications, social, polls,
            saves, moderation, search, seo, common)
frontend/   React SPA — src/ (api, app, components, features, i18n, lib, pages, router)
```

## Getting Started

Requirements: Python 3.12+, Node 22+, Docker (or a local PostgreSQL 16).

```bash
# Database
docker compose up -d          # starts PostgreSQL on :5432

# Backend — http://localhost:8000
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt   # runtime deps + pytest/ruff; the Docker image installs requirements.txt only
cp .env.example .env          # fill in values
python manage.py migrate
python manage.py seed              # optional: demo users/communities/posts (login: any user / password123)
python manage.py runserver

# Frontend — http://localhost:5173
cd frontend
npm install
cp .env.example .env          # VITE_API_URL
npm run dev
```

## Tests & Linting

```bash
# Backend
cd backend
pytest                        # full suite with coverage
ruff check . && ruff format --check .

# Frontend
cd frontend
npm run test                  # vitest
npm run lint                  # eslint
npm run build                 # tsc -b && vite build
```

## Production

A production-ish stack (Postgres + Redis + gunicorn backend + nginx frontend with API/media proxy) is provided. Redis backs the shared cache and throttle counters, Sentry activates when `SENTRY_DSN` is set, and nginx routes crawler user-agents to the OG endpoints:

```bash
cp .env.prod.example .env     # set real secrets
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

- **`SECRET_KEY`** must be at least 50 characters; the backend refuses to start otherwise. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(50))"`.
- **Logging:** the backend logs to stdout at `LOG_LEVEL` (default `INFO`).
- **Health:** `GET /api/v1/health/` returns `200 {"status":"ok"}` or `503 {"status":"unavailable"}` (no auth, exempt from the HTTPS redirect). The compose backend healthcheck uses it with `Host: backend`, so keep `backend` in `ALLOWED_HOSTS`; the frontend container waits for a healthy backend. Redis is capped at 128 MB with LRU eviction.
- **Security headers:** nginx sends a CSP (Google Fonts allowed), `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy` and `Permissions-Policy` (`frontend/nginx/security-headers.conf`). A split deploy with a different API origin must extend `connect-src`.
- **TLS and proxies:** TLS is expected to be terminated by an edge proxy in front of nginx (`SECURE_SSL_REDIRECT` env). The edge proxy must overwrite (not append to) `X-Forwarded-Proto`, and `NUM_PROXIES` must equal the number of proxies in front of Django: nginx (1) plus every proxy before it.

## License

MIT — see [LICENSE](./LICENSE).
