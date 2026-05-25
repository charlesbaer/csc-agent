# CSC Agent — Requirements

## Problem Statement

Members of the Community Swim Club (communityswimclub.com) are not reading emails or visiting the website to get information. They reach out directly via email or Facebook Messenger instead. The club needs an automated agent that can answer member questions immediately in the channels they already use, without requiring staff to respond manually to every inquiry.

---

## Goals

1. Reduce staff time spent answering repetitive informational questions.
2. Give members instant, accurate answers in the channels they already use.
3. Keep operating costs minimal.
4. Provide visibility into what members are asking through usage analytics.
5. Maintain quality through automated evaluations.

---

## Channels

### Phase 1 (Initial Release)
- **Facebook Messenger** — respond to messages sent to the CommunitySwimClub Facebook page.

### Phase 2 (Future)
- **CSC Website** — embedded chat widget directly on communityswimclub.com.
- **Gmail** — automatically respond to incoming emails sent to the club's Gmail account.

The agent's core knowledge and logic should be channel-agnostic so the same implementation can be surfaced across all three channels without duplicating business logic.

---

## Content Sources

| Source | Purpose |
|---|---|
| communityswimclub.com | Primary source of truth for all club information |
| facebook.com/communityswimclub | Secondary source for events, announcements, and social content |

Content will be crawled and indexed from both sources. When the website and Facebook page conflict, the website is authoritative. The knowledge base is re-indexed nightly to pick up changes without manual intervention.

---

## Agent Identity & Tone

The agent identifies itself as **CSC** (no custom persona or mascot name). Responses should be:
- Friendly, welcoming, and concise.
- Written in the first-person plural ("We open at 9am", "Our snack bar serves…").
- Free of jargon; accessible to members of all ages.

---

## Board Contact Addresses

The following role-based email addresses are public and may be shared by the agent with members:

| Role | Address |
|---|---|
| President | president@communityswimclub.com |
| Treasurer | treasurer@communityswimclub.com |
| Membership | membership@communityswimclub.com |
| Secretary | secretary@communityswimclub.com |

The agent should route members to the most relevant role address when possible (e.g., membership questions → membership@, payment questions → treasurer@), and fall back to secretary@ for anything else.

---

## Escalation Contact

When the agent cannot answer a question, it directs members to:

- **Email:** secretary@communityswimclub.com
- **Facebook Page:** facebook.com/communityswimclub

The secretary is also the administrator of the CommunitySwimClub Facebook Page and is the primary human escalation point for both channels.

---

## Knowledge Domains

The agent must be able to answer questions across the following topics:

| Domain | Example Questions |
|---|---|
| **Pool hours** | What are the pool hours? Is the pool open on holidays? |
| **Membership** | How do I join? What does membership cost? How do I renew? |
| **Social events** | What events are coming up? How do I sign up for a party? |
| **Tennis** | Are courts available? How do I book a court? Lessons? |
| **Racketball** | Court availability, booking, and lessons. |
| **Swim lessons** | Lesson schedules, age groups, registration, pricing. |
| **Snack bar / menu** | What food is available? What are snack bar hours? |
| **Facility reservations** | How do I reserve the pool, pavilion, or courts for a private event? |
| **Pool & governance** | Pool rules, board member names and roles, club history and policies. |

The agent should gracefully handle out-of-scope questions by directing members to contact the club directly.

---

## Functional Requirements

### FR-1: Question Answering
- The agent answers natural-language questions using a knowledge base derived from the CSC website and curated club documents.
- Answers must be accurate, concise, and friendly in tone.
- The agent must not hallucinate facts; if information is unavailable it should say so and suggest contacting the club.

### FR-2: Facebook Messenger Integration
- The agent connects to the CommunitySwimClub Facebook Page via the Meta Messenger Platform (Webhooks API).
- It receives incoming messages, generates a response, and sends the reply in the same conversation thread.
- Handles standard text messages; graceful fallback for attachments, stickers, or quick-reply payloads.

### FR-3: Channel Abstraction
- Business logic (intent classification, knowledge retrieval, answer generation) is separated from channel-specific I/O adapters so new channels (website widget, Gmail) can be added with minimal changes.

### FR-4: Knowledge Base Management
- Content is sourced from communityswimclub.com and any supplemental documents provided by club administrators.
- Administrators can update the knowledge base without code changes (e.g., by editing source documents or triggering a re-index).

### FR-5: Fallback & Escalation
- When the agent cannot answer confidently, it acknowledges the limitation and provides a contact method (email, phone, or website link).
- Optionally, unresolved questions can be flagged for a human follow-up queue.

---

## Non-Functional Requirements

### NFR-1: Cost Efficiency
- Use a cost-effective LLM (e.g., Claude Haiku or equivalent small model) for most queries; route to a larger model only for complex or ambiguous questions.
- Implement caching for frequently asked questions to reduce redundant LLM calls.
- Retrieval-augmented generation (RAG) should be scoped to relevant knowledge chunks to minimize token usage.

### NFR-2: Latency
- Responses should be delivered within 5 seconds under normal load.

### NFR-3: Reliability
- The agent should handle Facebook Webhook retries gracefully (idempotent message processing).
- Errors should be logged and surfaced via monitoring without exposing internal details to end users.

### NFR-4: Security & Privacy
- No personally identifiable information (PII) from conversations should be stored beyond what is necessary for analytics aggregation.
- API keys and secrets must be managed via environment variables / secrets manager, never committed to source control.
- Facebook Webhook verification token must be validated on every incoming request.

---

## Analytics Requirements

### AR-1: Usage Metrics
Track and expose the following metrics:

- Total conversations and messages per day / week / month.
- Top questions / intents (what members ask most).
- Topics that triggered a fallback / escalation (gaps in the knowledge base).
- Response latency (p50, p95).
- Channel breakdown (Messenger, website, email) once multiple channels are live.

### AR-2: Dashboard
- A lightweight dashboard (or export to a standard BI tool) to visualize the metrics above.
- Accessible to club administrators without engineering support.

---

## Evaluation Requirements

### EV-1: Offline Evals (Pre-deployment)
- A curated golden dataset of question–answer pairs covering all knowledge domains.
- Automated tests compare agent outputs against expected answers using LLM-as-judge and/or exact/fuzzy match scoring.
- Evals run in CI on every change to the knowledge base or agent logic.
- Minimum acceptable score threshold gates deployment.

### EV-2: Online Evals (Post-deployment)
- A sample of live conversations is evaluated automatically against quality rubrics (accuracy, helpfulness, tone, hallucination rate).
- Evaluation results are logged and fed back into the analytics dashboard.
- Alerts fire when quality drops below a configured threshold.

### EV-3: Regression Testing
- Any newly discovered failure case (wrong or hallucinated answer) is added to the golden dataset so it cannot regress.

---

## Analytics & Observability Tooling

No existing analytics tooling is in place. The following stack is recommended to meet analytics and eval requirements while keeping costs minimal:

### Recommended: Langfuse (LLM Observability — Free Tier)

[Langfuse](https://langfuse.com) is purpose-built for LLM applications. It covers:
- **Tracing** — every conversation, LLM call, retrieval step, and latency is recorded automatically.
- **Cost tracking** — token usage and estimated spend per model per day.
- **Evals** — built-in support for LLM-as-judge scoring on live traces (online evals) and dataset-based offline evals.
- **Dashboard** — built-in charts for volume, latency, quality scores, and error rates.
- **Free cloud tier** — generous enough for a small club's traffic; self-host on a small VM if needed to eliminate the cloud cost entirely.

Langfuse satisfies AR-1, AR-2, EV-2, and EV-3 with no additional tooling.

### Recommended: Google Looker Studio (Admin Dashboard — Free)

[Looker Studio](https://lookerstudio.google.com) (formerly Data Studio) connects to Langfuse exports or a lightweight Postgres/SQLite log table and provides a shareable, browser-based dashboard that administrators can view without any engineering access. This satisfies the AR-2 requirement for a non-technical admin view.

### Alternative Considered: PostHog

PostHog (free tier: 1M events/month) is a strong alternative for product analytics but lacks the LLM-specific tracing that Langfuse provides. It could be added later for session-level funnel analysis if needed.

### Decision Summary

| Requirement | Tool | Cost |
|---|---|---|
| LLM traces, costs, latency | Langfuse cloud (free tier) | $0 |
| Online evals (LLM-as-judge) | Langfuse evals | $0 + LLM token cost |
| Offline eval dataset & CI | Langfuse datasets + GitHub Actions | $0 |
| Admin-facing dashboard | Google Looker Studio | $0 |

---

## Meta Developer App Setup

No existing Meta Developer App exists. The following is required to build the Messenger integration:

### Phase 1 — Initial Setup (One-time)
1. Create a Meta Developer account at developers.facebook.com.
2. Create a new Meta App (type: Business).
3. Add the **Messenger** product to the app.
4. Configure a Webhook to receive `messages` and `messaging_postbacks` events.

### Phase 2 — Staging / Development

A dedicated test Facebook Page is used for development and QA so the production CommunitySwimClub page is never touched during development. The Meta App runs in development mode — only App admins and testers can interact with the bot, no App Review required.

**Steps:**
1. Secretary creates a new Facebook Page (e.g., "CSC Agent Test").
2. Link the test page to the Meta App.
3. Add each developer's Facebook account as an App Tester.
4. Point the webhook at the staging server.

**What is needed:**
- Secretary creates the test page (~5 minutes).
- A Facebook account for each developer to add as App Tester.

### Phase 3 — Production Cutover (Go-Live)

When testing is complete and the agent is ready for real members:

1. **Link the production page** — In the Meta App dashboard, add the CommunitySwimClub Facebook Page (secretary grants permission). The test page can remain linked for continued regression testing.
2. **Update the webhook URL** — Point the production webhook subscription to the production server endpoint.
3. **Subscribe the production page** — Generate and save a production Page Access Token scoped to the CommunitySwimClub page.
4. **Submit for App Review** — Request the `pages_messaging` permission from Meta. This is required before non-testers (i.e., regular members) can receive bot responses. Approval typically takes a few days.
5. **Verify end-to-end** — Send a test message from a non-tester account on the production page to confirm the live bot responds correctly.
6. **Announce to members** — Notify members that they can now message the CommunitySwimClub Facebook page to get instant answers.

> The test page and staging server remain active after go-live so future changes can be validated before being promoted to production.

---

## Out of Scope (v1)

- Booking or transactional workflows (the agent answers questions but does not process registrations, payments, or reservations directly).
- Multi-turn memory beyond a single conversation session.
- Support for languages other than English.
- Mobile app integration.

