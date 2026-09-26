---
type: manual
plugin_version: {{VERSION}}
generated: {{DATE}}
---
# Projects: User Manual · คู่มือการใช้งาน

> [!info] Written by the nk-work-kit plugin (v{{VERSION}}) and replaced on every plugin update, so keep your own notes elsewhere.
> ไฟล์นี้สร้างโดยปลั๊กอิน nk-work-kit (v{{VERSION}}) และจะถูกเขียนทับทุกครั้งที่อัปเดตปลั๊กอิน กรุณาอย่าจดบันทึกของคุณไว้ในไฟล์นี้

**→ [[{{FOLDER}}/Dashboard|📊 Open the Projects Dashboard · เปิดแดชบอร์ดโครงการ]]**

Jump to: [[#English]] · [[#ภาษาไทย]]

---

## English

### What this is

Each ongoing project is one **hub note** in `{{FOLDER}}/`. The hub records the project's status, its next action and its dated tasks, and links to your meeting notes and other material. The **[[{{FOLDER}}/Dashboard|Dashboard]]** collects every hub into one live overview. Claude (the `project-manager` skill of nk-work-kit) keeps the hubs up to date as you work, and it can email you a digest of what is due.

### The dashboard

| Section | Shows |
|---|---|
| 🔴 Overdue | Open dated tasks, next actions and project deadlines that are past due |
| 🟡 Due in the next {{DAYS}} days | The same, due between today and {{DAYS}} days from now |
| Active projects | Priority, next action, who you are waiting on, last update; ⚠️ stale = not updated for {{STALE_DAYS}} days |
| ⏳ Waiting on others | Projects that are `waiting`, or active ones that name someone to chase |

The views are **live**. They update as soon as any note changes, and ticking a task on the dashboard ticks it in its own note. Don't edit the dashboard itself: it is regenerated and your edits would be lost.

**The views need the Dataview plugin.** If you see code blocks instead of tables:
1. **Settings → Community plugins**. If asked, choose **Turn on community plugins**.
2. **Browse**, search for **Dataview**, then **Install** and **Enable**.
3. Recommended: in **Settings → Dataview**, turn on **Automatic task completion tracking** and **Use emoji shorthand for completion**. A task you tick on the dashboard then gets its completion date (`✅ 2026-10-01`).

### A hub note

The fields at the top of the note (the frontmatter):

| Field | Meaning |
|---|---|
| `type: project` | Makes the note a project. Required. |
| `status` | `idea` · `active` · `waiting` · `on-hold` · `done` · `dropped` |
| `priority` | `high` · `normal` · `low` |
| `area` | Free text for grouping, such as `Quality` or `Industry` |
| `start`, `due` | Start date and project deadline (`YYYY-MM-DD`) |
| `next_action`, `next_action_due` | The one next concrete step, and when it is due |
| `waiting_on` | Who or what you are waiting for |
| `updated` | The last time the hub was reviewed |

Below the fields come four sections: **Summary**, **Milestones / Tasks**, **Related notes** and **Log**.

**Tasks** use the Tasks-plugin format. A task appears on the dashboard only when it has a `📅` date:

```markdown
- [ ] Send draft MOU 📅 2026-10-02
- [x] Kickoff meeting ✅ 2026-09-22
```

A task in **any other note** counts for a project when its line links the hub:

```markdown
- [ ] Book the meeting room [[My Project]] 📅 2026-10-05
```

### Working with Claude

Ask in plain English or Thai, for example:

| You say | Claude does |
|---|---|
| "What's due this week?" / "What's overdue?" | Reads the hubs and lists overdue items first |
| "Update ABET: the letters went out today" | Ticks the task, logs it, moves the next action |
| "Add a new project: Lab renovation" | Creates a hub, pre-filled from your notes, email and calendar |
| "Log this meeting summary to the IPC project" | Links the note and adds a Log line |
| "Set up project tracking" | First-time setup: finds candidate projects and creates the hubs |
| "Set up the project digest" | Sets up the scheduled email digest |

Claude only puts real dates in `📅` or `*_due` fields, taken from you, an email, a calendar event or a document. A status change such as active → done is always your call: Claude proposes it and waits for your OK. Claude never edits or moves your other notes, and never reads `Confidential/`.

### Email digest (optional)

On weekday mornings, an email lists what is overdue or due within {{DAYS}} days. Nothing is sent on a quiet day, and each item links back to its note in Obsidian. To turn it on, ask Claude to "set up the project digest".

### Settings

These go in `~/.config/nk-work-kit/.env`:

| Setting | Default | Meaning |
|---|---|---|
| `OBSIDIAN_VAULT` | — | Path of this vault |
| `PM_FOLDER` | `Projects` | Folder of the hub notes |
| `PM_NOTIFY_DAYS` | `14` | "Due soon" window, in days |
| `PM_STALE_DAYS` | `14` | Days without an update before a project is flagged stale |
| `PM_NOTIFY_TO` | — | Email address for the digest |
| `PM_MAIL_METHOD` | `gmail-oauth` | How the digest is sent |

After changing `PM_FOLDER`, `PM_NOTIFY_DAYS` or `PM_STALE_DAYS`, ask Claude to "update the dashboard".

### Troubleshooting

- **The dashboard shows code blocks.** Install Dataview (see above).
- **A task is missing from the dashboard.** It needs a `📅 YYYY-MM-DD` date, and it must sit in a hub note or link one with `[[…]]`. Tasks in `done` or `dropped` projects are hidden.
- **A ticked task has no ✅ date.** Turn on the two Dataview settings above.
- **A red "Dataview: Error" box.** Ask Claude to "update the dashboard". If the error stays, report it with the error text.

---

## ภาษาไทย

### ภาพรวม

แต่ละโครงการที่กำลังดำเนินอยู่มี **โน้ตหลัก (hub note)** หนึ่งไฟล์ในโฟลเดอร์ `{{FOLDER}}/` โน้ตหลักบันทึกสถานะของโครงการ งานถัดไป และงานที่มีกำหนดส่ง พร้อมลิงก์ไปยังบันทึกการประชุมและเอกสารอื่น ๆ ที่เกี่ยวข้อง **[[{{FOLDER}}/Dashboard|แดชบอร์ด]]** รวมทุกโครงการไว้ในหน้าเดียวและแสดงผลแบบสด Claude (สกิล `project-manager` ของ nk-work-kit) จะช่วยอัปเดตโน้ตหลักระหว่างที่คุณทำงาน และส่งอีเมลสรุปงานที่ใกล้ถึงกำหนดให้ได้

### แดชบอร์ด

| ส่วน | แสดง |
|---|---|
| 🔴 Overdue (เลยกำหนด) | งานที่มีกำหนดส่ง งานถัดไป และกำหนดส่งโครงการที่เลยวันกำหนดแล้ว |
| 🟡 Due in the next {{DAYS}} days (ใกล้ถึงกำหนด) | รายการประเภทเดียวกันที่ครบกำหนดภายใน {{DAYS}} วันนับจากวันนี้ |
| Active projects (โครงการที่ดำเนินอยู่) | ความสำคัญ งานถัดไป ผู้ที่รออยู่ วันที่อัปเดตล่าสุด ⚠️ stale = ไม่ได้อัปเดตเกิน {{STALE_DAYS}} วัน |
| ⏳ Waiting on others (รอผู้อื่น) | โครงการสถานะ `waiting` หรือโครงการที่ระบุผู้ที่ต้องติดตาม |

ทุกส่วนแสดงผล **แบบสด** เมื่อโน้ตใดเปลี่ยน แดชบอร์ดจะอัปเดตทันที และเมื่อติ๊กงานบนแดชบอร์ด งานนั้นจะถูกติ๊กในโน้ตต้นทางด้วย อย่าแก้ไขแดชบอร์ดโดยตรง เพราะแดชบอร์ดถูกสร้างใหม่อยู่เสมอ สิ่งที่แก้ไว้จะหายไป

**แดชบอร์ดต้องใช้ปลั๊กอิน Dataview** หากเห็นเป็นโค้ดแทนที่จะเป็นตาราง ให้ทำดังนี้
1. ไปที่ **Settings → Community plugins** หากมีข้อความถาม ให้กด **Turn on community plugins**
2. กด **Browse** ค้นหา **Dataview** แล้วกด **Install** และ **Enable**
3. แนะนำให้เปิด **Automatic task completion tracking** และ **Use emoji shorthand for completion** ใน **Settings → Dataview** ด้วย เมื่อติ๊กงานบนแดชบอร์ด จะมีวันที่เสร็จ (`✅ 2026-10-01`) บันทึกไว้ให้

### โน้ตหลักของโครงการ

ช่องข้อมูลส่วนบนของโน้ต (frontmatter)

| ช่อง | ความหมาย |
|---|---|
| `type: project` | ระบุว่าโน้ตนี้เป็นโครงการ (จำเป็น) |
| `status` | `idea` แนวคิด · `active` ดำเนินอยู่ · `waiting` รอผู้อื่น · `on-hold` พักไว้ · `done` เสร็จ · `dropped` ยกเลิก |
| `priority` | `high` สูง · `normal` ปกติ · `low` ต่ำ |
| `area` | กลุ่มงาน (พิมพ์อิสระ) เช่น `Quality`, `Industry` |
| `start`, `due` | วันเริ่มและวันกำหนดส่งโครงการ (`YYYY-MM-DD` เป็นปี ค.ศ.) |
| `next_action`, `next_action_due` | งานถัดไปที่ต้องทำหนึ่งเรื่อง และวันกำหนด |
| `waiting_on` | กำลังรอใครหรือรออะไร |
| `updated` | วันที่ทบทวนโน้ตหลักครั้งล่าสุด |

ถัดจากช่องข้อมูลมีสี่หัวข้อ ได้แก่ **Summary** (สรุป), **Milestones / Tasks** (หมุดหมายและงาน), **Related notes** (โน้ตที่เกี่ยวข้อง) และ **Log** (บันทึกความคืบหน้า)

**งาน** เขียนตามรูปแบบของปลั๊กอิน Tasks งานจะแสดงบนแดชบอร์ดเฉพาะเมื่อมีวันที่ `📅`

```markdown
- [ ] ส่งร่าง MOU 📅 2026-10-02
- [x] ประชุมเริ่มโครงการ ✅ 2026-09-22
```

งานใน **โน้ตอื่น** จะนับเป็นงานของโครงการเมื่อบรรทัดนั้นลิงก์ถึงโน้ตหลัก

```markdown
- [ ] จองห้องประชุม [[My Project]] 📅 2026-10-05
```

### ทำงานร่วมกับ Claude

สั่งงานเป็นภาษาไทยหรือภาษาอังกฤษได้ตามปกติ เช่น

| สิ่งที่พูด | สิ่งที่ Claude ทำ |
|---|---|
| "สัปดาห์นี้มีอะไรใกล้ถึงกำหนด" / "มีอะไรเลยกำหนด" | อ่านโน้ตหลักทุกโครงการ แล้วรายงานงานที่เลยกำหนดก่อน |
| "อัปเดตโครงการ ABET: ส่งหนังสือเชิญแล้ววันนี้" | ติ๊กงาน บันทึกลง Log และเลื่อนงานถัดไป |
| "เพิ่มโครงการใหม่: ปรับปรุงห้องปฏิบัติการ" | สร้างโน้ตหลัก โดยเติมข้อมูลจากโน้ต อีเมล และปฏิทิน |
| "บันทึกสรุปการประชุมนี้ลงโครงการ IPC" | ลิงก์โน้ตและเพิ่มบรรทัดใน Log |
| "ตั้งค่าติดตามโครงการ" | ตั้งค่าครั้งแรก: หาโครงการที่น่าจะติดตามและสร้างโน้ตหลักให้ |
| "ตั้งค่าอีเมลสรุปโครงการ" | ตั้งเวลาส่งอีเมลสรุป |

Claude จะใส่วันที่ใน `📅` หรือช่อง `*_due` เฉพาะวันที่จริง ที่มาจากคุณ อีเมล ปฏิทิน หรือเอกสาร การเปลี่ยนสถานะ เช่น active → done คุณเป็นผู้ตัดสินใจเสมอ Claude จะเสนอและรอคุณยืนยันก่อน Claude จะไม่แก้ไขหรือย้ายโน้ตอื่นของคุณ และจะไม่อ่านโฟลเดอร์ `Confidential/`

### อีเมลสรุป (ไม่บังคับ)

ทุกเช้าวันทำการ ระบบจะส่งอีเมลสรุปงานที่เลยกำหนดหรือครบกำหนดภายใน {{DAYS}} วัน วันที่ไม่มีงานค้างจะไม่ส่ง แต่ละรายการในอีเมลมีลิงก์กลับไปยังโน้ตใน Obsidian หากต้องการเปิดใช้ ให้บอก Claude ว่า "ตั้งค่าอีเมลสรุปโครงการ"

### การตั้งค่า

ตั้งค่าไว้ในไฟล์ `~/.config/nk-work-kit/.env`

| ค่า | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `OBSIDIAN_VAULT` | — | ตำแหน่งของ vault นี้ |
| `PM_FOLDER` | `Projects` | โฟลเดอร์ของโน้ตหลัก |
| `PM_NOTIFY_DAYS` | `14` | จำนวนวันที่ถือว่า "ใกล้ถึงกำหนด" |
| `PM_STALE_DAYS` | `14` | จำนวนวันที่ไม่ได้อัปเดต ก่อนขึ้นเตือน stale |
| `PM_NOTIFY_TO` | — | อีเมลผู้รับอีเมลสรุป |
| `PM_MAIL_METHOD` | `gmail-oauth` | วิธีส่งอีเมล |

หลังแก้ `PM_FOLDER`, `PM_NOTIFY_DAYS` หรือ `PM_STALE_DAYS` ให้บอก Claude ว่า "อัปเดตแดชบอร์ด"

### แก้ปัญหาเบื้องต้น

- **แดชบอร์ดแสดงเป็นโค้ด:** ติดตั้ง Dataview (ดูด้านบน)
- **งานไม่ขึ้นบนแดชบอร์ด:** งานต้องมีวันที่ `📅 YYYY-MM-DD` และต้องอยู่ในโน้ตหลัก หรือลิงก์ถึงโน้ตหลักด้วย `[[…]]` งานของโครงการที่ `done` หรือ `dropped` จะไม่แสดง
- **ติ๊กงานแล้วไม่มีวันที่ ✅:** เปิดการตั้งค่า Dataview สองข้อด้านบน
- **มีกล่องสีแดง "Dataview: Error":** บอก Claude ว่า "อัปเดตแดชบอร์ด" หากยังไม่หาย ให้แจ้งพร้อมข้อความ error
