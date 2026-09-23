#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "playwright==1.60.0",
#   "pypdf>=5.0",
# ]
# ///
"""
edoc_digest.py — fetch eDoc documents, save their content, and optionally ลงรับ.

    uv run edoc_digest.py                        fetch unread docs (no ลงรับ)
    uv run edoc_digest.py --receive              ... and ลงรับ each one once saved
    uv run edoc_digest.py --all --receive        every row still in ค้างรับ, not only unread
    uv run edoc_digest.py --inbox "NAME" --limit 3 --json

For each document it opens the detail page, saves the detail text, downloads
every attachment, extracts the text layer of each PDF with pypdf, and — only
with --receive, and only once all of that is safely on disk — clicks รับเอกสาร
(ลงรับ). It never signs (ลงนาม), forwards, replies or cancels anything.

Opening a document marks it read in eDoc. That is inherent to the task; it is
why the ค้างรับ list, not the unread flag, is the source of truth for what is
still unreceived (see --all).

WHAT IT WRITES — <data dir>/<YYYY-MM-DD>/
----------------------------------------
    manifest.json            every document fetched that day, keyed by data_id
                             (a later run the same day updates its entries)
    <data_id>/detail.txt     the detail page's text (header fields, สั่งการ, route)
    <data_id>/NN_<name>      each attachment, as downloaded
    <data_id>/NN_<name>.txt  pypdf text layer of a PDF attachment; the manifest's
                             text_quality says ok / garbled (broken Thai font
                             map) / empty (scan)

<data dir> is ~/.local/share/nk-work-kit/edoc ($XDG_DATA_HOME honoured) on
Linux/macOS and %LOCALAPPDATA%\\nk-work-kit\\edoc on Windows. It sits outside
the version-pinned plugin directory, so upgrades do not delete downloads.

CONFIG — ~/.config/nk-work-kit/.env (see scripts/.env.example)
--------------------------------------------------------------
    EDOC_USERNAME, EDOC_PASSWORD   BUU login (shared with pending-docs)
    EDOC_DIGEST_INBOX              comma-separated inbox names to process. No
                                   "all inboxes" default: this script can write
                                   (ลงรับ), so the inbox must be chosen.

HARD-WON DETAILS — do not "simplify" these away:
  * ลงรับ only works from home.aspx. #btnReceive in the detail frame calls
    ShowDialog_Receive on parent.parent (the home page), so a standalone
    inboxdetail.aspx has no dialog to open. Docs are opened by clicking their
    row in the `home_list` frame; the detail loads into `iframeContent0`.
  * The receive dialog's "ออกเลขจาก" (#cmbDocumentReceiveRunNo) offers N
    (ไม่ออกเลข), P (ใช้หมายเลขเดิม) and, on some inboxes, a run-number book. A
    book issues a NEW เลขรับ from the registry sequence, so the script refuses
    to receive when anything other than N/P is preselected. A fresh browser has
    no remembered choice, so the preselection is the server default.
  * Success is read from VN.V2.App.Home.Page.DocumentReceive.Response
    .isReceiveSuccess, which the dialog's AJAX callback sets; errors surface as
    alert() dialogs, which are captured and dismissed.
  * Each attachment is listed twice (ItmId=0 and a per-route copy). Dedupe by
    AttId and keep ItmId=0. Download links carry a per-render token, so they
    are fetched while the doc is open and never written to the manifest as
    links; `edoc_url` (inboxdetail.aspx?id=) is the stable link, and it needs
    a signed-in browser session.
  * The download's Content-Disposition filename is UTF-8 mis-decoded as
    latin-1; the name is taken from the attachment link text instead.
  * Never wait for "networkidle" after HideContentFrame(): the keepalive
    stream never settles. A short sleep is enough.
  * A realistic desktop UA and viewport are required; the portal serves a
    broken page to bare headless Chromium.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    sys.exit("playwright is not installed. Run this script with `uv run`, "
             "which installs it automatically.")

EDOC_URL = "https://doc.buu.ac.th/docweb/v2/"
DETAIL_URL = "https://doc.buu.ac.th/docweb/v2/inboxdetail.aspx?id={id}"
EDOC_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
SAFE_RUNNO = {"N", "P"}  # ไม่ออกเลข / ใช้หมายเลขเดิม — never a new number
URGENCY = {"ปกติ", "ด่วน", "ด่วนมาก", "ด่วนที่สุด"}

EXIT_OK = 0
EXIT_FAILED = 1      # login/navigation failed, or at least one document failed
EXIT_CONFIG = 3
ALL_RECEIVE_CAP = 30  # --all --receive above this needs an explicit --limit

# Rows in the home_list frame. Urgency is matched by value; number, date and
# sender are the cells around the subject, as in check_pending.py.
LIST_JS = """(onlyUnread) => {
  const sel = onlyUnread ? 'a.home-list-open-item.unread' : 'a.home-list-open-item';
  return [...document.querySelectorAll(sel)].map(a => {
    const tr = a.closest('tr');
    const subject = (a.innerText || '').trim();
    const row = {data_id: a.dataset.id, subject, unread: a.classList.contains('unread'),
                 urgency: '', number: '', date_in: '', sender: ''};
    if (!tr) return row;
    const cells = [...tr.querySelectorAll('td')];
    const texts = cells.map(td => (td.innerText || '').trim());
    row.urgency = texts.find(t => %s.includes(t)) || '';
    const j = cells.findIndex(td => td.contains(a));
    if (j > -1) {
      const nonEmptyBefore = texts.slice(0, j).filter(Boolean);
      row.number = nonEmptyBefore.length ? nonEmptyBefore[nonEmptyBefore.length - 1] : '';
      const dateCell = cells[j + 1];
      const span = dateCell && dateCell.querySelector('span[title]');
      row.date_in = span ? span.title : (texts[j + 1] || '');
      row.sender = texts[j + 2] || '';
    }
    if (row.number === row.urgency) row.number = '';
    return row;
  });
}""" % json.dumps(sorted(URGENCY), ensure_ascii=False)

# Attachments in the detail frame, deduped by AttId, original copy (ItmId=0) first.
ATTACH_JS = """() => {
  const seen = new Map();
  for (const a of document.querySelectorAll('a[href*="AttachmentView.aspx"][href*="Download=1"]')) {
    const u = new URL(a.href, location.href);
    const att = u.searchParams.get('AttId'), itm = u.searchParams.get('ItmId') || '0';
    if (!att) continue;
    const row = a.closest('tr') || a.parentElement;
    const named = row ? [...row.querySelectorAll('a[href*="Download=0"]')]
                          .map(x => (x.innerText || '').trim()).filter(Boolean) : [];
    const prev = seen.get(att);
    if (!prev || (prev.itm !== '0' && itm === '0'))
      seen.set(att, {att_id: att, itm, href: a.href, name: named[0] || ''});
  }
  return [...seen.values()];
}"""

# Header fields on the detail page, as "label : value" lines.
FIELDS = {
    "from": "จาก", "sent_at": "วันที่ส่ง", "action": "ลงนาม/สั่งการ",
    "doc_number": "ที่", "secrecy": "ระดับชั้นความลับ", "speed": "ระดับชั้นความเร็ว",
    "doc_type": "ประเภทเอกสาร", "doc_date": "วันที่เอกสาร", "to": "เรียน",
    "subject": "เรื่อง", "due": "ควรดำเนินการหนังสือแล้วเสร็จภายใน",
}


# ── config ────────────────────────────────────────────────────────────────────

def config_files() -> list[Path]:
    """Where plugin config may live, most specific first (same as check_pending.py)."""
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


def data_root() -> Path:
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "nk-work-kit" / "edoc"
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "nk-work-kit" / "edoc"


# ── helpers ───────────────────────────────────────────────────────────────────

def safe_name(name: str, fallback: str) -> str:
    """A filename that is valid on Windows too; keeps Thai."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(".")
    return (name or fallback)[:120]


def parse_fields(text: str) -> dict:
    """Header fields are rendered as "label :<TAB>value". The title bar above
    them uses "เรื่อง: ... ส่งมาจาก: ..." with no space, which must not match."""
    out = {}
    by_label = {thai: key for key, thai in FIELDS.items()}
    for line in text.splitlines():
        m = re.match(r"^\s*(.+?) :\t(.*)$", line)
        if m and (key := by_label.get(m.group(1).strip())) and key not in out:
            if value := m.group(2).strip():
                out[key] = value
    return out


def pdf_text(path: Path) -> tuple[str, int | None]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n\n".join((p.extract_text() or "") for p in reader.pages).strip(), len(reader.pages)
    except Exception:  # corrupt / encrypted / not really a PDF
        return "", None


def text_quality(text: str, pages: int | None) -> str:
    """ok | garbled | empty. Thai PDFs with broken font maps extract as Latin-
    extended mojibake (ïĆîìċÖ×šĂÙüćö) — long, so a length test alone misses it."""
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 80 * max(pages or 1, 1) / 2:
        return "empty"          # scan, or next to no text layer
    thai = sum("\u0e00" <= c <= "\u0e7f" for c in letters)
    latin_ext = sum("\u00c0" <= c <= "\u024f" for c in letters)
    return "garbled" if latin_ext > thai else "ok"


def match_inboxes(boxes: list[dict], wanted: list[str]) -> list[dict]:
    """Whitespace-insensitive name match, as in check_pending.py. Errors, never guesses."""
    def key(s: str) -> str:
        return "".join(s.split())
    chosen = []
    for want in wanted:
        hits = [b for b in boxes if b["name"] == want] or \
               [b for b in boxes if key(b["name"]) == key(want)]
        if not hits:
            raise LookupError(f"inbox {want!r} not found — available: "
                              + " | ".join(b["name"] for b in boxes))
        if len(hits) > 1:
            raise LookupError(f"inbox {want!r} is ambiguous: "
                              + " | ".join(h["name"] for h in hits))
        if hits[0] not in chosen:
            chosen.append(hits[0])
    return chosen


# ── browser steps ─────────────────────────────────────────────────────────────

async def login(page, username: str, password: str) -> None:
    await page.goto(EDOC_URL, wait_until="domcontentloaded")
    await page.wait_for_selector("#txtLogin", state="visible", timeout=20000)
    await page.fill("#txtLogin", username)
    await page.fill("#txtPassword", password)
    async with page.expect_navigation(wait_until="networkidle"):
        await page.click("#btnLogin")
    if "home.aspx" not in page.url:
        raise PermissionError("login did not reach home.aspx — check EDOC_USERNAME / "
                              f"EDOC_PASSWORD (landed on {page.url})")


def list_frame(page):
    return next((f for f in page.frames if f.name == "home_list"), None)


async def open_shortcuts(page) -> list[dict]:
    """Show the ทางลัด tab on a fresh home.aspx and return the inboxes on it."""
    await page.goto(EDOC_URL + "home.aspx", wait_until="domcontentloaded")
    inner = page.frame_locator("#iframeHomeBody").frame_locator("#home_list_full")
    await inner.locator(".home-content-tab-shortcuts").click()
    # The links load in stages: a fixed sleep has read none, or only the first
    # of five. Poll until the list is non-empty and unchanged for ~1.5 s. Skip
    # nameless links (some are hidden placeholders).
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 20
    boxes, stable = [], 0
    while loop.time() < deadline:
        frame = list_frame(page)
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
            return boxes
        await asyncio.sleep(0.5)
    if boxes:
        return boxes
    raise RuntimeError("no inboxes appeared on the ทางลัด tab")


async def open_inbox(page, box: dict) -> None:
    inner = page.frame_locator("#iframeHomeBody").frame_locator("#home_list_full")
    await inner.locator(
        f'a.home-shortcuts-open-by-listsource[data-entity-id="{box["eid"]}"]').click()
    # The list reloads into home_list; wait until it shows this inbox's EntityId.
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 20
    while loop.time() < deadline:
        f = list_frame(page)
        if f and f"EntityId={box['eid']}" in f.url:
            try:
                await f.wait_for_load_state("domcontentloaded")
                break
            except Exception:
                pass
        await asyncio.sleep(0.4)
    else:
        raise TimeoutError(f"inbox {box['name']!r} did not open")
    await page.wait_for_timeout(1500)


async def detail_frame(page, data_id: str, timeout: float = 20.0):
    """iframeContent0 once it has loaded this document's InboxDetail page."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        f = page.frame(name="iframeContent0")
        if f is not None and f"id={data_id}" in f.url:
            try:
                rid = await f.evaluate(
                    "() => (window.VN && VN.V2.App.InboxDetail && VN.V2.App.InboxDetail.Page) "
                    "? String(VN.V2.App.InboxDetail.Page.routeId) : null")
                if rid == str(data_id):
                    return f
            except Exception:
                pass  # frame mid-navigation
        await asyncio.sleep(0.4)
    raise TimeoutError(f"detail page for {data_id} did not load")


async def receive(page, frame, alerts: list[str]) -> tuple[bool, str]:
    """ลงรับ the open document. Returns (received, note)."""
    if await frame.evaluate("() => VN.V2.App.InboxDetail.Page.routeReceived"):
        return True, "already received"

    await frame.click("#btnReceive")
    await page.wait_for_selector("#divDialogDocumentReceive", state="visible", timeout=15000)
    await page.wait_for_function(
        "() => document.querySelectorAll('#cmbDocumentReceiveRunNo option').length > 0",
        timeout=15000)
    await page.wait_for_timeout(500)
    chosen = await page.evaluate(
        """() => { const o = document.querySelector('#cmbDocumentReceiveRunNo option:checked');
                   return o ? {value: o.value, text: o.text} : null; }""")
    if not chosen or chosen["value"] not in SAFE_RUNNO:
        await page.click("#btnDocumentReceiveCancel")
        return False, ("refused: ออกเลขจาก preselects "
                       f"{chosen['text'] if chosen else 'nothing'!r}, which would issue a "
                       "new เลขรับ — receive this one by hand")

    await page.evaluate("""() => { const r = VN.V2.App.Home.Page.DocumentReceive.Response;
                                   if (r) { r.isReceiveSuccess = undefined; r.isReceiveMoveout = undefined; } }""")
    n_alerts = len(alerts)
    await page.click("#btnDocumentReceiveOK")
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 20
    while loop.time() < deadline:
        ok = await page.evaluate(
            "() => { const r = VN.V2.App.Home.Page.DocumentReceive.Response; return r ? r.isReceiveSuccess : undefined; }")
        if ok is True:
            return True, f"received ({chosen['text']})" + await confirm_received(page)
        if ok is False:
            return False, "eDoc reported the receive as unsuccessful"
        if len(alerts) > n_alerts:
            return False, "eDoc error: " + " / ".join(alerts[n_alerts:])
        await asyncio.sleep(0.4)
    return False, "no confirmation from eDoc within 20s — check the document by hand"


async def confirm_received(page, timeout: float = 10.0) -> str:
    """After a successful receive the detail frame reloads; read routeReceived back."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        f = page.frame(name="iframeContent0")
        try:
            if f and await f.evaluate("() => VN.V2.App.InboxDetail.Page.routeReceived === true"):
                return ""
        except Exception:
            pass  # frame mid-reload
        await asyncio.sleep(0.5)
    return " — eDoc said success, but the reloaded page did not confirm it"


async def process_document(page, ctx, row: dict, inbox: str, out_dir: Path,
                           do_receive: bool, alerts: list[str]) -> dict:
    doc = dict(row, inbox=inbox, edoc_url=DETAIL_URL.format(id=row["data_id"]),
               attachments=[], received=None, receive_note="", error=None)
    doc_dir = out_dir / row["data_id"]
    doc_dir.mkdir(parents=True, exist_ok=True)
    try:
        frame = list_frame(page)
        await frame.click(f"a[data-id='{row['data_id']}']", force=True)
        detail = await detail_frame(page, row["data_id"])
        await detail.wait_for_timeout(800)

        text = await detail.evaluate(
            "() => (document.querySelector('#divDocumentContent, .inbox-detail-body') || document.body).innerText")
        (doc_dir / "detail.txt").write_text(text, encoding="utf-8")
        doc["detail_text_path"] = str(doc_dir / "detail.txt")
        doc["fields"] = parse_fields(text)
        doc["notes"] = [t.strip() for t in
                        await detail.locator(".DocNoteContent").all_inner_texts() if t.strip()]

        failed = []
        for i, att in enumerate(await detail.evaluate(ATTACH_JS), 1):
            name = safe_name(att["name"], f"attachment_{att['att_id']}")
            path = doc_dir / f"{i:02d}_{name}"
            entry = {"name": att["name"] or name, "path": str(path), "file_uri": path.as_uri()}
            resp = await ctx.request.get(att["href"])
            body = await resp.body() if resp.ok else b""
            is_pdf = body[:5] == b"%PDF-"
            if not resp.ok or not body or (name.lower().endswith(".pdf") and not is_pdf):
                entry["error"] = f"download failed (HTTP {resp.status}, {len(body)} bytes)"
                failed.append(entry["name"])
            else:
                path.write_bytes(body)
                entry.update(bytes=len(body), is_pdf=is_pdf)
                if is_pdf:
                    txt, pages = pdf_text(path)
                    txt_path = path.with_name(path.name + ".txt")
                    txt_path.write_text(txt, encoding="utf-8")
                    entry.update(pages=pages, text_path=str(txt_path), text_chars=len(txt),
                                 text_quality=text_quality(txt, pages))
            doc["attachments"].append(entry)

        if not do_receive:
            doc["receive_note"] = "not requested (run with --receive)"
        elif failed:
            doc["received"] = False
            doc["receive_note"] = "skipped: attachment download failed — " + ", ".join(failed)
        else:
            doc["received"], doc["receive_note"] = await receive(page, detail, alerts)
            if doc["received"] is False:
                await page.screenshot(path=str(doc_dir / "receive_error.png"))
    except Exception as e:
        doc["error"] = f"{type(e).__name__}: {e}"
        try:
            await page.screenshot(path=str(doc_dir / "error.png"))
        except Exception:
            pass
    finally:
        try:
            await page.evaluate("VN.V2.App.Home.Page.HideContentFrame()")
        except Exception:
            pass
        await asyncio.sleep(0.8)
    return doc


async def run(args, username: str, password: str, wanted: list[str], out_dir: Path) -> dict:
    alerts: list[str] = []

    async def on_dialog(d):
        alerts.append(d.message)
        await d.dismiss()

    docs, inboxes = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900},
                                            user_agent=EDOC_UA)
            page = await ctx.new_page()
            page.on("dialog", on_dialog)
            await login(page, username, password)
            boxes = match_inboxes(await open_shortcuts(page), wanted)
            for n, box in enumerate(boxes):
                if n:
                    await open_shortcuts(page)  # the tab bar is gone once an inbox is open
                await open_inbox(page, box)
                frame = list_frame(page)
                rows = await frame.evaluate(LIST_JS, not args.all)
                inboxes.append({"name": box["name"], "entity_id": box["eid"], "selected": len(rows)})
                if args.limit:
                    rows = rows[:args.limit]
                elif args.all and args.receive and len(rows) > ALL_RECEIVE_CAP:
                    # A shared inbox's ค้างรับ list can be a 500-row backlog; one
                    # flag must not be enough to receive all of it.
                    raise LookupError(
                        f"{box['name']}: --all --receive would ลงรับ {len(rows)} documents; "
                        f"pass --limit N to confirm how many (cap without it: {ALL_RECEIVE_CAP})")
                for i, row in enumerate(rows, 1):
                    print(f"[{box['name']}] {i}/{len(rows)} {row['subject'][:70]}", file=sys.stderr)
                    docs.append(await process_document(page, ctx, row, box["name"], out_dir,
                                                       args.receive, alerts))
        finally:
            await browser.close()
    return {"inboxes": inboxes, "documents": docs}


def write_manifest(out_dir: Path, result: dict) -> Path:
    path = out_dir / "manifest.json"
    existing = {}
    if path.is_file():
        try:
            existing = {d["data_id"]: d for d in json.loads(path.read_text(encoding="utf-8"))["documents"]}
        except (ValueError, KeyError):
            pass
    for d in result["documents"]:
        existing[d["data_id"]] = d
    manifest = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "out_dir": str(out_dir),
        "documents": list(existing.values()),
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def render(result: dict) -> None:
    for box in result["inboxes"]:
        print(f"{box['name']}: {box['selected']} selected")
    for d in result["documents"]:
        mark = "!" if d["error"] else ("✓" if d["received"] else "·")
        print(f"  {mark} {d['data_id']}  {d.get('urgency') or '-'}  {d['subject'][:80]}")
        print(f"      {len(d['attachments'])} attachment(s); {d['error'] or d['receive_note']}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="Fetch eDoc documents and their attachments; "
                                             "optionally ลงรับ. Never signs.")
    ap.add_argument("--inbox", action="append", help="inbox name (repeatable); "
                    "default: EDOC_DIGEST_INBOX")
    ap.add_argument("--receive", action="store_true",
                    help="ลงรับ each document after its content is saved")
    ap.add_argument("--all", action="store_true",
                    help="every row in the ค้างรับ list, not only unread ones")
    ap.add_argument("--limit", type=int, help="at most N documents per inbox")
    ap.add_argument("--out", type=Path, help="output dir (default: <data dir>/<YYYY-MM-DD>)")
    ap.add_argument("--json", action="store_true", help="print this run's result as JSON")
    ap.add_argument("--timeout", type=int, default=1200, help="seconds for the whole run")
    args = ap.parse_args()

    load_env()
    username = os.environ.get("EDOC_USERNAME", "")
    password = os.environ.get("EDOC_PASSWORD", "")
    wanted = args.inbox or [n.strip() for n in
                            os.environ.get("EDOC_DIGEST_INBOX", "").split(",") if n.strip()]
    if not username or not password:
        print("error: EDOC_USERNAME / EDOC_PASSWORD not set in ~/.config/nk-work-kit/.env",
              file=sys.stderr)
        return EXIT_CONFIG
    if not wanted:
        print("error: no inbox chosen — set EDOC_DIGEST_INBOX or pass --inbox", file=sys.stderr)
        return EXIT_CONFIG

    out_dir = args.out or data_root() / datetime.now().strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = asyncio.run(asyncio.wait_for(run(args, username, password, wanted, out_dir),
                                              args.timeout))
    except LookupError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_CONFIG
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return EXIT_FAILED

    manifest = write_manifest(out_dir, result)
    result.update(ok=not any(d["error"] for d in result["documents"]),
                  out_dir=str(out_dir), manifest=str(manifest),
                  receive_requested=args.receive,
                  fetched_at=datetime.now().isoformat(timespec="seconds"))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        render(result)
        print(f"\nmanifest: {manifest}")
    return EXIT_OK if result["ok"] else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
