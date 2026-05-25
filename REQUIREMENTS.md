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

Content will be crawled and indexed from both sources. When the website and Facebook page conflict, the website is authoritative. The knowledge base should be re-indexed on a scheduled basis (e.g., nightly) to pick up changes without manual intervention.

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

### Production Setup
1. Create a Meta Developer account at developers.facebook.com.
2. Create a new Meta App (type: Business).
3. Add the **Messenger** product to the app.
4. Link the app to the **CommunitySwimClub** Facebook Page (secretary@communityswimclub.com is the Page admin and can grant the required permissions).
5. Configure a Webhook to receive `messages` and `messaging_postbacks` events.
6. Submit for Meta App Review to obtain `pages_messaging` permission for production use.

### Staging / Development Setup

For development and QA, Meta's development mode allows testing without App Review — only admins, developers, and testers added to the Meta App can interact with the bot. Two options:

**Option A — Use the production page in dev mode (simplest)**
- Add developers as Testers on the Meta App.
- The bot only responds to those testers until the app is approved.
- No second page needed.

**Option B — Create a dedicated test Facebook Page**
- Create a new Facebook Page (e.g., "CSC Agent Test") — this is free and takes ~5 minutes.
- Link it to the Meta App for development.
- The production CommunitySwimClub page is never touched during development.
- Recommended if multiple developers will be testing simultaneously.

**What is needed to proceed:**
- Admin access to the CommunitySwimClub Facebook Page (secretary has this).
- Decision on Option A vs. Option B above.
- A Facebook account for each developer to add as App Tester.

---

## Out of Scope (v1)

- Booking or transactional workflows (the agent answers questions but does not process registrations, payments, or reservations directly).
- Multi-turn memory beyond a single conversation session.
- Support for languages other than English.
- Mobile app integration.

---

## Open Questions

1. **Staging page approach** — Option A (use the production page with dev-mode testers) or Option B (create a dedicated test page)? Option B is recommended.
2. **Re-index schedule** — Is nightly sufficient, or are there time-sensitive announcements (e.g., same-day pool closures) that require a faster refresh?
3. **Tone / persona** — Should the agent have a name and persona (e.g., "Splash, the CSC Assistant"), or respond neutrally as "CSC"?
4. **Board member privacy** — Should board members' personal contact info (phone/email) be surfaced by the agent, or should all contacts route through the secretary?
