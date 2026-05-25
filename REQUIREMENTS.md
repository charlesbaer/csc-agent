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

## Out of Scope (v1)

- Booking or transactional workflows (the agent answers questions but does not process registrations, payments, or reservations directly).
- Multi-turn memory beyond a single conversation session.
- Support for languages other than English.
- Mobile app integration.

---

## Open Questions

1. Where is the authoritative source of truth for pool hours, events, and pricing — the website, a Google Sheet, or another system? This affects the knowledge-base update workflow.
2. Does the club want the agent to hand off to a specific staff email/phone, or is a generic "contact us" message sufficient for escalations?
3. Are there any existing Facebook Page credentials or a Meta Developer App already set up?
4. What analytics tooling does the club already use (Google Analytics, a BI tool, spreadsheets)?
5. Is there a staging/test Facebook Page that can be used for development and QA?
