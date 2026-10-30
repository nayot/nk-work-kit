---
name: meet-attendees
description: Activate this skill when the user asks who is in, or was in, a Google Meet call — "who's here?", "who's in the meeting", "list the attendees", "who joined", "who left", "who was invited but didn't come", "group the attendees by organisation", "ใครอยู่ในห้องบ้าง", "รายชื่อผู้เข้าประชุม", "ใครเข้าประชุมบ้าง", "ใครยังไม่เข้า", "ใครออกไปแล้ว". Works during a live call and for meetings up to about 30 days old. Read-only.
version: 1.1.0
---

# Meet attendees

One read-only script lists the participants of a Google Meet call, with their
email where Google shows it, join/leave times (Asia/Bangkok) and whether they
were on the calendar invite:

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/meet_attendees.py" [CODE_OR_LINK] [--record ID] --json
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script is in `<plugin-root>/scripts/`.

## Which meeting

- No argument: the meeting on the user's calendar happening now (default for
  "who's here?").
- A meeting code (`abc-mnop-xyz`) or `meet.google.com/...` link the user gives,
  or that is in the calendar event they name.
- `--record conferenceRecords/ID` for one particular session; `recent` lists
  the user's recent meetings.

An ended meeting is visible only to its organiser; a live one to anyone in it.
If the script says it can't see the meeting, say that in one line.

## Answering

Always run with `--json` and answer from it; don't paste the JSON. Each
participant has `name`, `email`, `email_source` (`directory`, `contacts`,
`invite` = matched by name to the calendar invite, `invite (name≈email)` =
name matched to an invitee's email address, or null), `kind`
(`signed_in` / `anonymous` / `phone`), `domain`, `joined`, `left`,
`still_here`, `minutes` and `invited` (true / false / null = unknown: no
email to compare, so they may be one of `invited_absent`).
`invited_absent` lists invitees who never joined (null when no calendar event
was found).

- Default answer: a short list of who is here now (live) or who attended
  (ended), with the count.
- Group as the user asks: by organisation (`domain`; name the BUU domains as
  BUU, and put "no email" in its own group), invited vs not invited (and the
  invited who did not join), still here vs left.
- `minutes` is first join to last leave, so a rejoin counts the gap too.
- Mark emails whose `email_source` starts with `invite` as "from invite". Never guess an email
  or an organisation the script did not give.
- Pass on any `notes` that change the answer (calendar unreadable, several
  sessions of the same meeting).

## Setup

First use: `uv run …/meet_attendees.py auth` opens a browser for a one-time
Google sign-in with the BUU account (read-only Meet, directory, contacts and
calendar). On a machine without a browser it prints a link; after signing in,
run `auth --url '<address the browser ended on>'`. If the script says "Not
signed in" or a scope is missing, tell the user to run `auth`.
