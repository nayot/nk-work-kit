---
name: business-card
description: Process a photo of a business card for Nayot — extract the contact details, save them to his Google Contacts, and draft a greeting email that shares his vCard link. Use this skill whenever the user uploads, pastes or points at a photo that looks like a business card or name card (นามบัตร), even if they only say "here's a card", "new contact", "met this person today", "บันทึกนามบัตร", or send the image with no text at all. Also use it for photos of several cards at once, or the front and back of one card.
version: 1.2.0
---

# Business card → contact + greeting email

Nayot (Asst. Prof. Dr. Nayot Kurukitkoson, Burapha University Faculty of
Engineering, Bang Saen, Chonburi) meets many people at conferences, industry
visits and partner meetings, often in the EEC. He photographs their cards and
wants three things done with as little back-and-forth as possible.

Two scripts ship with the plugin:

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/gcontacts.py" search|create|update ...
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/make_vcf.py" contact.json out.vcf
```

Below, `gcontacts` is short for the first line (on Nayot's machine a
`gcontacts` command on `PATH` runs the same script). If `CLAUDE_PLUGIN_ROOT` is
not set, both sit in `<plugin-root>/scripts/`.

## Step 0 — Is it a business card?

Read the image (a path he gives, or an attachment). A business card is a small
printed card with a person's name plus some mix of title, organisation, phone,
email, address, website, QR code or logo.

- If it clearly is not a business card (a receipt, a slide, a badge, a letter),
  say what you see in one sentence and ask what he'd like done. Do not run the
  workflow.
- If it is a card but blurry, cropped or glare-covered so that the name or email
  can't be read, extract what you can and ask for a retake of just the
  unreadable part.
- Several cards in one photo → process each one; front + back of one card →
  merge into one contact.

## Step 1 — Extract the information

Read every field on the card. Cards in Thailand are often bilingual (Thai one
side, English the other) — keep both versions of the name and organisation;
don't translate one into the other yourself.

Capture:
- Full name (English and/or Thai), honorific/academic title (Dr., Prof., คุณ, ดร., รศ.)
- Job title, department, organisation
- Phones — label each as mobile / work / fax. Normalise to international form
  (Thai `08x-xxx-xxxx` → `+66 8x xxx xxxx`; landline `038-xxx-xxx` → `+66 38 xxx xxx`)
- Email(s), website, LINE ID, social handles
- Postal address
- QR code contents if legible (often a vCard or LINE link)

Show the result as a short table and flag anything you're unsure of with "(?)"
— e.g. an ambiguous 0/O or 1/l in an email address. Email errors break Step 3,
so double-check those characters. Do not guess missing fields.

The contact's note is `Card scanned <today's date>` plus any context Nayot gave
("met at the DCI meeting").

## Step 2 — Save to Google Contacts

The Contacts MCP (`mcp__claude_ai_Google_Contacts__*`, load with ToolSearch) is
**search-only**. Edits go through `gcontacts` (People API via gcloud Application
Default Credentials): `search`, `create` and `update`, all printing JSON.

1. **Check for an existing contact first.** Run `gcontacts search <email>`, then
   `gcontacts search "<name>"` (English, then Thai). `search_contacts` from the
   MCP is an alternative when `gcontacts` is missing. If a match exists, show
   what's already stored next to what's new and say which fields would change.
2. **Existing contact → update it**, never create a duplicate:
   ```bash
   gcontacts update people/c123 --add-email a@b.com --add-phone "+66 81 234 5678" \
       --org "Foamtec" --title "VP" --note "<existing note>\nCard scanned 29 Sep 2026 …"
   ```
   `--add-email`/`--add-phone` append, one value per flag (repeat the command for
   a second one). `--given`, `--family`, `--org`, `--title` and `--note`
   **replace** the stored value, so only pass them when the card changes them,
   and build `--note` from the existing note plus the new line so nothing is lost.
   Address, website and LINE ID can't be set this way; list them in the note.
3. **New contact → create it.** Write `contact.json` to the scratchpad and run
   ```bash
   gcontacts create contact.json
   ```
   It stores every field (Thai name as a nickname, address, websites) and prints
   the new `resourceName`. It exits 1 and prints the match when one of the emails
   is already on a contact (it checks the full list, not search, so a contact
   created a minute ago still counts); update that one instead. `--force` makes
   a separate contact anyway — only when he says it is a different person.

   `contact.json` fields (also used by `make_vcf.py`): `given_name`, `family_name`, `prefix`, `alt_name` (Thai
   name), `org`, `department`, `title`, `phones` [{`number`, `type`}], `emails`
   [{`address`, `type`}], `urls`, `address`
   {`street`,`city`,`region`,`postcode`,`country`}, `note`.

If `gcontacts` fails on auth (no or expired gcloud ADC login, or a login without
the contacts scope), say so with the error and fall back to a vCard: build it in `~/Downloads/<First>_<Last>.vcf` with
`make_vcf.py` and tell him in one line to import it at contacts.google.com →
Import, or open it on his phone. Re-authenticating gcloud is an interactive
login he runs himself — the command is in the README's Business cards section.

## Step 3 — Draft the greeting email

**Draft only — never send.** Use Gmail `create_draft` (load with ToolSearch,
`mcp__claude_ai_Gmail__create_draft`), addressed to the email on the card, and
give him the draft link. If Gmail isn't available, or the card has no email, show
the email text in chat so he can copy it.

Language: English by default; Thai if the card is Thai-only or the person is
clearly a Thai counterpart with a Thai-language title. Keep it short — 4 to 6
sentences — warm, professional, not salesy.

Content:
- Subject: `Great to meet you — Nayot Kurukitkoson, Burapha University`. For a
  Thai email, start with `ยินดีที่ได้รู้จักครับ`.
- Greeting with the right honorific (Dear Dr. X / เรียน คุณ X, เรียน ดร. X).
- Thank them for the conversation; if he mentioned where they met or what was
  discussed, reference it in one clause. If he didn't, keep it generic rather
  than inventing details.
- One sentence on staying in touch / possible collaboration.
- The vCard link: `My contact details are here: https://nayot.github.io/vCard`
  (Thai: `ข้อมูลติดต่อของผมอยู่ที่ https://nayot.github.io/vCard`).
- Sign-off:
  ```
  Best regards,
  Nayot Kurukitkoson
  Faculty of Engineering, Burapha University
  https://nayot.github.io/vCard
  ```

For Thai: first person ผม, particle ครับ, close with `ขอบคุณครับ` and sign `ณยศ`
followed by his full Thai name and `คณะวิศวกรรมศาสตร์ มหาวิทยาลัยบูรพา`. Never
transliterate his surname into Thai: take the exact spelling from one of his own
Thai emails (Gmail `search_threads`, `from:me` with Thai text) or ask him.

## Finish

Reply briefly: the extracted table, the contact status (updated / created / `.vcf` to
import), and the Gmail draft link (or the email text). Point out any "(?)"
fields that need a human check. If the person clearly belongs to a tracked
project, offer to log the contact there (project-manager skill). Nothing else.
