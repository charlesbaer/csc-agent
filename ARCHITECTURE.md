# CSC Agent — Architecture

## 1. The Key Design Question: Prompt Stuffing Wins

**Decision: Prompt stuffing with Anthropic prompt caching (no vector database).**

The CSC website is a small community club site. A full crawl of communityswimclub.com plus recent Facebook page posts will produce somewhere between 5,000 and 30,000 tokens of content — well under Claude's 200K context window.

Reasons this beats full RAG at this scale:

- **No vector database to run, pay for, or maintain.** ChromaDB needs to be hosted somewhere; pgvector needs a Postgres instance. Neither is free at any meaningful reliability level.
- **No embeddings pipeline.** The infrastructure to generate, store, search, and serve embeddings is real ongoing complexity for no gain when the entire knowledge base fits in a context window.
- **Prompt caching makes it nearly free.** Anthropic caches system prompt blocks marked with `cache_control`. Cache read cost is ~10% of normal input token cost. At 500 messages/month with a ~25K-token cached knowledge block, the effective cost is fractions of a cent per message.
- **Full context is always available.** RAG retrieval can miss. With prompt stuffing, Claude sees everything and can synthesize across topics (e.g., "what's open on Labor Day?" touching pool hours, snack bar, and events simultaneously).
- **The escape valve is clear.** If the site grows past ~100K tokens of content, switching to RAG means swapping the knowledge injection mechanism in `agent.py` — not the whole architecture.

The one real risk is staleness: cached prompt blocks have a TTL of ~1 hour, so responses could be up to 1 hour stale after a nightly re-crawl. For a swim club, this is completely acceptable.

---

## 2. System Overview

```
                    ┌──────────────────────────────────────────────┐
                    │              EXTERNAL SYSTEMS                 │
                    │                                               │
                    │  communityswimclub.com  facebook.com/csc     │
                    └──────────────┬─────────────────┬─────────────┘
                                   │ nightly crawl   │ nightly crawl
                                   ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CSC AGENT SERVER                                 │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  SCHEDULER  (APScheduler, nightly 2am)                                 │ │
│  │                                                                         │ │
│  │  crawler.py ──► facebook.py ──► knowledge_builder.py ──► knowledge.md  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                    │                         │
│                                                    │ loads at startup        │
│                                                    ▼                         │
│  ┌─────────────────────┐    ┌────────────────────────────────────────────┐  │
│  │  WEBHOOK ADAPTER    │    │  AGENT CORE                                │  │
│  │  (Messenger)        │    │                                            │  │
│  │                     │    │  ┌──────────────────────────────────────┐  │  │
│  │  POST /webhook  ─────────►  │  agent.py                            │  │  │
│  │  GET  /webhook  ────────►│  │  build_system_prompt()               │  │  │
│  │  (verify)           │    │  │  call_claude() ──────────────────────┼──┼──► Anthropic API
│  │                     │    │  │  handle_escalation()                 │  │  │  (Claude Haiku)
│  │  messenger.py       │    │  └──────────────────────────────────────┘  │  │
│  └─────────────────────┘    └─────────────▲──────────────────────────────┘  │
│                                            │                                  │
│  ┌─────────────────────┐                  │                                  │
│  │  WIDGET ADAPTER     │                  │                                  │
│  │  (Website chat)     │                  │                                  │
│  │                     │                  │                                  │
│  │  GET  /widget   ──► chat page (iframe) │                                  │
│  │  POST /chat     ─────────────────────────┘                                │
│  │  (rate-limited per IP)                                                    │
│  │  widget.py          │                                                     │
│  └──────────┬──────────┘                                                     │
│             │                                                                 │
│             ▼                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  SQLITE  (message_log.db)                                            │   │
│  │  dedup / idempotency store + conversation log                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
         │
         │ traces + scores
         ▼
  ┌─────────────┐
  │  Langfuse   │
  │  (cloud,    │
  │  free tier) │
  └──────┬──────┘
         │
         │ CI eval runs
         ▼
  ┌─────────────────────┐
  │  GitHub Actions     │
  │  eval workflow      │
  └─────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Crawler (`src/crawler/`)

Nightly at 2am, fetches all public pages from `communityswimclub.com` via a recursive HTTP crawl (following internal links), and fetches recent posts from the Facebook page via the Graph API's `/page/feed` endpoint. Converts HTML to clean markdown via `html2text`. Writes results to `data/knowledge.md`.

**Key decisions:**
- Start URLs are configured in `config.py`, not hardcoded.
- Facebook scraping uses a long-lived Page Access Token generated once by the secretary. If the token expires, the crawler logs a warning and proceeds with website-only content.
- The output `data/knowledge.md` is written only when content has changed (diff check before write), giving a free audit trail via git.

### 3.2 Knowledge Builder (`src/crawler/knowledge_builder.py`)

Takes raw crawled content, normalizes it (deduplicates near-identical sections, enforces source priority — website beats Facebook), and merges in any manually curated content from `overrides/`. Writes the final `data/knowledge.md` and `data/knowledge_meta.json` (crawl timestamp, source URLs, byte count).

### 3.3 Agent Core (`src/agent/`)

The heart of the system. Receives a normalized `Message` dataclass from any adapter, builds the system prompt (knowledge block + instructions + board contacts + escalation rules), calls the Anthropic API with `cache_control` on the knowledge block, and returns a normalized `Response` dataclass.

**Claude call structure:**
```
system: [
  { "text": STATIC_INSTRUCTIONS, "cache_control": {"type": "ephemeral"} },
  { "text": knowledge_block,      "cache_control": {"type": "ephemeral"} }
]
messages: [
  { "role": "user", "content": member_message }
]
```

Two cache breakpoints allow Claude to cache instructions and knowledge separately. Instructions never change mid-day; the knowledge block is refreshed in memory after each nightly crawl without a server restart.

**Model:** `claude-haiku-4-5` for all queries in v1. No automatic Sonnet fallback — not warranted at 500 messages/month. If Haiku returns an escalation response, log it to Langfuse for review.

**Multi-turn history:** `Message.history` is an optional list of prior `{role, content}` turns, prepended to the `messages` array before the current turn. It defaults to empty, so Messenger (which never sets it) is unaffected. The website widget uses it to give Claude context for follow-up questions within a browser session.

### 3.4 Messenger Adapter (`src/adapters/messenger.py`)

Implements the Meta Messenger Webhooks protocol as a Flask blueprint.

- `GET /webhook` — handles the one-time hub verification challenge.
- `POST /webhook` — validates the `X-Hub-Signature-256` HMAC header, checks the SQLite dedup table, returns HTTP 200 immediately, then spawns a background thread to call the agent and deliver the reply via the Send API.

The async-after-200 pattern is essential: Meta expects a response in under 20 seconds and will retry otherwise. Returning 200 before the LLM call prevents retry storms.

**Attachment handling:** Non-text events (stickers, images, voice notes) receive a canned reply: "Hi! I can only read text messages. If you have a question, just type it out and I'll do my best to help."

### 3.5 Website Widget Adapter (`src/adapters/widget.py`)

Implements the embeddable website chat as a Flask blueprint.

- `GET /widget` — serves the chat page (`src/templates/widget/index.html`, styled by `src/static/widget/`). Sets `Content-Security-Policy: frame-ancestors <WIDGET_FRAME_ANCESTORS>` so only approved sites (communityswimclub.com) can embed it in an `<iframe>`.
- `POST /chat` — accepts `{ message, session_id, history }`, validates and bounds the input (message ≤1000 chars, history ≤6 turns), calls `agent.respond()` with `channel=WIDGET`, logs to `conversation_log`, traces to Langfuse, and returns `{ reply, escalated }`.

**Identity:** `session_id` is a random UUID generated client-side and kept only in browser `sessionStorage` — never tied to any account. It is SHA-256-hashed before being used as `sender_id_hash` in the conversation log, mirroring the Messenger PSID-hash pattern.

**Rate limiting:** `flask-limiter`, keyed by client IP (`Fly-Client-IP` header, falling back to `X-Forwarded-For`/`remote_addr`), limits `/chat` to `WIDGET_RATE_LIMIT_PER_MINUTE` and `WIDGET_RATE_LIMIT_PER_DAY` (defaults: 10/min, 150/day), and limits `GET /widget` to `WIDGET_PAGE_RATE_LIMIT_PER_MINUTE` (default: 30/min) to blunt scripted floods of the page itself. In-memory storage is sufficient for the single Fly.io machine. Exceeding either limit returns HTTP 429 with a friendly JSON `reply` the widget displays inline.

**Same-origin by design:** the iframe's `src` is the widget page itself, so the page's `fetch("/chat")` call is same-origin — no CORS configuration is needed. The `frame-ancestors` CSP header is the actual access control, preventing other sites from embedding the widget and running up API costs.

### 3.6 Web Server (`src/server.py`)

Thin Flask app. Mounts:
- `GET/POST /webhook` → Messenger adapter
- `GET /widget`, `POST /chat` → website widget adapter
- `GET /privacy-policy` → serves `docs/privacy-policy.html`
- `GET /health` → returns `{status: ok, knowledge_age_hours: N, knowledge_bytes: N}`

Flask is chosen over FastAPI. The webhook endpoint must return 200 synchronously then do work asynchronously. Flask with a background thread is simpler to reason about than FastAPI's async machinery for this single-endpoint use case.

### 3.7 Scheduler (`src/scheduler.py`)

APScheduler `BackgroundScheduler` runs inside the server process and triggers the nightly crawl at 2am. On crawl completion, reloads the in-memory knowledge block so the running agent picks up fresh content without a restart. No separate cron job or cloud scheduler needed.

### 3.8 SQLite Store (`data/message_log.db`)

Two tables:

- `processed_messages(mid TEXT PRIMARY KEY, processed_at TIMESTAMP)` — idempotency. Check before processing; insert before spawning background task.
- `conversation_log(id, channel, sender_id_hash, message_text, response_text, latency_ms, escalated BOOL, created_at)` — local conversation log for admin review. `sender_id_hash` is SHA-256 of the PSID (Messenger) or session UUID (website); no raw PII stored.

SQLite is sufficient at 500 messages/month. SQLAlchemy abstracts both SQLite and Postgres, so migration is trivial if traffic ever warrants it.

### 3.9 Langfuse Integration (`src/observability.py`)

Wraps every `agent.respond()` call in a Langfuse trace recording input/output tokens, model, latency, `escalated` flag, and `channel` tag. Online evals: Langfuse is configured to score ~20% of live traces using a Haiku-based judge prompt (accuracy, helpfulness, tone). Offline evals: `evals/run_evals.py` fetches the `csc-golden-set` dataset from Langfuse, runs the agent against each input, scores with the judge prompt, and asserts a minimum pass rate — invoked by GitHub Actions CI.

---

## 4. Data Flow — Incoming Messenger Message

```
1.  Member sends "What are the pool hours?" in Messenger.

2.  Meta POSTs to https://csc-agent.fly.dev/webhook
    with X-Hub-Signature-256 header.

3.  Flask view (messenger.py):
    a. Verifies HMAC signature. Returns 403 if invalid.
    b. Extracts messaging.mid and sender.id from payload.
    c. Checks SQLite processed_messages for mid. If found, returns 200 (dedup).
    d. Inserts mid into processed_messages.
    e. Returns HTTP 200 to Meta immediately.
    f. Spawns background thread with (sender_psid, message_text).

4.  Background thread calls agent.respond(Message(text="...", channel="messenger"))

5.  agent.respond():
    a. Loads knowledge block from memory (refreshed nightly).
    b. Builds messages with cache_control on both system blocks.
    c. Creates Langfuse trace, starts span.
    d. Calls Anthropic API (claude-haiku-4-5). Cache hit on knowledge block.
    e. Checks response for escalation signal.
    f. Ends Langfuse span (tokens, latency, model, escalated flag).
    g. Returns Response(text="We're open Monday–Friday 6am–8pm...", escalated=False)

6.  Background thread:
    a. Logs to conversation_log (hashed sender ID, message, response, latency).
    b. POSTs reply to Meta Send API → delivered to member in Messenger.

7.  Langfuse (async): scores ~20% of traces via online eval job.
```

**Latency budget:**
- HMAC verify + SQLite check: < 50ms
- Claude Haiku with cache hit: 300–800ms
- Meta Send API: 100–200ms
- **End-to-end member wait: ~1–1.5 seconds** (well under 5s requirement)

---

## 5. Tech Stack

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | Anthropic SDK is Python-first; crawling libraries are mature |
| Web framework | Flask 3.x | Dead simple; single webhook endpoint; background thread pattern is clean |
| LLM | claude-haiku-4-5 | Cheapest Anthropic model; fast; capable for FAQ answering with full context |
| Prompt strategy | Prompt stuffing + cache_control | Eliminates vector DB; see Section 1 |
| Crawler | requests + beautifulsoup4 + html2text | No JS rendering needed for a static club site |
| Scheduling | APScheduler (in-process) | No separate infra; adequate for one nightly job |
| Rate limiting | flask-limiter (in-memory) | Per-IP limits on `/chat`; sufficient for a single Fly.io machine |
| Storage | SQLite via SQLAlchemy | Zero-ops; trivially upgradeable to Postgres |
| Hosting | Fly.io (free tier) | Free single small VM; persistent volume for SQLite; built-in HTTPS |
| LLM observability | Langfuse cloud (free tier) | Purpose-built for LLM tracing; covers online evals, offline datasets, cost tracking |
| CI | GitHub Actions | Free; used for offline eval gating |
| Secrets | Fly.io secrets | Encrypted at rest; injected as env vars |
| Tunnel (local dev) | ngrok | Industry standard for webhook development; free tier sufficient |
| Dependency management | uv + pyproject.toml | Fast, modern Python packaging; reproducible lockfile |

---

## 6. Project Directory Structure

```
csc-agent/
├── pyproject.toml              # dependencies, project metadata
├── uv.lock                     # lockfile (committed)
├── .env.example                # template for required env vars (no secrets)
├── .gitignore
├── fly.toml                    # Fly.io deployment config
├── Dockerfile
├── REQUIREMENTS.md
├── ARCHITECTURE.md
│
├── data/
│   ├── knowledge.md            # built nightly by crawler (gitignored; on Fly persistent volume)
│   ├── knowledge_meta.json     # crawl timestamp, source URLs, byte count (gitignored)
│   └── message_log.db          # SQLite (gitignored; on Fly persistent volume)
│
├── overrides/
│   ├── board.md                # manually curated board contacts; always authoritative
│   └── social.md                # manually curated social calendar; always authoritative
│
├── src/
│   ├── config.py               # all config read from env vars; typed dataclass
│   ├── server.py               # Flask app factory; mounts adapters; health endpoint
│   ├── scheduler.py            # APScheduler setup; triggers nightly crawl
│   │
│   ├── agent/
│   │   ├── agent.py            # respond(Message) -> Response; LLM call + caching
│   │   ├── prompts.py          # system prompt templates
│   │   └── types.py            # Message, Response dataclasses; Channel enum
│   │
│   ├── adapters/
│   │   ├── messenger.py        # Flask blueprint; GET+POST /webhook
│   │   └── widget.py           # Flask blueprint; GET /widget, POST /chat, rate limiting
│   │
│   ├── templates/widget/
│   │   └── index.html          # Chat widget page (Jinja)
│   │
│   ├── static/widget/
│   │   ├── style.css           # Chat widget styling
│   │   └── chat.js             # Chat widget client logic
│   │
│   ├── crawler/
│   │   ├── crawler.py          # HTTP crawler; follows internal links
│   │   ├── facebook.py         # Graph API feed fetcher
│   │   └── knowledge_builder.py# merge, dedupe, write knowledge.md
│   │
│   └── observability.py        # Langfuse client wrapper; trace/span helpers
│
├── evals/
│   ├── golden_set.json         # golden Q&A pairs (source of truth; also in Langfuse)
│   ├── judge_prompt.txt        # LLM-as-judge prompt for eval scoring
│   └── run_evals.py            # CI script: fetch dataset, run agent, score, assert
│
├── scripts/
│   ├── crawl.py                # one-shot crawler: python scripts/crawl.py
│   └── seed_langfuse.py        # uploads golden_set.json to Langfuse dataset
│
└── .github/
    └── workflows/
        ├── ci.yml              # lint + type check + tests on every PR
        └── evals.yml           # offline evals on PRs touching src/ or data/
```

---

## 7. Deployment

### Production (Fly.io)

```bash
# One-time setup
fly launch --name csc-agent --region iad
fly volumes create csc_data --size 1    # 1GB persistent volume for SQLite

# Secrets (set once; Fly encrypts and injects as env vars)
fly secrets set \
  ANTHROPIC_API_KEY=sk-ant-... \
  MESSENGER_VERIFY_TOKEN=your-random-token \
  MESSENGER_APP_SECRET=your-app-secret \
  MESSENGER_PAGE_ACCESS_TOKEN=your-page-token \
  FACEBOOK_PAGE_ACCESS_TOKEN=your-graph-token \
  LANGFUSE_PUBLIC_KEY=pk-lf-... \
  LANGFUSE_SECRET_KEY=sk-lf-...

# Deploy
fly deploy
```

`fly.toml` mounts the persistent volume at `/data` so SQLite and `knowledge.md` survive deploys. One gunicorn worker with `--threads 4` handles the Flask server + background threads. Memory usage will be well under Fly's free 256MB limit.

### Local Development

```bash
# Install dependencies
uv sync

# Copy and populate secrets
cp .env.example .env

# Start ngrok tunnel (in a separate terminal)
ngrok http 5000
# Set the https://xxxx.ngrok.io/webhook URL in Meta Developer Console
# Note: only one webhook active at a time — coordinate with team

# Run the server
uv run flask --app src.server run --debug --port 5000

# Populate knowledge base
uv run python scripts/crawl.py

# Run evals
uv run python evals/run_evals.py
```

### Environment Variables (`.env.example`)

```
ANTHROPIC_API_KEY=
MESSENGER_VERIFY_TOKEN=
MESSENGER_APP_SECRET=
MESSENGER_PAGE_ACCESS_TOKEN=
FACEBOOK_PAGE_ACCESS_TOKEN=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
CRAWL_SCHEDULE_HOUR=2
CRAWL_SCHEDULE_MINUTE=0
WIDGET_RATE_LIMIT_PER_MINUTE=10
WIDGET_RATE_LIMIT_PER_DAY=150
WIDGET_PAGE_RATE_LIMIT_PER_MINUTE=30
WIDGET_FRAME_ANCESTORS=https://communityswimclub.com https://www.communityswimclub.com
PRIVACY_POLICY_URL=/privacy-policy
LOG_LEVEL=INFO
```

---

## 8. Cost Estimate — 500 Messages/Month

Assumptions: 15-token average user message, 25K-token cached knowledge block, 150-token average response, ~95% cache hit rate.

**Claude Haiku pricing:**
- Cache read: $0.08/MTok → 25K tokens = $0.002/message
- Output: $4.00/MTok → 150 tokens = $0.0006/message
- **Per message: ~$0.0026**

| Item | Monthly cost |
|---|---|
| LLM (500 messages × $0.0026) | ~$1.30 |
| Langfuse online evals (100 judge calls) | ~$0.30 |
| Fly.io hosting | $0 (free tier) |
| Langfuse cloud | $0 (free tier) |
| GitHub Actions | $0 (free tier) |
| **Total** | **~$1.60/month** |

At 10× traffic (5,000 messages/month), total cost remains under $15/month.

---

## 9. Future Extension Points

### Website Widget Adapter — Implemented

See [3.5](#35-website-widget-adapter-srcadapterswidgetpy). `POST /chat` request/response shape:

```json
Request:  { "message": "...", "session_id": "...", "history": [{"role": "user", "content": "..."}, ...] }
Response: { "reply": "...", "escalated": false }
```

### Adding a New Knowledge Source

If the club adds a Google Doc or PDF FAQ, add a new fetcher in `src/crawler/` that outputs markdown, then merge it in `knowledge_builder.py`. The agent sees it automatically on the next crawl with no other changes.

---

## 10. Implementation Sequence

Build in this order — each step is independently testable before the next begins:

1. `src/config.py` and `src/agent/types.py` — establish contracts everything else depends on
2. `src/crawler/` — populate `data/knowledge.md`; verify content fits in context window
3. `src/agent/agent.py` + `src/agent/prompts.py` — build and test LLM logic in isolation (no web server); write first golden Q&A pairs
4. `evals/` — set up Langfuse, upload golden set, wire `run_evals.py`; get CI green
5. `src/server.py` + `src/adapters/messenger.py` — add webhook; test locally with ngrok
6. `src/scheduler.py` — add nightly crawl schedule
7. `src/observability.py` — wrap agent calls with Langfuse tracing
8. Fly.io deploy — production
9. `src/adapters/widget.py` + `src/templates/widget/` + `src/static/widget/` — embeddable website chat, rate-limited per IP
