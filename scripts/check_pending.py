#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "playwright==1.60.0",
# ]
# ///
"""
check_pending.py — what is waiting for me in BUU eDoc and e-Signature?

    uv run check_pending.py                 human-readable report
    uv run check_pending.py --json          machine-readable, for Claude
    uv run check_pending.py --only esign    one system only

READ-ONLY. It signs in, counts, and closes the browser. It never opens,
receives (รับ), signs, forwards or acknowledges a document — opening a document
in eDoc would mark it read, which is a real side effect on the user's workload.

Playwright logic started as a port of NKAutomationAI/eDashboard
(edoc_checker.py, esign_checker.py); the eDoc half has since been rewritten —
see "WHAT COUNTS AS PENDING" below.

CREDENTIALS — ~/.config/nk-work-kit/.env (see scripts/.env.example)
--------------------------------------------------------------------
Falls back to a `.env` beside this script. Keep it in ~/.config: a plugin is
installed into a version-pinned directory, so anything stored next to the
script is lost on the next plugin upgrade.

    EDOC_USERNAME, EDOC_PASSWORD    BUU login
    EDOC_INBOX                      optional. Comma-separated inbox names to
                                    check. Empty = every inbox the account has.
    ESIGN_USERNAME, ESIGN_PASSWORD  optional; falls back to the EDOC_ pair

WHAT COUNTS AS PENDING
----------------------
eDoc's own "รายการหนังสือค้างรับ" list is the inbox of documents not yet
received. Two numbers come out of it and they are NOT the same:

  * `pending`  — rows marked ใหม่/ยังไม่ได้อ่าน (`a.home-list-open-item.unread`).
                 This is the actionable number.
  * `in_list`  — every row in the ค้างรับ list. On a shared inbox this is a
                 backlog going back years, so it is reported but never used as
                 the headline count.

The server caps the list at 500 rows; when `in_list` hits 500 the entry is
marked `list_capped` and the real backlog may be larger. The list is also
filtered to the current Buddhist-era year, eDoc's own default — pending items
older than that are not shown by eDoc and so are not counted here.

HARD-WON DETAILS — do not "simplify" these away:
  * An account has SEVERAL inboxes (personal, faculty, department, ...), each
    an `a.home-shortcuts-open-by-listsource` with its own `data-entity-id`.
    They are enumerated live rather than configured, because a wrong name in
    config used to produce a silent "0 pending" that looked like good news.
    A configured name that is not on the ทางลัด tab is NOT an error: it was
    observed (Sept 2026, by the user; not confirmed against eDoc itself) that
    an inbox with no new documents can drop off the tab. It is reported as
    `absent` with 0 new, plus a note naming the inboxes that ARE listed so a
    typo can still be spotted. An ambiguous name is still a hard error. This
    is only safe because the tab is read with a stability poll (links load in
    stages) — keep the poll, or a slow load becomes a false "nothing new".
  * The shortcut tab bar disappears once an inbox is open, so each inbox is
    loaded by navigating straight to `home_list.aspx` with its EntityId
    instead of clicking back and forth. No frames needed on that page.
  * Login success is asserted on the post-login URL. Without that check a
    failed login walks the same code path as an empty inbox.
  * eSign reuses the SAME id (`totalNotBeenSigned`) for the รอลงนาม badge and
    the เอกสารลับ badge, so each badge must be scoped to its own sidebar <li>
    or you silently read the wrong number.
  * eSign shows an SSO "Authorize" button on first login only; it is clicked
    through .evaluate() because an overlay intercepts a normal click.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    from playwright.async_api import async_playwright, TimeoutError as PwTimeout
except ImportError:
    sys.exit("playwright is not installed. Run this script with `uv run`, "
             "which installs it automatically.")

EDOC_URL = "https://doc.buu.ac.th/docweb/v2/"
EDOC_LIST = ("https://doc.buu.ac.th/docweb/v2/home_list.aspx?"
             "listSource=2&inShared=false&FolderType=20&EntityId={eid}&FolderId=0")
ESIGN_URL = "https://e-sign.buu.ac.th"
MAX_ITEMS = 10
ROW_CAP = 500  # server-side cap on the ค้างรับ list
DEFAULT_TIMEOUT = 180  # seconds per system

EDOC_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
ESIGN_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

EXIT_OK = 0
EXIT_ALL_FAILED = 1
EXIT_CONFIG = 3

# Per unread row: subject from the anchor, then the neighbouring non-empty
# cells (number before it, date and sender after it).
ROW_JS = """(max) => {
  const rows = [...document.querySelectorAll('a.home-list-open-item.unread')];
  const total = document.querySelectorAll('a.home-list-open-item').length;
  const items = rows.slice(0, max).map(a => {
    const tr = a.closest('tr');
    const subject = (a.innerText || '').trim();
    let number = '', date = '', sender = '';
    if (tr) {
      const tds = [...tr.querySelectorAll('td')]
        .map(td => (td.innerText || '').trim()).filter(Boolean);
      const j = tds.indexOf(subject);
      if (j > -1) {
        number = tds[j - 1] || '';
        date   = tds[j + 1] || '';
        sender = tds[j + 2] || '';
      }
    }
    return {number, subject: subject.slice(0, 160), date, sender};
  });
  return {unread: rows.length, total, items};
}"""


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


async def goto(page, url: str, attempts: int = 2, **kw) -> None:
    """Navigate, retrying once — a single dropped request on the BUU network
    would otherwise be reported as a failed check."""
    for n in range(attempts):
        try:
            await page.goto(url, **kw)
            return
        except Exception:
            if n == attempts - 1:
                raise
            await page.wait_for_timeout(2000)


def system(name: str, pending: int, items=None, error=None, **extra) -> dict:
    out = {"name": name, "pending": pending, "error": error, "items": items or []}
    out.update(extra)
    return out


async def check_edoc(username: str, password: str, wanted: list[str]) -> dict:
    if not username or not password:
        return system("eDoc", 0, error="EDOC_USERNAME / EDOC_PASSWORD not set",
                      config_error=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900}, user_agent=EDOC_UA)
            page = await context.new_page()

            await goto(page, EDOC_URL, wait_until="domcontentloaded")
            await page.wait_for_selector("#txtLogin", state="visible", timeout=20000)
            await page.fill("#txtLogin", username)
            await page.fill("#txtPassword", password)
            async with page.expect_navigation(wait_until="networkidle"):
                await page.click("#btnLogin")

            if "home.aspx" not in page.url:
                await browser.close()
                return system("eDoc", 0, error=(
                    "login did not reach home.aspx — check EDOC_USERNAME / "
                    f"EDOC_PASSWORD (landed on {page.url})"))

            # Enumerate the account's inboxes from the ทางลัด (shortcuts) tab.
            inner = page.frame_locator("#iframeHomeBody").frame_locator("#home_list_full")
            await inner.locator(".home-content-tab-shortcuts").click()
            # The links load in stages: a fixed sleep has read none, or only the
            # first of five (see edoc_digest.open_shortcuts). Poll until the list
            # is non-empty and unchanged for ~1.5 s — a missing name is reported
            # as "no new documents" below, so a partial read must not reach it.
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 20
            boxes, stable, frame = [], 0, None
            while loop.time() < deadline:
                frame = next((f for f in page.frames if f.name == "home_list"), None)
                now = []
                if frame is not None:
                    try:
                        now = await frame.evaluate(
                            """() => [...document.querySelectorAll('a.home-shortcuts-open-by-listsource')]
                                 .map(a => ({name: a.innerText.trim(), eid: a.dataset.entityId}))
                                 .filter(b => b.name && b.eid)""")
                    except Exception:
                        now = []  # frame mid-navigation
                stable = stable + 1 if now and now == boxes else 0
                boxes = now
                if stable >= 3:
                    break
                await asyncio.sleep(0.5)
            if frame is None:
                await browser.close()
                return system("eDoc", 0, error="inbox frame (home_list) not found")
            if not boxes:
                await browser.close()
                return system("eDoc", 0, error="no inboxes found on the ทางลัด tab")

            available = [b["name"] for b in boxes]
            unknown: list[str] = []
            if wanted:
                # Match on the name with all whitespace removed. Thai titles are
                # written both "ผศ. ดร. ณยศ" and "ผศ.ดร.ณยศ", and a config that
                # differs only in those spaces is a typo, not a different person.
                # Ambiguity is still an error — never guess between two inboxes.
                def key(s: str) -> str:
                    return "".join(s.split())

                chosen = []
                for want in wanted:
                    exact = [b for b in boxes if b["name"] == want]
                    hits = exact or [b for b in boxes if key(b["name"]) == key(want)]
                    if not hits:
                        unknown.append(want)
                    elif len(hits) > 1:
                        await browser.close()
                        return system("eDoc", 0, config_error=True, error=(
                            f"EDOC_INBOX name {want!r} matches more than one "
                            "inbox: " + " | ".join(h["name"] for h in hits)))
                    elif hits[0] not in chosen:
                        chosen.append(hits[0])
                boxes = chosen

            inboxes, items = [], []
            for box in boxes:
                await goto(page, EDOC_LIST.format(eid=quote(box["eid"])),
                          wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
                data = await page.evaluate(ROW_JS, MAX_ITEMS)
                entry = {
                    "name": box["name"],
                    "entity_id": box["eid"],
                    "pending": data["unread"],
                    "in_list": data["total"],
                    "items": data["items"],
                }
                if data["total"] >= ROW_CAP:
                    entry["list_capped"] = True
                inboxes.append(entry)
                for it in data["items"]:
                    items.append(dict(it, inbox=box["name"]))

            await browser.close()
            extra = {}
            if unknown:
                # Not on the ทางลัด tab after a stable read. Observed (Sept 2026)
                # to happen when the inbox has no new documents, so this is not
                # a config error. The listed names go in the note so a real typo
                # is still visible.
                for want in unknown:
                    inboxes.append({"name": want, "entity_id": None, "pending": 0,
                                    "in_list": 0, "items": [], "absent": True})
                extra["note"] = ("not on the ทางลัด tab, most likely no new documents: "
                                 + ", ".join(unknown) + " — listed now: " + " | ".join(available))
            return system("eDoc", sum(b["pending"] for b in inboxes),
                          items[:MAX_ITEMS], inboxes=inboxes, **extra)

    except Exception as e:
        return system("eDoc", 0, error=f"{type(e).__name__}: {e}")


async def check_esign(username: str, password: str) -> dict:
    if not username or not password:
        return system("eSign", 0, error="ESIGN_USERNAME / ESIGN_PASSWORD not set",
                      config_error=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080}, user_agent=ESIGN_UA)
            page = await context.new_page()

            await goto(page, ESIGN_URL)
            await page.locator('[name="username"]').fill(username)
            await page.locator('[name="password"]').fill(password)
            await page.locator("button[type='submit']").click()
            await page.wait_for_load_state("networkidle")

            auth = page.locator(
                "xpath=//button[contains(text(),'Authorize')] | //a[contains(text(),'Authorize')]")
            try:
                await auth.first.wait_for(state="visible", timeout=3000)
                await auth.first.evaluate("el => el.click()")
                await page.wait_for_load_state("networkidle")
            except PwTimeout:
                pass

            sidebar = page.locator("span#totalNotBeenSigned").first
            try:
                await sidebar.wait_for(state="attached", timeout=8000)
            except PwTimeout:
                await browser.close()
                return system("eSign", 0, error=(
                    "signed-in page has no signature badge — check "
                    f"ESIGN_USERNAME / ESIGN_PASSWORD (landed on {page.url})"))

            async def badge_count(li_selector: str) -> int:
                try:
                    badge = page.locator(f"{li_selector} span#totalNotBeenSigned").first
                    await badge.wait_for(state="attached", timeout=5000)
                    raw = await badge.get_attribute("data-count") or "0"
                    return int(raw) if raw.isdigit() else 0
                except PwTimeout:
                    return 0

            pending = await badge_count(
                'li.list-group-item:has(a[href="https://e-sign.buu.ac.th/signDocument"])')
            secret = await badge_count(
                'li.list-group-item:has(a[href^="https://e-sign.buu.ac.th/secretDocument/"])'
                ":has(span#totalNotBeenSigned)")

            items = []
            try:
                rows = page.locator("tr:has(a.btn.btn-outline-success) a.title-document")
                for i in range(min(await rows.count(), MAX_ITEMS)):
                    text = (await rows.nth(i).inner_text()).strip()
                    if text:
                        items.append({"subject": text[:160]})
            except Exception:
                pass

            # The landing page lists รอลงนาม documents only. เอกสารลับ live
            # behind /secretDocument/ and are deliberately NOT opened here: a
            # status check should not pull secret document titles into a
            # terminal or a chat log. They are counted, never named.
            note = None
            if secret and not items:
                note = ("titles not listed: the pending items are เอกสารลับ, "
                        "which are counted but not opened by this check")
            elif secret:
                note = (f"{secret} เอกสารลับ are counted but not named; the "
                        "titles listed are รอลงนาม only")

            await browser.close()
            return system("eSign", pending + secret, items,
                          breakdown={"รอลงนาม": pending, "เอกสารลับ": secret},
                          note=note)

    except Exception as e:
        return system("eSign", 0, error=f"{type(e).__name__}: {e}")


async def run(which: str, timeout: int) -> list[dict]:
    edoc_user = os.environ.get("EDOC_USERNAME", "")
    edoc_pass = os.environ.get("EDOC_PASSWORD", "")
    wanted = [n.strip() for n in os.environ.get("EDOC_INBOX", "").split(",") if n.strip()]
    esign_user = os.environ.get("ESIGN_USERNAME") or edoc_user
    esign_pass = os.environ.get("ESIGN_PASSWORD") or edoc_pass

    async def guard(name: str, coro):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            return system(name, 0, error=f"timed out after {timeout}s")

    def fresh(name: str):
        if name == "eDoc":
            return check_edoc(edoc_user, edoc_pass, wanted)
        return check_esign(esign_user, esign_pass)

    names = [n for n in ("eDoc", "eSign")
             if which == "all" or which == n.lower()]
    results = await asyncio.gather(*(guard(n, fresh(n)) for n in names))

    # One retry per failed system. Both sites drop the occasional request, and
    # a transient blip should not be reported as "could not be checked".
    # A config error is not transient, so it is never retried.
    retry = [i for i, r in enumerate(results)
             if r["error"] and not r.get("config_error")]
    if retry:
        again = await asyncio.gather(
            *(guard(results[i]["name"], fresh(results[i]["name"])) for i in retry))
        results = list(results)
        for i, r in zip(retry, again):
            results[i] = r
    return list(results)


def render(systems: list[dict]) -> None:
    print(f"Pending documents — {datetime.now():%Y-%m-%d %H:%M}\n")
    for s in systems:
        if s["error"]:
            print(f"{s['name']}  !  {s['error']}\n")
            continue

        head = "nothing pending" if s["pending"] == 0 else f"{s['pending']} pending"
        if s.get("breakdown"):
            parts = [f"{k} {v}" for k, v in s["breakdown"].items() if v]
            if parts:
                head += "  (" + ", ".join(parts) + ")"
        print(f"{s['name']}  —  {head}")
        if s.get("note"):
            print(f"      ({s['note']})")

        for box in s.get("inboxes", []):
            if box.get("absent"):
                print(f"  · {box['name']}: not listed (likely no new documents)")
                continue
            backlog = f"{box['in_list']}{'+' if box.get('list_capped') else ''} in ค้างรับ"
            mark = "·" if box["pending"] == 0 else "•"
            print(f"  {mark} {box['name']}: {box['pending']} new  ({backlog})")
            for it in box["items"]:
                num = f"{it['number']}  " if it.get("number") else ""
                print(f"      - {num}{it['subject']}")
                if it.get("sender") or it.get("date"):
                    print(f"        {it.get('sender','')}  {it.get('date','')}".rstrip())
            if box["pending"] > len(box["items"]):
                print(f"      … and {box['pending'] - len(box['items'])} more")

        if "inboxes" not in s:
            for it in s["items"]:
                print(f"      - {it['subject']}")
            extra = s["pending"] - len(s["items"])
            if extra > 0 and s["items"]:
                print(f"      … and {extra} more")
            elif extra > 0 and not s.get("note"):
                print(f"      ({extra} pending, no titles available)")
        print()

    total = sum(s["pending"] for s in systems if not s["error"])
    print(f"total pending: {total}")


def main() -> int:
    # Thai text on stdout: Windows still hands a legacy code page to a
    # redirected/piped stream, and every caller of this script pipes it.
    # Without this the whole run dies on UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(
        description="Check pending documents in BUU eDoc and e-Signature. Read-only.")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a report")
    ap.add_argument("--only", choices=["edoc", "esign"], help="check one system only")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"seconds allowed per system (default {DEFAULT_TIMEOUT})")
    args = ap.parse_args()

    load_env()
    systems = asyncio.run(run(args.only or "all", args.timeout))

    failed = [s for s in systems if s["error"]]
    config_broken = [s for s in systems if s.get("config_error")]
    total = sum(s["pending"] for s in systems if not s["error"])
    ok = len(failed) < len(systems)

    if args.json:
        print(json.dumps({
            "ok": ok,
            "total_pending": total,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "systems": systems,
        }, ensure_ascii=False, indent=2))
    else:
        render(systems)

    if len(config_broken) == len(systems):
        return EXIT_CONFIG
    return EXIT_OK if ok else EXIT_ALL_FAILED


if __name__ == "__main__":
    sys.exit(main())
