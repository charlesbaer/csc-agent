# Data Processing & Third-Party Services

This document is for maintainers and club administrators evaluating the
implications of running this assistant. It lists every third-party service
the application sends data to, what data each one receives, and links to
that provider's own terms so you can assess their data handling, retention,
and compliance posture.

(For the member-facing summary, see [`privacy-policy.html`](privacy-policy.html),
served at `/privacy-policy`.)

## Summary

| Service | Role | What it receives |
|---|---|---|
| [Fly.io](#flyio) | Hosting — runs the app server and the persistent volume | Everything: env vars/secrets, conversation logs (message text, response text, hashed sender IDs, timestamps), the crawled knowledge base |
| [Anthropic API](#anthropic-api) | LLM that generates every reply | The crawled knowledge base, conversation history, and the user's message text for each request |
| [Langfuse](#langfuse) | Observability — traces and scores each response | Message text, response text, a pseudonymous user/session ID hash, model name, and token usage |

## Fly.io

The app, its SQLite database (`message_log.db`), and `knowledge.md` all live
on a single Fly.io machine with a persistent volume in the `iad` region. This
means Fly.io has access to everything the application stores or processes —
it is the underlying infrastructure provider, not a sub-processor for a
specific feature.

- [Terms of Service](https://fly.io/legal/terms-of-service/)
- [Privacy Policy](https://fly.io/legal/privacy-policy/)

## Anthropic API

Every `respond()` call (`src/agent/agent.py`) sends three things to the
Anthropic API:

1. The static system instructions (`SYSTEM_INSTRUCTIONS`)
2. The full crawled knowledge base (`knowledge.md` — public club website content)
3. The current message plus up to 6 prior turns of conversation history

Anthropic processes this to generate the response. No data is sent to
Anthropic outside of the synchronous API call made for each user message.

- [Commercial Terms of Service](https://www.anthropic.com/legal/commercial-terms)
- [Privacy Policy](https://www.anthropic.com/legal/privacy)
- [Data Processing Addendum](https://www.anthropic.com/legal/data-processing-addendum)

## Langfuse

After each response, `trace_response()` (`src/observability.py`) sends a
trace to Langfuse containing the user's message, the assistant's reply, the
channel (`messenger` or `widget`), a SHA-256 hash of the sender/session ID,
the model name, token usage, latency, and whether the response was escalated.
This is used to monitor response quality and catch errors — it is not used
for advertising or shared further.

- [Terms of Service](https://langfuse.com/terms)
- [Privacy Policy](https://langfuse.com/privacy)

## Notes for assessment

- Conversation records (in Fly's SQLite volume and in Langfuse) are purged
  after 12 months by the nightly scheduler (`src/scheduler.py`).
- No real names, email addresses, or social media profiles are ever sent to
  any of these services — only message content and one-way hashed
  identifiers (see `privacy-policy.html` for how those hashes are derived).
- If you add a new third-party integration (e.g. a different LLM provider or
  analytics tool), add it to this document and to the "Third-party services"
  section of `privacy-policy.html`.
