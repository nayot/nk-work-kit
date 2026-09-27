#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "playwright==1.60.0",
# ]
# ///
"""
eleave.py — BUU e-Leave (https://e-leave.buu.ac.th): leave balance, leave
status, and submitting or cancelling a leave request (ยื่นใบลา / ยกเลิกใบลา).

    uv run eleave.py balance [--json]
    uv run eleave.py status [--year 2570 ...] [--json]
    uv run eleave.py types [--json]
    uv run eleave.py fields <type> [--json]
    uv run eleave.py request spec.json [--json]                 preview only
    uv run eleave.py request spec.json --confirm <preview_id>   SUBMITS
    uv run eleave.py cancel --start 2026-11-18 [--year Y]       preview only
    uv run eleave.py cancel --start 2026-11-18 --confirm        CANCELS

SIDE EFFECTS
------------
`balance`, `status`, `types` and `fields` only read. `request` and `cancel`
are two-phase: without `--confirm` they fill everything in, stop at the
site's own review step and print what would be sent. Submitting a leave
request, or cancelling one, e-mails the approvers — it cannot be taken back
quietly. `request --confirm` needs the `preview_id` printed by the preview
run, and refuses if the ใบลา the site renders now differs from the one that
was previewed. A submit is never retried automatically: if the outcome is
unclear, the script says so and the user checks `status`.

CREDENTIALS — ~/.config/nk-work-kit/.env (see scripts/.env.example)
--------------------------------------------------------------------
    ELEAVE_USERNAME, ELEAVE_PASSWORD   optional; fall back to the EDOC_ pair
    EDOC_USERNAME, EDOC_PASSWORD       BUU account (sso.buu.ac.th)

REQUEST SPEC (JSON)
-------------------
    {"type": "ลาพักผ่อน",              name or id, see `types`
     "start": "2026-11-18",            ISO (ค.ศ.) or dd/mm/yyyy (พ.ศ.)
     "end": "2026-11-18",              default: start
     "start_period": "full",           full | morning | afternoon
     "end_period": "full",             multi-day only
     "reason": "...",                  เหตุผลการลา / ไปราชการเกี่ยวกับ
     "documents": ["cert.pdf"],        evidence; pdf/jpg/jpeg/png, < 5 MB each
     # ไปราชการ (9) only
     "start_time": "08:30", "end_time": "16:30", "place": "...",
     "with_people": ["ชื่อ นามสกุล"], "with_outsiders": ["นาย ก ข"],
     # ต่างประเทศ (4, 6) only
     "objective": "...", "countries": ["ญี่ปุ่น"],
     "country_start": "...", "country_end": "...",   default: start / end
     "fields": {"LED_X": "value"}}     raw text fields, escape hatch

Only the types in SUPPORTED are automated; the rest (อุปสมบท, ช่วยเหลือภริยา
คลอดบุตร, ติดตามคู่สมรส, ฟื้นฟูสมรรถภาพ, ...) are rare, long forms and are
refused with a pointer to the website and `fields <type>`.

HARD-WON DETAILS — do not "simplify" these away:
  * The site sits behind a WAF that blocks Playwright's default headless user
    agent ("Web Page Blocked", Attack ID 20000051). A desktop Chrome UA is
    mandatory.
  * Login goes through sso.buu.ac.th (#username/#password), which may show an
    "Authorize" button on first use; it is clicked via .evaluate(). Success is
    asserted on the post-login URL being back on e-leave, not /auth or SSO.
  * The per-type part of the form is loaded by AJAX (leave-request/load-form)
    into #load-leave-request; the in/abroad radio reloads the type list first
    (load-type-leave). The radios are styled away, so click their <label>.
  * Date inputs are readonly jQuery-UI datepickers: set them with jQuery
    .val() and trigger 'change'. The change handler posts to
    leave-request/calculate-leave-days, which is the server's business-rule
    oracle: it fills LED_CALENDARDAY/LED_REALDAY (hidden, required by the
    server), can hide the submit button with a message (not enough days,
    too late, ...), and can make LED_DOCUMENT mandatory (sick leave evidence).
    Its response is read directly, not guessed from the DOM.
  * Half days: on a single day the start select offers เช้า/บ่าย; on a
    multi-day request the site disables start=เช้า and end=บ่าย and shows the
    end select. The periods are set after the dates and read back.
  * ไปราชการ (9) has hour/minute selects instead of half-day selects, a
    textarea LED_REMARK, LED_PLACE, and select2 multi-selects whose option
    values are "id::code::name" (people) or "id::name" (countries).
    LED_WITHOUTSIDER is select2 with tags:true — options are created in JS.
  * Attachment inputs are named differently per type (LED_DOCUMENT,
    LED_DOCUMENT[], LED_DOCUMENT[0]/[1]); they are filled in DOM order. The
    client rejects anything but pdf/jpg/jpeg/png and files of 5 MB or more,
    silently from a script's point of view, so both are checked here first.
  * Only ลาพักผ่อน carries startMinDate (tomorrow); the other types accept
    past dates — sick leave is normally filed after the fact.
  * ปีประเมิน is not the calendar year and rolls over before 1 October:
    on 27 Sep 2569 the site already defaults to 2570. `status` therefore reads
    the preselected year and the one before it unless --year is given.
  * Submit flow, verified 27 Sep 2569 with a real ไปราชการ request: POST
    /leave-request/confirm renders the ใบลา (with the user's e-signature) and
    saves nothing; its ยืนยัน opens a jquery-confirm dialog whose ยืนยัน
    saves and lands on leave-status with "บันทึกข้อมูลเรียบร้อยแล้ว". The
    preview_id was stable across two separate runs on the same day (the ใบลา
    carries today's date, so it changes at midnight).
  * NOT YET VERIFIED: the cancel flow (manual: expand a รออนุมัติ entry,
    ยกเลิกใบลา, dialog ยืนยัน, "ส่งอีเมลเรียบร้อยแล้ว"). The ยกเลิกใบลา button
    is detected on a รออนุมัติ entry; the rest follows the manual and stops
    with "unclear" rather than guess if the page differs.
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright, TimeoutError as PwTimeout
except ImportError:
    sys.exit("playwright is not installed. Run this script with `uv run`, "
             "which installs it automatically.")

BASE = "https://e-leave.buu.ac.th"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
DATA_DIR = Path.home() / ".local" / "share" / "nk-work-kit" / "eleave"
MAX_FILE = 5 * 1024 * 1024
FILE_EXT = {".pdf", ".jpg", ".jpeg", ".png"}

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_INPUT = 2
EXIT_CONFIG = 3

# id -> (Thai name, abroad?)
TYPES = {
    1: ("ลากิจส่วนตัว", False),
    2: ("ลาป่วย", False),
    3: ("ลาพักผ่อน", False),
    9: ("ไปราชการ", False),
    11: ("ลาไปช่วยเหลือภริยาที่คลอดบุตร", False),
    8: ("ลาอุปสมบท", False),
    15: ("ลาไปฟื้นฟูสมรรถภาพด้านอาชีพ", False),
    6: ("ลากิจส่วนตัวไปต่างประเทศ", True),
    4: ("ลาพักผ่อนไปต่างประเทศ", True),
    12: ("ลาติดตามคู่สมรส", True),
}
SUPPORTED = {1, 2, 3, 9, 4, 6}
PERIODS = {"full": "1", "morning": "2", "afternoon": "3"}
THAI_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
               "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


class UserError(Exception):
    """Bad input or a rule the site enforces — reported, exit code 2."""


def config_files() -> list[Path]:
    """Where plugin config may live, most specific first.

    The user-level file is the real home: a plugin installs into a
    version-pinned directory (~/.claude/plugins/cache/<market>/<plugin>/<ver>/),
    so a `.env` kept beside this script is orphaned by the next upgrade. The
    script-local path stays as a fallback for a plugin run from a clone.
    """
    bases = []
    if xdg := os.environ.get("XDG_CONFIG_HOME"):
        bases.append(Path(xdg))
    if appdata := os.environ.get("APPDATA"):       # Windows
        bases.append(Path(appdata))
    bases.append(Path.home() / ".config")          # Linux and macOS
    return [b / "nk-work-kit" / ".env" for b in bases] + [
        Path(__file__).resolve().parent / ".env"]


def load_env() -> None:
    """Read KEY=VALUE from the first config file found. Real env vars win."""
    for env_file in config_files():
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return


# ---------------------------------------------------------------- helpers

def to_be(value: str) -> str:
    """ISO ค.ศ. date or dd/mm/yyyy พ.ศ. -> dd/mm/yyyy พ.ศ. (the site's format)."""
    value = str(value).strip()
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value):
        d = date(int(m[1]), int(m[2]), int(m[3]))
    elif m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value):
        y = int(m[3])
        d = date(y - 543 if y > 2400 else y, int(m[2]), int(m[1]))
    else:
        raise UserError(f"unrecognised date {value!r}: use 2026-11-18 or 18/11/2569")
    return f"{d.day:02d}/{d.month:02d}/{d.year + 543}"


def be_to_date(be: str) -> date:
    d, m, y = (int(x) for x in be.split("/"))
    return date(y - 543, m, d)


def thai_short(be: str) -> str:
    """dd/mm/yyyy พ.ศ. -> '18 พ.ย. 2569', the form leave-status prints."""
    d, m, y = be.split("/")
    return f"{d} {THAI_MONTHS[int(m) - 1]} {y}"


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def resolve_type(value) -> int:
    if isinstance(value, int) or str(value).strip().isdigit():
        tid = int(value)
        if tid in TYPES:
            return tid
        raise UserError(f"unknown leave type id {tid}; see `types`")
    want = squash(str(value))
    exact = [t for t, (name, _) in TYPES.items() if squash(name) == want]
    if exact:
        return exact[0]
    loose = [t for t, (name, _) in TYPES.items() if want in squash(name)]
    if len(loose) == 1:
        return loose[0]
    names = ", ".join(f"{t}={n}" for t, (n, _) in TYPES.items())
    raise UserError(f"leave type {value!r} is {'ambiguous' if loose else 'unknown'}; "
                    f"one of: {names}")


def check_documents(paths: list[str]) -> list[Path]:
    out = []
    for p in paths:
        f = Path(p).expanduser().resolve()
        if not f.is_file():
            raise UserError(f"attachment not found: {f}")
        if f.suffix.lower() not in FILE_EXT:
            raise UserError(f"{f.name}: e-Leave accepts only .pdf .jpg .jpeg .png")
        if f.stat().st_size >= MAX_FILE:
            raise UserError(f"{f.name}: {f.stat().st_size / 1048576:.1f} MB — "
                            "e-Leave accepts files under 5 MB")
        out.append(f)
    return out


def parse_time(value: str) -> tuple[str, str]:
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", str(value).strip())
    if not m or int(m[1]) > 23 or int(m[2]) % 5 or int(m[2]) > 55:
        raise UserError(f"time {value!r}: use HH:MM with minutes in steps of 5")
    return f"{int(m[1]):02d}", m[2]


async def goto(page, url: str, attempts: int = 2, **kw) -> None:
    """Navigate, retrying once — a single dropped request on the BUU network
    (seen: net::ERR_NETWORK_CHANGED) would otherwise fail the whole run."""
    kw.setdefault("wait_until", "networkidle")
    for n in range(attempts):
        try:
            await page.goto(url, **kw)
            return
        except Exception:
            if n == attempts - 1:
                raise
            await page.wait_for_timeout(2000)


class Session:
    """Signed-in headless browser on e-leave; fresh login each run, nothing
    persisted to disk."""

    async def __aenter__(self):
        user = os.environ.get("ELEAVE_USERNAME") or os.environ.get("EDOC_USERNAME")
        pwd = os.environ.get("ELEAVE_PASSWORD") or os.environ.get("EDOC_PASSWORD")
        if not user or not pwd:
            raise ConfigError("EDOC_USERNAME / EDOC_PASSWORD (or ELEAVE_*) not set in "
                              f"{config_files()[-2]}")
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(headless=True)
        try:
            await self._login(user, pwd)
        except BaseException:
            await self.__aexit__()
            raise
        return self

    async def _login(self, user: str, pwd: str) -> None:
        ctx = await self.browser.new_context(
            viewport={"width": 1440, "height": 900}, user_agent=UA, locale="th-TH")
        self.page = page = await ctx.new_page()
        await goto(page, BASE + "/")
        if "Web Page Blocked" in await page.content():
            raise RuntimeError("blocked by the BUU web firewall (user agent?)")
        if "sso.buu.ac.th" in page.url:
            await page.fill("#username", user)
            await page.fill("#password", pwd)
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")
            auth = page.locator("xpath=//button[contains(text(),'Authorize')]"
                                " | //a[contains(text(),'Authorize')]")
            try:
                await auth.first.wait_for(state="visible", timeout=3000)
                await auth.first.evaluate("el => el.click()")
                await page.wait_for_load_state("networkidle")
            except PwTimeout:
                pass
        if not page.url.startswith(BASE) or "/auth" in page.url:
            raise ConfigError(f"login did not reach e-leave (landed on {page.url}) — "
                              "check EDOC_USERNAME / EDOC_PASSWORD")

    async def __aexit__(self, *exc):
        await self.browser.close()
        await self._pw.stop()


class ConfigError(Exception):
    pass


def main_text_js() -> str:
    # The page body minus menu/footer chrome.
    return """() => { const m = document.querySelector('.page-content') || document.body;
                      let t = m.innerText; const i = t.indexOf('Copyright');
                      return (i > 0 ? t.slice(0, i) : t); }"""


# ---------------------------------------------------------------- balance

async def cmd_balance(s: Session) -> dict:
    page = s.page
    await goto(page, BASE + "/leave-balances")
    text = await page.evaluate(main_text_js())
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = {"year": None, "vacation_remaining": None, "vacation_accumulated": None,
           "taken": [], "attendance": {}}
    for i, l in enumerate(lines):
        if m := re.fullmatch(r"ปีประเมิน\s*(\d{4})", l):
            out["year"] = out["year"] or m[1]
        elif l == "วันลาพักผ่อนคงเหลือ" and i + 1 < len(lines):
            out["vacation_remaining"] = _num(lines[i + 1])
        elif m := re.search(r"จำนวนวันลาพักผ่อนสะสม\s*([\d.]+)", l):
            out["vacation_accumulated"] = _num(m[1])
        elif (m := re.fullmatch(r"([\d.]+)\s*ครั้ง\s*([\d.]+)\s*วัน", l)) and i:
            out["taken"].append({"type": lines[i - 1], "times": _num(m[1]),
                                 "days": _num(m[2])})
        elif l in ("ไม่สแกนเช้า", "ไม่สแกนเย็น", "มาสาย") and i + 1 < len(lines):
            out["attendance"][l] = lines[i + 1]
    if out["vacation_remaining"] is None:
        raise RuntimeError("leave-balances page did not show วันลาพักผ่อนคงเหลือ")
    return out


def _num(s: str):
    try:
        f = float(s)
        return int(f) if f.is_integer() else f
    except ValueError:
        return s


# ---------------------------------------------------------------- status

STATUS_JS = """() => [...document.querySelectorAll('#accordion-leave-status, .accordion')]
  .filter(a => a.querySelector('.leave-status'))
  .map((a, i) => {
    const head = a.querySelector('.accordion-btn');
    const dates = (head.querySelector('strong')?.innerText || '').trim();
    const seqs = [...a.querySelectorAll('.box-commander')].flatMap(box => {
      const role = (box.querySelector('.section-name')?.innerText || '').trim();
      return [...box.querySelectorAll('.approval-seq')].map(q => ({
        role, status: (q.querySelector('.status-name')?.innerText || '').trim(),
        person: (q.querySelector('.person-name')?.innerText || '').trim(),
        position: (q.querySelector('.position-name')?.innerText || '').trim(),
        date: (q.querySelector('.date')?.innerText || '').trim()}));
    });
    const docs = [...a.querySelectorAll('.toolFile')].map(f => f.dataset.originalfilename);
    const cancel = [...a.querySelectorAll('button, a')]
      .some(b => /ยกเลิกใบลา/.test(b.innerText || ''));
    return {index: i, type: (head.querySelector('span')?.innerText || '').trim(),
            dates, status: (a.querySelector('.leave-status')?.innerText || '').trim(),
            approvals: seqs, documents: docs, cancellable: cancel};
  })"""


async def load_status_year(page, year: str | None) -> tuple[str, list[str]]:
    """Open leave-status on `year` (None = the site's preselected year)."""
    if not page.url.startswith(BASE + "/leave-status"):
        await goto(page, BASE + "/leave-status")
    years = await page.eval_on_selector_all("#BUD_YEAR option", "os => os.map(o => o.value)")
    current = await page.eval_on_selector("#BUD_YEAR", "e => e.value")
    if year and year != current:
        if year not in years:
            raise UserError(f"ปีประเมิน {year} not offered; available: {', '.join(years)}")
        async with page.expect_navigation(wait_until="networkidle"):
            await page.select_option("#BUD_YEAR", year)
        current = year
    return current, years


async def read_status(page) -> list[dict]:
    rows = await page.evaluate(STATUS_JS)
    for r in rows:
        if m := re.search(r"\(\s*([\d.]+)\s*วัน\s*\)", r["dates"]):
            r["days"] = _num(m[1])
        r["dates"] = re.sub(r"\s*\(.*\)\s*$", "", r["dates"])
    return rows


async def cmd_status(s: Session, years: list[str] | None) -> dict:
    page = s.page
    current, offered = await load_status_year(s.page, None)
    if not years:
        years = [current] + ([str(int(current) - 1)] if str(int(current) - 1) in offered else [])
    out = []
    for y in years:
        await load_status_year(page, y)
        out.append({"year": y, "leaves": await read_status(page)})
    return {"default_year": current, "years": out}


# ---------------------------------------------------------------- the form

async def open_form(page, tid: int) -> None:
    """Leave-request page with type `tid` selected and its sub-form loaded."""
    await goto(page, BASE + "/leave-request")
    abroad = TYPES[tid][1]
    radio = "OUT" if abroad else "IN"
    if not await page.is_checked(f"#TYPE_COUNTRY_{radio}"):
        await page.click(f"label[for=TYPE_COUNTRY_{radio}]")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_function(
            "v => [...document.querySelectorAll('#TYPE_ID option')].some(o => o.value == v)",
            arg=str(tid), timeout=15000)
    offered = await page.eval_on_selector_all("#TYPE_ID option", "os => os.map(o => o.value)")
    if str(tid) not in offered:
        raise UserError(f"{TYPES[tid][0]} is not offered to this account")
    await page.evaluate("v => $('#TYPE_ID').val(v).trigger('change')", str(tid))
    await page.wait_for_load_state("networkidle")
    await page.wait_for_function(
        "v => $('#TYPE_ID').val() == v && document.querySelector('#load-leave-request #LED_STARTDATE')",
        arg=str(tid), timeout=15000)
    await page.wait_for_timeout(500)


FIELDS_JS = """() => {
 const lab = e => { const l = e.id && document.querySelector(`label[for="${e.id}"]`);
   return (l ? l.innerText : (e.closest('.group')?.querySelector('label')?.innerText || '')).trim(); };
 const skip = /^(startMinDate|startMaxDate|startDefaultDate|endMinDate|endMaxDate|endDefaultDate|disabledDates|LED_CALENDARDAY|LED_REALDAY)$/;
 return [...document.querySelectorAll('#load-leave-request input, #load-leave-request select, #load-leave-request textarea')]
  .filter(e => e.name && !skip.test(e.name))
  .map(e => ({name: e.name, kind: e.type, label: lab(e),
    visible: e.type != 'hidden' && e.offsetParent !== null,
    options: e.tagName == 'SELECT' && e.options.length <= 12
      ? [...e.options].map(o => o.text.trim()) : undefined,
    n_options: e.tagName == 'SELECT' ? e.options.length : undefined}));
}"""


async def cmd_fields(s: Session, tid: int) -> dict:
    await open_form(s.page, tid)
    return {"type_id": tid, "type": TYPES[tid][0], "supported": tid in SUPPORTED,
            "fields": await s.page.evaluate(FIELDS_JS)}


async def set_multi(page, name: str, wanted: list[str], tags: bool = False) -> list[str]:
    """Pick options of a select2 multi-select by visible name. Returns labels."""
    sel = f"#load-leave-request select[name='{name}']"
    if not await page.locator(sel).count():
        raise UserError(f"this leave type has no {name} field")
    opts = await page.eval_on_selector_all(
        sel + " option", "os => os.filter(o => o.value).map(o => [o.value, o.text.trim()])")
    values, labels = [], []
    for w in wanted:
        key = squash(w)
        hits = [o for o in opts if squash(o[1]) == key] or \
               [o for o in opts if key and key in squash(o[1])]
        if len(hits) == 1:
            values.append(hits[0][0]); labels.append(hits[0][1])
        elif tags and not hits:
            values.append(w); labels.append(w)
        else:
            some = ", ".join(h[1] for h in hits[:8])
            raise UserError(f"{name}: {w!r} " + (f"is ambiguous: {some}" if hits
                                                   else "matches no option"))
    await page.evaluate("""([sel, values]) => {
        const $s = $(sel);
        for (const v of values)
          if (!$s.find('option').filter((_, o) => o.value === v).length)
            $s.append(new Option(v, v, false, false));
        $s.val(values).trigger('change'); }""", [sel, values])
    return labels


async def fill_request(page, spec: dict) -> dict:
    """Fill the form from `spec`; return what was set and the day count.
    Raises UserError on anything the site would refuse."""
    tid = resolve_type(spec.get("type", ""))
    if tid not in SUPPORTED:
        raise UserError(f"{TYPES[tid][0]} is not automated — submit it on {BASE} "
                        f"(`eleave.py fields {tid}` lists what the form asks for)")
    start = to_be(spec["start"]) if spec.get("start") else None
    if not start:
        raise UserError("spec needs a start date")
    end = to_be(spec.get("end") or spec["start"])
    if be_to_date(end) < be_to_date(start):
        raise UserError("end date is before start date")
    single = start == end
    sp = PERIODS.get(spec.get("start_period", "full"))
    ep = PERIODS.get(spec.get("end_period", "full"))
    if sp is None or ep is None:
        raise UserError("start_period / end_period: full, morning or afternoon")
    if not single and (sp == "2" or ep == "3"):
        raise UserError("multi-day leave can start with an afternoon half-day and end "
                        "with a morning half-day, not the other way round")
    docs = check_documents(spec.get("documents") or [])

    await open_form(page, tid)
    # startMinDate is set only where the site restricts it (ลาพักผ่อน: tomorrow).
    min_date = await page.evaluate("() => $('#startMinDate').val() || ''")
    if min_date and be_to_date(start) < be_to_date(min_date):
        raise UserError(f"{TYPES[tid][0]} can start no earlier than {min_date}")

    if tid == 9:
        for key, hid, mid in (("start_time", "LED_STARTHOUR", "LED_STARTMINUTE"),
                              ("end_time", "LED_ENDHOUR", "LED_ENDMINUTE")):
            if spec.get(key):
                h, m = parse_time(spec[key])
                await page.select_option(f"#{hid}", h)
                await page.select_option(f"#{mid}", m)

    calc = await set_dates(page, start, end)
    if tid != 9:
        # Dates first (their handler may reset the periods), then periods.
        await page.evaluate("v => $('#LEDD_STARTTYPE').val(v)", sp)
        if not single:
            await page.evaluate("v => $('#LEDD_ENDTYPE').val(v)", ep)
        async with page.expect_response("**/calculate-leave-days") as r:
            await page.evaluate("() => $('#LEDD_STARTTYPE').trigger('change')")
        calc = await (await r.value).json()
        got = await page.evaluate("() => [$('#LEDD_STARTTYPE').val(), $('#LEDD_ENDTYPE').val()]")
        if got[0] != sp or (not single and got[1] != ep):
            raise UserError(f"the site would not accept that half-day combination "
                            f"(start={got[0]}, end={got[1]})")

    button = calc.get("button") or {}
    if button.get("disabled"):
        raise UserError(f"e-Leave refuses this request: {button.get('message') or 'no reason given'}")
    validate = calc.get("validate") or {}
    doc_required = (validate.get("field") == "LED_DOCUMENT" and validate.get("rules") == "add")
    if doc_required and not docs:
        raise UserError(f"evidence is required: {validate.get('message') or 'attach a document'}")

    if spec.get("reason"):
        await page.fill("#LED_REMARK", str(spec["reason"]))
    if tid == 9 and spec.get("place"):
        await page.fill("#LED_PLACE", str(spec["place"]))
    set_people = []
    if spec.get("with_people"):
        set_people = await set_multi(page, "LED_WITHPEOPLE[]", spec["with_people"])
    if spec.get("with_outsiders"):
        await set_multi(page, "LED_WITHOUTSIDER[]", spec["with_outsiders"], tags=True)
    countries = []
    if TYPES[tid][1]:
        if spec.get("objective"):
            await page.fill("#LED_OBJECTIVE", str(spec["objective"]))
        if spec.get("countries"):
            countries = await set_multi(page, "LED_COUNTRY[]", spec["countries"])
        cs = to_be(spec.get("country_start") or spec["start"])
        ce = to_be(spec.get("country_end") or spec.get("end") or spec["start"])
        await page.evaluate("([a, b]) => { $('#LED_STARTDATE_COUNTRY').val(a); "
                            "$('#LED_ENDDATE_COUNTRY').val(b); }", [cs, ce])
    for name, value in (spec.get("fields") or {}).items():
        loc = page.locator(f"#load-leave-request [name='{name}']")
        if not await loc.count():
            raise UserError(f"fields: this form has no {name!r}")
        await loc.first.fill(str(value))

    inputs = page.locator("#load-leave-request input[type=file]")
    n_inputs = await inputs.count()
    if docs:
        if not n_inputs:
            raise UserError(f"{TYPES[tid][0]} has no attachment field")
        if n_inputs == 1 and await inputs.first.get_attribute("multiple") is not None:
            await inputs.first.set_input_files([str(d) for d in docs])
        elif len(docs) > n_inputs:
            raise UserError(f"{len(docs)} attachments given, the form has {n_inputs} slot(s)")
        else:
            for i, d in enumerate(docs):
                await inputs.nth(i).set_input_files(str(d))

    return {"type_id": tid, "type": TYPES[tid][0], "start": start, "end": end,
            "calendar_days": calc.get("calendarLeave"), "working_days": calc.get("actualLeave"),
            "evidence_required": doc_required, "documents": [d.name for d in docs],
            "with_people": set_people, "countries": countries}


async def set_dates(page, start: str, end: str) -> dict:
    async with page.expect_response("**/calculate-leave-days") as r:
        await page.evaluate("([a, b]) => { $('#LED_STARTDATE').val(a); "
                            "$('#LED_ENDDATE').val(b).trigger('change'); }", [start, end])
    calc = await (await r.value).json()
    await page.wait_for_timeout(300)
    return calc


async def submit_form(page) -> None:
    """Click ยื่นใบลา and wait for the review page, or explain why not."""
    btn = page.locator("#leave-request-submit")
    if not await btn.count() or not await btn.is_visible():
        msg = (await page.inner_text("#submit-condition-message-under-calendar")).strip()
        raise UserError(f"e-Leave hides the submit button: {msg or 'no reason shown'}")
    try:
        async with page.expect_navigation(wait_until="networkidle", timeout=30000):
            await btn.click()
    except PwTimeout:
        errors = await page.eval_on_selector_all(
            "label.error, .error:not(input):not(select)",
            "es => es.filter(e => e.offsetParent && e.innerText.trim()).map(e => e.innerText.trim())")
        raise UserError("the form did not submit: " + ("; ".join(errors) or "no message shown"))
    if page.url.rstrip("/").endswith("/leave-request"):
        errors = await page.eval_on_selector_all(
            ".alert, .invalid-feedback, .text-danger, .color-red",
            "es => es.filter(e => e.offsetParent && e.innerText.trim()).map(e => e.innerText.trim())")
        raise UserError("e-Leave rejected the request: " + ("; ".join(errors) or "no message shown"))


REVIEW_JS = """() => {
  const btn = [...document.querySelectorAll('button, a, input[type=submit]')]
    .find(b => /ยืนยัน/.test(b.innerText || b.value || '') && b.offsetParent);
  const box = btn && (btn.closest('form') || btn.closest('.card') || btn.closest('.content'));
  return {has_button: !!btn, text: (box || document.body).innerText.replace(/\\s*ยืนยัน\\s*$/, '').trim()};
}"""


def preview_id(letter: str) -> str:
    return hashlib.sha256(squash(letter).encode()).hexdigest()[:12]


async def cmd_request(s: Session, spec: dict, confirm: str | None) -> dict:
    page = s.page
    filled = await fill_request(page, spec)
    await submit_form(page)
    review = await page.evaluate(REVIEW_JS)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shot = DATA_DIR / f"{stamp}-preview.png"
    await page.screenshot(path=str(shot), full_page=True)
    (DATA_DIR / f"{stamp}-preview.html").write_text(await page.content(), encoding="utf-8")
    pid = preview_id(review["text"])
    out = {**filled, "letter": review["text"], "preview_id": pid,
           "screenshot": str(shot), "review_url": page.url, "submitted": False}
    if not review["has_button"]:
        out["warning"] = ("the review page has no ยืนยัน button — layout differs from the "
                          f"manual; see {shot}")
        return out
    if confirm is None:
        return out
    if confirm != pid:
        raise UserError(f"the ใบลา rendered now (preview_id {pid}) differs from the one "
                        f"previewed ({confirm}); nothing was submitted — preview again")

    btn = page.locator("button:visible, a:visible, input[type=submit]:visible").filter(
        has_text=re.compile("ยืนยัน")).first
    try:
        await btn.click(timeout=10000)
    except PwTimeout:
        raise UserError(f"could not click ยืนยัน on the review page; nothing was "
                        f"submitted — see {shot}")
    dialog = page.locator(".jconfirm-box button, .jconfirm-buttons button").filter(
        has_text=re.compile("ยืนยัน"))
    try:
        await dialog.first.wait_for(state="visible", timeout=8000)
        async with page.expect_navigation(wait_until="networkidle", timeout=60000):
            await dialog.first.click()
    except PwTimeout:
        out["submitted"] = "unclear"
        out["warning"] = ("no confirmation dialog / navigation after ยืนยัน — do NOT retry; "
                          "run `status` to see whether the request was saved")
        return out
    body = await page.evaluate(main_text_js())
    out["submitted"] = True if "บันทึกข้อมูลเรียบร้อยแล้ว" in body else "unclear"
    if out["submitted"] != True:
        out["warning"] = ("no บันทึกข้อมูลเรียบร้อยแล้ว message — do NOT retry; run "
                          "`status` to check")
    shot2 = DATA_DIR / f"{stamp}-submitted.png"
    await page.screenshot(path=str(shot2), full_page=True)
    out["screenshot_after"] = str(shot2)
    if page.url.startswith(BASE + "/leave-status"):
        out["status_now"] = await read_status(page)
    return out


# ---------------------------------------------------------------- cancel

async def cmd_cancel(s: Session, start: str, year: str | None, confirm: bool) -> dict:
    page = s.page
    start_be = to_be(start)
    key = squash(thai_short(start_be))
    current, offered = await load_status_year(page, year)
    rows = await read_status(page)
    matches = [r for r in rows if squash(r["dates"]).startswith(key)]
    if not matches and not year:
        prev = str(int(current) - 1)
        if prev in offered:
            await load_status_year(page, prev)
            rows = await read_status(page)
            matches = [r for r in rows if squash(r["dates"]).startswith(key)]
    if not matches:
        raise UserError(f"no leave starting {thai_short(start_be)} in ปีประเมิน "
                        f"{year or current}{'' if year else ' or the year before'}")
    if len(matches) > 1:
        raise UserError("several leaves start that day: " +
                        "; ".join(f"{m['type']} {m['dates']} ({m['status']})" for m in matches))
    row = matches[0]
    out = {"leave": row, "cancelled": False}
    if "รออนุมัติ" not in row["status"]:
        raise UserError(f"{row['type']} {row['dates']} is '{row['status']}' — e-Leave "
                        "only cancels a request that has not been approved yet")
    if not confirm:
        return out

    item = page.locator(".accordion").filter(has=page.locator(".leave-status")).nth(row["index"])
    await item.locator(".accordion-btn").click()
    btn = item.locator("button:visible, a:visible").filter(
        has_text=re.compile("ยกเลิกใบลา")).first
    try:
        await btn.click(timeout=10000)
    except PwTimeout:
        raise UserError("no clickable ยกเลิกใบลา button on that entry; nothing was cancelled")
    dialog = page.locator(".jconfirm-box button, .jconfirm-buttons button").filter(
        has_text=re.compile("ยืนยัน"))
    try:
        await dialog.first.wait_for(state="visible", timeout=8000)
        async with page.expect_navigation(wait_until="networkidle", timeout=60000):
            await dialog.first.click()
    except PwTimeout:
        out["cancelled"] = "unclear"
        out["warning"] = "no dialog / navigation after ยกเลิกใบลา — run `status` to check"
        return out
    body = await page.evaluate(main_text_js())
    out["cancelled"] = True if "ส่งอีเมลเรียบร้อยแล้ว" in body else "unclear"
    if out["cancelled"] != True:
        out["warning"] = "no ส่งอีเมลเรียบร้อยแล้ว message — run `status` to check"
    return out


# ---------------------------------------------------------------- output

def render(cmd: str, res: dict) -> None:
    if cmd == "balance":
        print(f"ปีประเมิน {res['year']}: วันลาพักผ่อนคงเหลือ {res['vacation_remaining']} วัน "
              f"(สะสม {res['vacation_accumulated']})")
        for t in res["taken"]:
            print(f"  {t['type']}: {t['times']} ครั้ง {t['days']} วัน")
        for k, v in res["attendance"].items():
            print(f"  {k}: {v}")
    elif cmd == "status":
        for y in res["years"]:
            print(f"ปีประเมิน {y['year']}:" + ("" if y["leaves"] else " ไม่พบข้อมูลการลา"))
            for l in y["leaves"]:
                print(f"  {l['type']}  {l['dates']} ({l.get('days', '?')} วัน)  — {l['status']}")
    elif cmd == "types":
        for t in res["types"]:
            print(f"  {t['id']:>2}  {t['name']}{' (ต่างประเทศ)' if t['abroad'] else ''}"
                  f"{'' if t['supported'] else '  — website only'}")
    elif cmd == "fields":
        print(f"{res['type']} ({res['type_id']}){'' if res['supported'] else ' — website only'}")
        for f in res["fields"]:
            if f["visible"]:
                print(f"  {f['name']:<40} {f['kind']:<16} {f['label'][:50]}")
    elif cmd == "request":
        print(f"{res['type']} {res['start']} – {res['end']}: {res['working_days']} วันทำการ "
              f"({res['calendar_days']} วันตามปฏิทิน)")
        if res["documents"]:
            print("แนบ: " + ", ".join(res["documents"]))
        print("\n" + res["letter"] + "\n")
        print(f"preview_id: {res['preview_id']}   screenshot: {res['screenshot']}")
        if res.get("warning"):
            print("WARNING: " + res["warning"])
        print({False: "NOT submitted (preview only).", True: "SUBMITTED."}.get(
            res["submitted"], "Submission outcome UNCLEAR."))
    elif cmd == "cancel":
        l = res["leave"]
        print(f"{l['type']} {l['dates']} — {l['status']}")
        if res.get("warning"):
            print("WARNING: " + res["warning"])
        print({False: "NOT cancelled (preview only).", True: "CANCELLED."}.get(
            res["cancelled"], "Cancel outcome UNCLEAR."))


async def run(args) -> dict:
    if args.cmd == "types":
        return {"types": [{"id": t, "name": n, "abroad": a, "supported": t in SUPPORTED}
                          for t, (n, a) in TYPES.items()]}
    spec = None
    if args.cmd == "request":
        try:
            spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise UserError(f"cannot read spec {args.spec}: {e}")
        # Validate offline before logging in.
        tid = resolve_type(spec.get("type", ""))
        if tid not in SUPPORTED:
            raise UserError(f"{TYPES[tid][0]} is not automated — submit it on {BASE} "
                            f"(`eleave.py fields {tid}` lists what the form asks for)")
        check_documents(spec.get("documents") or [])
    async with Session() as s:
        if args.cmd == "balance":
            return await cmd_balance(s)
        if args.cmd == "status":
            return await cmd_status(s, args.year)
        if args.cmd == "fields":
            return await cmd_fields(s, resolve_type(args.type))
        if args.cmd == "request":
            return await cmd_request(s, spec, args.confirm)
        if args.cmd == "cancel":
            return await cmd_cancel(s, args.start, args.year, args.confirm)
    raise AssertionError(args.cmd)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(description="BUU e-Leave: balance, status, request, cancel")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("balance", help="วันลาคงเหลือ and leave taken this ปีประเมิน")
    p = sub.add_parser("status", help="สถานะการลา")
    p.add_argument("--year", action="append", help="ปีประเมิน (พ.ศ.), repeatable")
    sub.add_parser("types", help="leave types and which are automated")
    p = sub.add_parser("fields", help="list the form fields of one leave type")
    p.add_argument("type")
    p = sub.add_parser("request", help="ยื่นใบลา (preview unless --confirm)")
    p.add_argument("spec", help="JSON request spec")
    p.add_argument("--confirm", metavar="PREVIEW_ID",
                   help="submit; must match the preview_id of the previewed ใบลา")
    p = sub.add_parser("cancel", help="ยกเลิกใบลา that is still รออนุมัติ")
    p.add_argument("--start", required=True, help="start date of the leave")
    p.add_argument("--year", help="ปีประเมิน to look in")
    p.add_argument("--confirm", action="store_true", help="actually cancel")
    # Allow --json after the subcommand too.
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    args = ap.parse_args()
    load_env()

    # A run that writes nothing is retried once: the BUU network drops the odd
    # request (net::ERR_NETWORK_CHANGED). A --confirm run is never retried; a
    # request preview is safe to retry, since the review step saves nothing.
    writes = bool(getattr(args, "confirm", None))
    try:
        try:
            res = asyncio.run(run(args))
        except (UserError, ConfigError):
            raise
        except Exception:
            if writes:
                raise
            res = asyncio.run(run(args))
        code = EXIT_OK
    except UserError as e:
        res, code = {"error": str(e)}, EXIT_INPUT
    except ConfigError as e:
        res, code = {"error": str(e), "config_error": True}, EXIT_CONFIG
    except Exception as e:
        res, code = {"error": f"{type(e).__name__}: {e}"}, EXIT_FAIL
    res = {"ok": code == EXIT_OK, **res}
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif code:
        print(f"error: {res['error']}", file=sys.stderr)
    else:
        render(args.cmd, res)
    return code


if __name__ == "__main__":
    sys.exit(main())
