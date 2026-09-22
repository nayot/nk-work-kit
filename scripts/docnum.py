#!/usr/bin/env python3
"""
ระบบขอเลขเอกสารอัตโนมัติ — คณะวิศวกรรมศาสตร์ มหาวิทยาลัยบูรพา
Command-line driver for the faculty's Google Apps Script document-numbering system.

    docnum.py login                  open a browser to sign in (once per profile)
    docnum.py whoami                 show the signed-in user
    docnum.py list [--json] [--all]  list documents you have requested
    docnum.py request ...            request a NEW number  (irreversible — confirms first)
    docnum.py cancel <docNumber> ... cancel a number you requested (24h window)

HOW THIS WORKS, AND WHY
-----------------------
The web app is an Apps Script deployment whose user interface renders inside a
nested iframe on `script.googleusercontent.com` (path `/blank`). Rather than
click the wizard, we call the app's own server functions directly through
`google.script.run` from inside that frame. Those functions are:

    checkUserAccess()                                  -> {success, user:{name,email}}
    getMyDocuments(email)                              -> {success, documents:[...]}
    requestDocumentNumber(docType, requester,
                          recipient, subject)          -> {success, documentNumber, date, time}
    cancelDocument(docNumber, sheetName, rowIndex,
                   reason, userEmail)                  -> {success, ...}

`requester` is the user's EMAIL, not their name — the form has a separate
requesterName field that the app never sends. The server derives the display
name from the email.

HARD-WON DETAILS — do not "simplify" these away:
  * The UI frame test must be `script.googleusercontent.com` AND path `/blank`.
    The Google sign-in page also has inputs and text, so "a frame with content"
    is not a readiness test and will happily dump the login page instead.
  * Chromium must run HEADED. In headless, Google parks the session on
    accounts.google.com/v3/signin/confirmidentifier forever, even with valid
    cookies. We run headed but position the window offscreen so it does not
    steal focus. `login` is the one command that shows it on screen.
  * GPU is disabled (this machine needs it; symptom is a hung/blank window).
  * The wizard's docType radios are covered by their card <div>, so a normal
    .check() times out — irrelevant now that we bypass the wizard, but that is
    why clicking through the UI is not the approach here.
  * Never name a helper module `inspect.py` — it shadows the stdlib and breaks
    playwright's import chain.
"""
import argparse
import json
import pathlib
import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright is not installed.  pip install --user playwright  "
             "&&  playwright install chromium")

URL = ("https://script.google.com/a/macros/eng.buu.ac.th/s/"
       "AKfycbz-n8KyAVbjLUwLUBBAGAEjbqVb7nrwzqlQtnZzZQ2ERtGdH91aZM0qAvkquNTWc10EKg/exec")
PROFILE = pathlib.Path.home() / ".local/share/buu-docnum/profile"

GPU_OFF = [
    "--disable-gpu", "--disable-gpu-compositing", "--disable-software-rasterizer",
    "--disable-accelerated-2d-canvas", "--disable-dev-shm-usage", "--use-gl=swiftshader",
]
OFFSCREEN = ["--window-position=-3000,0", "--window-size=1280,900"]

DOC_TYPES = {
    "EXTERNAL":     "หนังสือออกภายนอก",
    "INTERNAL":     "หนังสือออกภายใน",
    "ANNOUNCEMENT": "ประกาศ",
    "ORDER":        "คำสั่ง",
}
# convenience aliases so the caller can say "ภายใน" or "internal"
ALIASES = {
    "external": "EXTERNAL", "นอก": "EXTERNAL", "ภายนอก": "EXTERNAL",
    "หนังสือออกภายนอก": "EXTERNAL", "หนังสือภายนอก": "EXTERNAL", "nok": "EXTERNAL",
    "internal": "INTERNAL", "ใน": "INTERNAL", "ภายใน": "INTERNAL",
    "หนังสือออกภายใน": "INTERNAL", "หนังสือภายใน": "INTERNAL",
    "บันทึกข้อความ": "INTERNAL", "nai": "INTERNAL",
    "announcement": "ANNOUNCEMENT", "ประกาศ": "ANNOUNCEMENT",
    "order": "ORDER", "คำสั่ง": "ORDER",
}

# Promise-wrap a google.script.run call so Playwright can await it.
CALL_JS = """
([fn, args]) => new Promise((resolve) => {
  const t = setTimeout(() => resolve({ok: false, error: 'timeout waiting for ' + fn}), 90000);
  try {
    google.script.run
      .withSuccessHandler(r => { clearTimeout(t); resolve({ok: true, data: r}); })
      .withFailureHandler(e => { clearTimeout(t); resolve({ok: false, error: String((e && e.message) || e)}); })
      [fn].apply(null, args);
  } catch (e) {
    clearTimeout(t);
    resolve({ok: false, error: 'client error: ' + String((e && e.message) || e)});
  }
})"""


class SessionExpired(RuntimeError):
    pass


def _ui_frame(page):
    """The Apps Script user-interface frame, or None."""
    for f in page.frames:
        if "script.googleusercontent.com" in f.url and f.url.rstrip("/").endswith("/blank"):
            return f
    return None


class App:
    """Open the web app once; issue any number of server calls against it."""

    def __init__(self, visible=False, timeout=90):
        self.visible = visible
        self.timeout = timeout

    def __enter__(self):
        PROFILE.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        args = [*GPU_OFF] + ([] if self.visible else OFFSCREEN)
        if self.visible:
            args.append("--start-maximized")
        self.ctx = self._pw.chromium.launch_persistent_context(
            str(PROFILE), headless=False, args=args,
            viewport={"width": 1280, "height": 900})
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        try:
            # networkidle matters: the Apps Script shell loads its user iframe late,
            # and domcontentloaded returns long before the UI frame exists.
            self.page.goto(URL, wait_until="networkidle", timeout=self.timeout * 1000)
        except Exception:
            self.page.goto(URL, wait_until="domcontentloaded", timeout=self.timeout * 1000)
        return self

    def __exit__(self, *exc):
        try:
            self.ctx.close()
        finally:
            self._pw.stop()

    def wait_ready(self, seconds=90, allow_signin=False):
        """Wait for the app UI. Raises SessionExpired if parked on a sign-in page.

        `login` passes allow_signin=True: the sign-in page is where that command
        starts, so aborting on it would make signing in impossible.
        """
        deadline = time.time() + seconds
        while time.time() < deadline:
            fr = _ui_frame(self.page)
            if fr:
                try:                       # frame exists but may still be booting
                    if fr.evaluate("typeof google !== 'undefined' && !!(google.script && google.script.run)"):
                        return fr
                except Exception:
                    pass
            if not allow_signin and ("accounts.google.com" in self.page.url
                                     or "/ServiceLogin" in self.page.url):
                raise SessionExpired(
                    "not signed in (Google is showing a sign-in / confirm-identity page)")
            time.sleep(2)
        frames = [f.url[:90] for f in self.page.frames]
        raise SessionExpired(
            f"the app UI did not load in time (url={self.page.url[:90]} frames={frames})")

    def call(self, fn, *args):
        fr = self.wait_ready()
        res = fr.evaluate(CALL_JS, [fn, list(args)])
        if not res.get("ok"):
            raise RuntimeError(f"{fn} failed: {res.get('error')}")
        return res.get("data")


# ── helpers ────────────────────────────────────────────────────────────────

def die_expired(msg):
    print(f"✗ {msg}\n\n  Run:  docnum.py login\n"
          "  A browser window opens; sign in with your @eng.buu.ac.th account.\n"
          "  The session is stored in the profile and reused afterwards.", file=sys.stderr)
    sys.exit(3)


def norm_doctype(v):
    if not v:
        return None
    v = v.strip()
    if v.upper() in DOC_TYPES:
        return v.upper()
    return ALIASES.get(v.lower(), ALIASES.get(v))


def fmt_doc(d):
    flag = "✓" if d.get("status") == "ใช้งาน" else "✗"
    cancel = "  [ยกเลิกได้]" if d.get("canCancel") else ""
    return (f"  {flag} {d.get('docNumber','?'):<16} {d.get('docTypeName',''):<18} "
            f"{d.get('datetime','')}{cancel}\n"
            f"      เรียน : {d.get('recipient','')}\n"
            f"      เรื่อง : {d.get('subject','')}")


# ── commands ───────────────────────────────────────────────────────────────

def cmd_login(a):
    print("Opening the document-number system.\n"
          "Sign in with your @eng.buu.ac.th Google account in the browser window.\n"
          "This window closes by itself once you are through.\n")
    with App(visible=True, timeout=120) as app:
        try:
            app.wait_ready(seconds=a.wait, allow_signin=True)
        except SessionExpired:
            print(f"✗ still not signed in after {a.wait}s — run login again and complete the sign-in.",
                  file=sys.stderr)
            return 3
        who = app.call("checkUserAccess")
        u = (who or {}).get("user", {})
        print(f"✓ signed in as {u.get('name')} <{u.get('email')}>")
        print("  The session is saved; other commands will not prompt again.")
    return 0


def cmd_whoami(a):
    with App() as app:
        try:
            who = app.call("checkUserAccess")
        except SessionExpired as e:
            die_expired(str(e))
    u = (who or {}).get("user", {})
    print(json.dumps(u, ensure_ascii=False) if a.json
          else f"{u.get('name')} <{u.get('email')}>")
    return 0


def cmd_list(a):
    with App() as app:
        try:
            who = app.call("checkUserAccess")
            email = (who or {}).get("user", {}).get("email")
            res = app.call("getMyDocuments", email)
        except SessionExpired as e:
            die_expired(str(e))
    docs = (res or {}).get("documents") or []
    if a.type:
        t = norm_doctype(a.type)
        docs = [d for d in docs if d.get("docType") == t]
    if not a.all:
        docs = [d for d in docs if d.get("status") == "ใช้งาน"]
    if a.limit:
        docs = docs[: a.limit]
    if a.json:
        print(json.dumps(docs, ensure_ascii=False, indent=2))
    else:
        print(f"เอกสารของ {(who or {}).get('user', {}).get('email')} — {len(docs)} รายการ\n")
        for d in docs:
            print(fmt_doc(d))
            print()
    return 0


def cmd_request(a):
    doctype = norm_doctype(a.type)
    if not doctype:
        print(f"✗ unknown document type {a.type!r}. One of: "
              + ", ".join(f"{k} ({v})" for k, v in DOC_TYPES.items()), file=sys.stderr)
        return 2

    with App() as app:
        try:
            who = app.call("checkUserAccess")
        except SessionExpired as e:
            die_expired(str(e))
        email = a.requester or (who or {}).get("user", {}).get("email")

        print("\n  ── ขอเลขเอกสารใหม่ ─────────────────────────────")
        print(f"  ประเภท   : {doctype}  ({DOC_TYPES[doctype]})")
        print(f"  ผู้ขอ     : {email}")
        print(f"  เรียน    : {a.recipient}")
        print(f"  เรื่อง    : {a.subject}")
        print("  ────────────────────────────────────────────────")
        print("  This CONSUMES a real document number and writes a row in the")
        print("  faculty sheet. It can only be cancelled within 24 hours.\n")

        if not a.yes:
            if not sys.stdin.isatty():
                print("✗ refusing to request without confirmation. Re-run with --yes "
                      "once the details above are correct.", file=sys.stderr)
                return 4
            if input("  Proceed? type 'yes' to confirm: ").strip().lower() not in ("y", "yes"):
                print("aborted — no number was requested.")
                return 1

        res = app.call("requestDocumentNumber", doctype, email, a.recipient, a.subject)

    if not (res or {}).get("success"):
        print(f"✗ request failed: {(res or {}).get('error')}", file=sys.stderr)
        return 5
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"\n✓ เลขเอกสาร: {res.get('documentNumber')}")
        print(f"  วันที่ {res.get('date')}  เวลา {res.get('time')}")
        print("  ยกเลิกได้ภายใน 24 ชั่วโมง")
    return 0


def cmd_cancel(a):
    with App() as app:
        try:
            who = app.call("checkUserAccess")
            email = (who or {}).get("user", {}).get("email")
            res = app.call("getMyDocuments", email)
        except SessionExpired as e:
            die_expired(str(e))
        docs = (res or {}).get("documents") or []
        match = [d for d in docs if d.get("docNumber") == a.docnumber]
        if not match:
            print(f"✗ {a.docnumber} is not in your documents.", file=sys.stderr)
            return 2
        doc = match[0]
        if not doc.get("canCancel"):
            print(f"✗ {a.docnumber} can no longer be cancelled "
                  f"(status {doc.get('status')}, requested {doc.get('datetime')}, "
                  f"{doc.get('hoursDiff')}h ago; the window is 24h).", file=sys.stderr)
            return 6

        print(fmt_doc(doc))
        if not a.yes:
            if not sys.stdin.isatty():
                print("✗ refusing to cancel without confirmation; re-run with --yes.", file=sys.stderr)
                return 4
            if input("\n  Cancel this number? type 'yes': ").strip().lower() not in ("y", "yes"):
                print("aborted — nothing cancelled.")
                return 1

        out = app.call("cancelDocument", doc["docNumber"], doc["sheetName"],
                       doc["rowIndex"], a.reason, email)
    if not (out or {}).get("success"):
        print(f"✗ cancel failed: {(out or {}).get('error')}", file=sys.stderr)
        return 5
    print(f"✓ {a.docnumber} ถูกยกเลิกแล้ว")
    return 0


def main():
    p = argparse.ArgumentParser(
        description="ระบบขอเลขเอกสารอัตโนมัติ — คณะวิศวกรรมศาสตร์ ม.บูรพา",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("login", help="open a browser and sign in (once per profile)")
    s.add_argument("--wait", type=int, default=600, help="seconds to wait for sign-in (default 600)")
    s.set_defaults(func=cmd_login)

    s = sub.add_parser("whoami", help="show the signed-in user")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_whoami)

    s = sub.add_parser("list", help="list documents you have requested")
    s.add_argument("--json", action="store_true")
    s.add_argument("--all", action="store_true", help="include cancelled documents")
    s.add_argument("--type", help="filter: INTERNAL/EXTERNAL/ANNOUNCEMENT/ORDER or Thai alias")
    s.add_argument("--limit", type=int)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("request", help="request a NEW document number (irreversible)")
    s.add_argument("--type", required=True,
                   help="INTERNAL | EXTERNAL | ANNOUNCEMENT | ORDER (Thai aliases accepted)")
    s.add_argument("--recipient", required=True, help="เรียน — who the document is addressed to")
    s.add_argument("--subject", required=True, help="เรื่อง — the subject line")
    s.add_argument("--requester", help="requester email (default: the signed-in user)")
    s.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_request)

    s = sub.add_parser("cancel", help="cancel a number you requested (24h window)")
    s.add_argument("docnumber", help="e.g. อว8116/XXXX")
    s.add_argument("--reason", default="", help="เหตุผลการยกเลิก")
    s.add_argument("--yes", action="store_true")
    s.set_defaults(func=cmd_cancel)

    a = p.parse_args()
    try:
        return a.func(a)
    except SessionExpired as e:
        die_expired(str(e))
    except KeyboardInterrupt:
        print("\naborted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
