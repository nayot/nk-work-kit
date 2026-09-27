---
name: e-leave
description: Activate this skill when the user wants to do anything in BUU's e-Leave system (e-leave.buu.ac.th) — "ยื่นใบลา", "ขอลา", "ลาพักผ่อน", "ลาป่วย", "ลากิจ", "ไปราชการ", "ขอไปราชการ", "ลาไปต่างประเทศ", "วันลาคงเหลือ", "เหลือวันลากี่วัน", "สถานะการลา", "ใบลาอนุมัติหรือยัง", "ยกเลิกใบลา", "submit a leave request", "take leave", "sick leave", "how many vacation days do I have left", "cancel my leave". Checks leave balance and status, and submits or cancels leave requests with evidence (ใบรับรองแพทย์, เอกสารต้นเรื่อง) attached — always showing the rendered ใบลา and waiting for the user's approval before submitting.
allowed-tools: [Bash, Read, Write]
version: 1.0.0
---

# e-Leave — ระบบลาออนไลน์ มหาวิทยาลัยบูรพา

Driver for **https://e-leave.buu.ac.th**. One script does all the work:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/eleave.py" <command>
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script sits at
`<plugin-root>/scripts/eleave.py`. It runs headless and signs in through BUU
SSO with the eDoc account (`EDOC_USERNAME` / `EDOC_PASSWORD`, or
`ELEAVE_USERNAME` / `ELEAVE_PASSWORD` if set) from `~/.config/nk-work-kit/.env`.
A run takes about 15–40 seconds.

## Commands

| Command | What it does | Writes? |
|---|---|---|
| `balance` | วันลาพักผ่อนคงเหลือ, leave taken and late/no-scan counts this ปีประเมิน | no |
| `status [--year 2569 ...]` | สถานะการลา with approvers. Default: the site's current ปีประเมิน and the one before | no |
| `types` | Leave types and which ones are automated | no |
| `fields <type>` | The form fields of one type (for the website-only types) | no |
| `request spec.json` | Fills the form and stops at the site's review page: prints the ใบลา and a `preview_id` | no |
| `request spec.json --confirm <preview_id>` | **Submits the request.** E-mails the approvers | **YES** |
| `cancel --start <date> [--year Y]` | Finds a รออนุมัติ request by its start date and shows it | no |
| `cancel --start <date> --confirm` | **Cancels it.** E-mails the approvers | **YES** |

Put `--json` before or after the command for machine-readable output; use it
and write the summary yourself. Exit codes: 0 ok, 2 bad input or a rule the
site enforces (the message says which — relay it), 3 config/login problem,
1 anything else.

## Submitting a leave request — the rule

**Never submit or cancel without the user's explicit approval of that
specific request**, the same rule as e-mail. The workflow is always:

1. Gather the details (below). Ask only for what is missing; don't ask for
   optional fields the user has no reason to fill.
2. Write the spec to a JSON file in the scratchpad and run
   `request spec.json --json` (preview). The review step saves nothing
   (verified).
3. Show the user: type, dates, **working days** (`working_days`) and calendar
   days, attachments, and the rendered ใบลา text (`letter`) — it is the actual
   letter the approvers will see. Offer the screenshot path.
4. Only after the user says yes to *that* preview, run
   `request spec.json --confirm <preview_id> --json`. The script refuses if the
   ใบลา the site renders now differs from the preview (e.g. the date rolled
   over) — then preview again and re-confirm.
5. Report `submitted`. If it is `"unclear"`, **do not run it again** — run
   `status` and tell the user what you see. A duplicate submission is worse
   than a check.

If the preview fails with exit 2, the message is the site's own rule (e.g. not
enough days left, evidence required, date too early) — tell the user plainly;
don't try to work around it.

## Request spec

```json
{"type": "ลาพักผ่อน",
 "start": "2026-11-18", "end": "2026-11-20",
 "start_period": "full", "end_period": "full",
 "reason": "ธุระส่วนตัว",
 "documents": ["/path/to/evidence.pdf"]}
```

- `type`: Thai name (a unique fragment like `"ป่วย"` works) or id from `types`.
- Dates: ISO ค.ศ. (`2026-11-18`) or พ.ศ. `18/11/2569`. `end` defaults to `start`.
- `start_period` / `end_period`: `full`, `morning` (ครึ่งวันเช้า), `afternoon`
  (ครึ่งวันบ่าย). One day: set `start_period` only. Several days: may start
  with an afternoon and end with a morning, not the reverse.
- `reason`: เหตุผลการลา. Optional for ลาพักผ่อน, expected for ลากิจ and ลาป่วย.
  For ไปราชการ it is the "ขออนุญาตไปราชการเกี่ยวกับ" text — required in practice.
- `documents`: evidence, **.pdf/.jpg/.jpeg/.png under 5 MB each**, filled into
  the form's upload slots in order.
- `fields`: `{"LED_NAME": "value"}` escape hatch for a text field the spec
  doesn't cover (see `fields <type>`).

### Per type

| Type | id | Notes |
|---|---|---|
| ลากิจส่วนตัว | 1 | `reason` |
| ลาป่วย | 2 | Can be backdated. `documents`: ใบรับรองแพทย์ — the site demands it for longer sick leave; the preview says so if it's missing |
| ลาพักผ่อน | 3 | Starts tomorrow at the earliest. Check `balance` if the user may be short |
| ไปราชการ | 9 | `start_time` / `end_time` `"HH:MM"` (5-minute steps), `reason`, `place` (ณ), `with_people` (staff names, matched against the site's list), `with_outsiders` (free-text names: outside people/นิสิต), `documents` (เอกสารแนบต้นเรื่อง: the invitation, order or memo) |
| ลากิจส่วนตัวไปต่างประเทศ | 6 | `objective` (มีความประสงค์จะลา), `countries` (Thai country names), `country_start` / `country_end` (default: the leave dates), `reason` |
| ลาพักผ่อนไปต่างประเทศ | 4 | same as 6 |

Website only (rare, long forms): ลาอุปสมบท (8), ลาไปช่วยเหลือภริยาที่คลอดบุตร (11),
ลาติดตามคู่สมรส (12), ลาไปฟื้นฟูสมรรถภาพด้านอาชีพ (15). Say so, run
`fields <id>` if the user wants to know what the form asks for, and point
them to https://e-leave.buu.ac.th/leave-request.

**Evidence the user mentions** ("แนบใบรับรองแพทย์", "ต้นเรื่องอยู่ใน Downloads")
must be a local file path. If it is in eDoc or Drive, fetch it first (the
`edoc-digest` skill downloads eDoc attachments to
`~/.local/share/nk-work-kit/edoc/<date>/`). Check the file opens and is the
right document before attaching; convert other formats to PDF.

## Cancelling

`cancel --start <date>` finds the request by its start date in the current
ปีประเมิน, then the year before. e-Leave cancels only requests that are still
**รออนุมัติ**; once approved, the user needs the website/HR. Show the match,
get an explicit yes, then run with `--confirm`. Same "unclear → check
`status`, never repeat" rule.

## Reading status

- **ปีประเมิน is not the calendar year**, and it rolls over before
  1 October (in late September 2569 the site already shows 2570). That is why
  `status` reads two years by default. When the user asks about "this year's"
  leave, say which ปีประเมิน you mean.
- Statuses seen: `อนุญาต` (approved), `รออนุมัติ` (pending); each entry lists
  its approval chain (`approvals`: role, person, position, status, date).
- The user is an approver as well (คณบดี). This skill does not approve other
  people's leave — that stays on the website.

## Verification state

Submitting was verified end to end on 27 Sep 2569 (a ไปราชการ request with a
PDF attached). **Cancel is not yet verified** — it follows the manual and
stops with `"unclear"` rather than guessing; after the first real cancel,
check `status` with the user.

For ไปราชการ, "full day" means `start_time` 08:30 and `end_time` 16:30. The
approval chain is chosen by e-Leave (e.g. หัวหน้าภาค, then the acting dean);
report it from `status` after submitting.
