# Control Flow & Architecture — Business and Functional View

Purpose

- A concise, non-technical reference describing how the Gim Gym Bot supports business processes: member onboarding, reservation lifecycle, admin approvals, and operational controls.

Executive summary

- The bot provides three primary business functions: manage membership join requests, enforce capacity-based reservations and check-ins, and enable admin oversight (locking/reserving and reporting). It uses Telegram as the user-facing channel, a relational database for state and history, and a service layer to implement business rules and SLAs.

1. Control flow — user journeys (functional view)

- New member onboarding: User requests to join via private chat → submits name, roll, phone → admins receive a single approval message → on approval the user receives a one-time invite into the group. This is an asynchronous human-in-the-loop approval flow.
- Reservation and attendance: Members reserve slots (subject to capacity and global lock state) → reservations expire if not checked-in within the reservation window → checking in starts a timed session → automatic checkout or manual checkout ends session. The system records no-shows and overstays for enforcement.
- Admin actions: Admins lock/unlock reservations, promote/demote admins, review active/expiring sessions, and approve join requests. Actions occur in a dedicated admin channel to preserve auditability.

2. Event model & interaction patterns (how Telegram is used functionally)

- Primary events: immediate user commands (reserve/checkin/checkout), multi-step form events (join flow), and admin decision callbacks (approve/decline).
- Interaction patterns: synchronous commands for quick member actions; asynchronous approval messages for manual decisions; automated scheduled jobs for policy enforcement (expiry, overdue sessions).
- UX rationale: Inline approval buttons and message edits keep the conversation clean, reduce administrative noise, and create an auditable trail of decisions.

3. Slash commands and deep links (business meaning)

- Slash commands are the main user interface: discoverable, concise actions that map directly to business operations (reserve, checkin, checkout, cancel, status).
- Deep links (arguments to the start command) are used for integrations such as QR-code driven flows—enabling physical touchpoints (QR scan) to trigger reserved/checkin intents directly.

4. Why Telegram from a business standpoint

- Developer and feature advantages: programmatic invite links, inline keyboards, callback-based approvals, and robust message-editing support enable the core business workflows (quick approvals, single-use invites).
- Operational advantages: low deployment friction for pilots, built-in group context for admins, and straightforward UX for members—no extra apps or sign-ups.

5. Three-layer functional architecture (business roles)

- Channel & Interaction (Telegram)
  - Role: Surface UI for members and admins; deliver notifications, collect inputs, and host approval actions.
  - Business needs: reliable delivery, minimal friction, audit logs of approvals, and invite distribution.
- State & Audit (Database)
  - Role: Source of truth for membership status, reservations, session history, and policy flags (no-shows, overstays).
  - Business needs: accurate occupancy reporting, historical records for disputes, exportable data for analytics.
- Rules & Policies (Service layer)
  - Role: Enforce capacity rules, reservation windows, session durations, block/penalty logic, and compose messages to members/admins.
  - Business needs: deterministic rule outcomes, clear human-readable messages, and config-driven policy parameters (capacity, time windows).

6. Key business decisions and trade-offs

- In-process scheduler: chosen to keep operations simple (single process) during pilots. Trade-off: a single-process scheduler can impact availability and scaling; consider a separate scheduler/worker for production.
- Human-in-loop approvals in one admin channel: simplifies oversight and auditability; trade-off: depends on admin availability—introduce SLAs or delegation for scale.
- Flexible state encoding for global settings: allows rapid product changes but makes analytics and audit queries harder; consider structured fields for critical controls.

9. Recommended next steps (business / operational)

- Formalize SLAs for admin approvals and session handling; communicate these to members.
- Instrument the system for the KPIs above and add dashboards and alerts for capacity and invite failures.
- Create a short operations playbook: add/remove super-users, handover steps for admin changes, backup & restore, and invite-permission checks.

Want this converted into a one-page slide, a runbook template, or a sequence diagram (mermaid)? Tell me which and I’ll produce it.

10. SDKs and Event Hooks — broader concepts

- SDKs: We build on established SDKs (Telegram client libraries, ORM, config/validation libraries, scheduling and logging SDKs) to accelerate delivery, reduce bugs, and rely on maintained primitives. Business impact: faster time-to-market, consistent error handling, and predictable upgrade paths — but requires tracking upstream API changes and managing dependency upgrades.
- Event hooks & patterns: The system uses event-driven patterns (user commands, callback events, FSM state transitions, and scheduled events) to decouple transport, business rules, and persistence. Business impact: clear separation allows independent scaling of business logic and persistence, more testable flows, and flexibility for future channels (webhooks, mobile apps) by implementing the same event contracts.
