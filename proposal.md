# 🏋️ College Gym Access Automation — Telegram Bot Proposal

## 1. Overview

The college gym has a maximum capacity of 18 users at any time. Currently, this is managed manually in a WhatsApp group.  
This proposal outlines a Telegram-based automation system to simplify entry management, enforce fair usage, and improve transparency.

**Key objectives:**

- Prevent overbooking beyond 18 users.
- Ensure fairness through time-bound sessions.
- Keep operations low-effort for admins.
- Allow only verified students to participate.

---

## 2. Core Concept

Students interact with a Telegram bot using simple commands.  
The bot tracks who has reserved a slot, who is checked in, and who has checked out — all in real time.

- No advance bookings: You can only reserve if space is available right now.
- Time-bound reservations:
  - 15-minute check-in window.
  - 120-minute session duration.
- Automatic clean-up: Reservations and sessions expire automatically.

---

## 3. User Commands

/reserve — Reserve a slot immediately (only if capacity < 18). You must check in within 15 min.
/checkin — Confirm you’ve entered the gym (must have an active reservation). Starts a 120-min session.
/checkout — End your session early and free up space.
/cancel — Cancel your reservation before check-in.
/status — See current occupancy and your personal status/timers.
/rules — Display gym policies and timing rules.
/help — Show usage instructions.

---

## 4. Session Lifecycle

States:

- Idle – not currently holding a slot.
- Reserved – temporary hold for up to 15 minutes.
- Checked In – actively using the gym (up to 120 minutes).
- Checked Out / Expired – session finished or auto-ended.

Transitions:

1. /reserve → Reserved (if capacity < 18)
2. /checkin within 15 min → Checked In (starts 120 min timer)
3. /cancel → back to Idle
4. No /checkin within 15 min → auto-expire (Idle, mark no-show)
5. /checkout → back to Idle
6. No /checkout within 120 min → auto-checkout (mark overstay)

Capacity logic:
Current occupancy = users in Checked In state.  
New reservation allowed only if Checked In + Reserved < 18.

---

## 5. Fairness Rules

- One active slot per user — you can’t reserve while already reserved or checked in.
- 15-minute check-in window — late arrivals forfeit slot.
- 120-minute max session — enforced automatically.
- Cancellations allowed anytime before check-in.
- Soft penalties:
  - 2 no-shows in 7 days → 24 h cool-down.
  - 3 overstays in 14 days → 72 h cool-down.
- Admins may lift blocks for valid reasons (exams, events, etc.).

---

## 6. Admin Oversight

There is no separate admin UI.  
Instead, a private “Admin Group” is maintained with special bot commands.

Admin Commands:
/summary — Show current occupancy and list of active users.
/user @username — Display a user’s monthly activity (no-shows, overstays, sessions).
/force_checkout @username — End a user’s active session manually.
/block @username Xd — Temporarily prevent user from booking.
/unblock @username — Restore booking privileges.

Admins use this group to monitor patterns, handle appeals, and maintain fairness.

---

## 7. Onboarding & Access Control

Step 1 — Private Telegram Group:

- The main gym group is private and only admins can approve join requests.
- The bot operates inside this group for transparency and announcements.

Step 2 — Google Form Verification:
A Google Form collects:

- Full Name
- College Email (verified manually or via suffix check)
- Student ID / Enrollment Number
- Telegram @username
- Graduation Year
- A short acknowledgment of the gym rules

Step 3 — Admin Approval:

1. Admins verify responses (email domain = college domain, valid student ID).
2. Approved students receive a single-use Telegram invite link to join the gym group.
3. Links are rotated monthly to prevent leaks.

Step 4 — Maintenance:

- Inactive users (no sessions > 90 days) are removed.
- Semester refresh: re-verify roster via updated Form.
- Admins may manually remove alumni or non-students.

---

## 8. Group Conduct

Pinned message inside the group:

Gym Booking Rules:

1. Walk-in only — reserve only when you’re ready to come now.
2. /checkin within 15 minutes of reservation, else auto-cancel.
3. Each session lasts 120 minutes max; auto-checkout enforced.
4. One active session per person.
5. Cancel promptly if you change your mind.
6. Respect time limits; repeated no-shows or overstays lead to temporary suspension.
7. Be polite in chat; admins’ decisions are final regarding misuse or penalties.

---

## 9. Notifications & Reminders

- Confirmation messages for each action (reserve, check-in, checkout).
- Reminder at T-5 min before 15-min check-in expiry.
- Reminder 10 min before auto-checkout.
- Quiet group updates (e.g., occupancy changes) at moderate frequency to avoid spam.

---

## 10. Implementation Overview

- Uses Telegram’s Bot API — stable, free, and well-documented.
- Operates fully inside Telegram; no external web interface required.
- Admin group serves as the monitoring interface.
- Automated timers handle expiries and cleanup daily.

---

## 11. Expected Benefits

- Prevents overcrowding and confusion.
- Reduces manual tracking work for admins.
- Enforces fairness automatically.
- Maintains verifiable usage records.
- Restricts participation to verified students only.

---

## 12. Roll-out Plan

Week 0 — Publish rules & Google Form, set up private Telegram group, onboard first batch manually.
Week 1 — Pilot bot with limited users (e.g., 30–50 students). Observe edge cases.
Week 2 — Full launch campus-wide; rotate invite links; post quick-start guide.
Week 3+ — Monitor usage stats, fine-tune timers and penalty thresholds.

---

Prepared for: Gym Committee / Student Affairs  
Purpose: Proposal for Telegram-based automated gym access management.
