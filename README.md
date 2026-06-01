# CSC Agent

Automated chat assistant for the [Community Swim Club](https://communityswimclub.com). Answers member questions sent to the CommunitySwimClub Facebook Page via Messenger, using a knowledge base built nightly from the club website and Facebook page.

## How it works

- Members message the CommunitySwimClub Facebook Page
- Meta delivers the message to `/webhook` via the Messenger Webhooks API
- The agent answers using Claude (Haiku) with the full club knowledge base injected as a cached system prompt
- Responses are delivered back to the member in Messenger within ~1–2 seconds
- Every conversation is traced in Langfuse for quality monitoring and analytics

The knowledge base is crawled nightly from `communityswimclub.com` and the club's Facebook page, rebuilt into `data/knowledge.md`, and reloaded in memory without a server restart.

## Local development

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), [ngrok](https://ngrok.com)

```bash
# Install dependencies
uv sync

# Configure secrets
cp .env.example .env
# Fill in all values in .env

# Populate the knowledge base
uv run python scripts/crawl.py

# Start the server
uv run flask --app src.server run --debug --port 5000
```

To receive webhook events locally, point Meta at your machine via ngrok:

```bash
ngrok http 5000
# Set https://<your-id>.ngrok.io/webhook as the webhook URL in the Meta Developer Console
# Only one webhook can be active at a time — coordinate with the team
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `MESSENGER_VERIFY_TOKEN` | Yes | Token used to verify the Meta webhook |
| `MESSENGER_APP_SECRET` | Yes | Meta app secret for HMAC signature verification |
| `MESSENGER_PAGE_ACCESS_TOKEN` | Yes | Page access token for sending Messenger replies |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | No | Graph API token for crawling page posts |
| `FACEBOOK_PAGE_ID` | No | Facebook page ID or username (default: `communityswimclub`) |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse public key for observability |
| `LANGFUSE_SECRET_KEY` | No | Langfuse secret key |
| `LANGFUSE_HOST` | No | Langfuse host (default: `https://cloud.langfuse.com`) |
| `CRAWL_SCHEDULE_HOUR` | No | Hour to run nightly crawl, 24h clock (default: `2`) |
| `CRAWL_SCHEDULE_MINUTE` | No | Minute to run nightly crawl (default: `0`) |
| `ANTHROPIC_MODEL` | No | Model override (default: `claude-haiku-4-5`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

## Running evals

Evals compare agent responses against a golden Q&A dataset and score them with an LLM-as-judge. They run automatically in CI on changes to `src/` or `data/`, and can be run locally:

```bash
uv run python evals/run_evals.py
```

To upload the golden dataset to Langfuse (one-time setup):

```bash
uv run python scripts/seed_langfuse.py
```

## Deployment

The app runs on [Fly.io](https://fly.io) with a persistent volume for SQLite and the knowledge base.

```bash
# First-time setup
fly launch --name csc-agent --region iad
fly volumes create csc_data --size 1

# Set secrets (one-time)
fly secrets set \
  ANTHROPIC_API_KEY=sk-ant-... \
  MESSENGER_VERIFY_TOKEN=... \
  MESSENGER_APP_SECRET=... \
  MESSENGER_PAGE_ACCESS_TOKEN=... \
  FACEBOOK_PAGE_ACCESS_TOKEN=... \
  LANGFUSE_PUBLIC_KEY=... \
  LANGFUSE_SECRET_KEY=...

# Deploy
fly deploy
```

Production URL: `https://csc-agent.fly.dev`  
Webhook endpoint: `https://csc-agent.fly.dev/webhook`  
Health check: `https://csc-agent.fly.dev/health`

## Project structure

```
src/
  agent/          # LLM call, system prompt, response types
  adapters/       # Messenger webhook (Phase 2: website widget, Gmail)
  crawler/        # Nightly website + Facebook page crawler
  config.py       # All config from environment variables
  db.py           # SQLite schema (conversation log, dedup store)
  observability.py# Langfuse tracing wrapper
  scheduler.py    # APScheduler: nightly crawl + 12-month data purge
data/
  knowledge.md    # Built nightly by crawler
  overrides/      # Manually curated content; always authoritative
evals/
  golden_set.json # Golden Q&A pairs for offline evals
  run_evals.py    # CI eval runner
docs/
  privacy-policy.html  # Publish at communityswimclub.com/privacy for Meta App Review
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a full breakdown of design decisions, data flow, and cost estimates.
