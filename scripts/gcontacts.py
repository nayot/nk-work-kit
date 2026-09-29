#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["google-auth", "requests"]
# ///
"""Search and edit Google Contacts via the People API, using gcloud Application Default Credentials.

Part of nk-work-kit (business-card skill): the Google Contacts connector is search-only,
so contact edits go through this script. Run it as `uv run scripts/gcontacts.py ...`;
on Nayot's machine `~/.local/bin/gcontacts` is a symlink to the clone's copy.
Auth is gcloud ADC with the contacts scope; nothing is stored by this script.

Usage:
  gcontacts search <query>
  gcontacts create <contact.json | -> [--force]
  gcontacts update <resourceName> [--add-email EMAIL] [--given NAME] [--family NAME]
                                  [--org COMPANY] [--title TITLE] [--add-phone PHONE] [--note TEXT]

Examples:
  gcontacts search "Alan Foamtec"
  gcontacts update people/c123 --add-email a@b.com --org "Foamtec" --title "VP"
  gcontacts create card.json

create takes the business-card JSON used by nk-work-kit's make_vcf.py:
  given_name, family_name, prefix, alt_name (e.g. Thai name, stored as a nickname),
  org, department, title, phones [{number, type}], emails [{address, type}],
  urls [..], address {street, city, region, postcode, country}, note.
It refuses when a contact with one of the emails already exists (use update),
unless --force.
"""
import argparse
import json
import sys

import google.auth
from google.auth.transport.requests import AuthorizedSession

API = "https://people.googleapis.com/v1"
MASK = "names,emailAddresses,organizations,phoneNumbers,biographies"


def session():
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/contacts"])
    return AuthorizedSession(creds)


def summary(p):
    return {
        "resourceName": p["resourceName"],
        "name": next((n.get("displayName") for n in p.get("names", [])), None),
        "emails": [e["value"] for e in p.get("emailAddresses", [])],
        "phones": [ph["value"] for ph in p.get("phoneNumbers", [])],
        "orgs": [{"name": o.get("name"), "title": o.get("title")} for o in p.get("organizations", [])],
        "note": next((b.get("value") for b in p.get("biographies", [])), None),
    }


def search(s, query):
    s.get(f"{API}/people:searchContacts", params={"query": "", "readMask": "names"})  # warm-up cache
    r = s.get(f"{API}/people:searchContacts", params={"query": query, "readMask": MASK})
    r.raise_for_status()
    return [summary(x["person"]) for x in r.json().get("results", [])]


def update(s, a):
    r = s.get(f"{API}/{a.resource}", params={"personFields": MASK})
    r.raise_for_status()
    p = r.json()
    fields = set()
    if a.given or a.family:
        n = (p.get("names") or [{}])[0]
        p["names"] = [{"givenName": a.given or n.get("givenName", ""),
                       "familyName": a.family if a.family is not None else n.get("familyName", "")}]
        fields.add("names")
    if a.add_email:
        emails = p.get("emailAddresses", [])
        if not any(e["value"].lower() == a.add_email.lower() for e in emails):
            emails.append({"value": a.add_email, "type": "work"})
        p["emailAddresses"] = emails
        fields.add("emailAddresses")
    if a.add_phone:
        phones = p.get("phoneNumbers", [])
        phones.append({"value": a.add_phone, "type": "mobile"})
        p["phoneNumbers"] = phones
        fields.add("phoneNumbers")
    if a.org or a.title:
        o = (p.get("organizations") or [{}])[0]
        p["organizations"] = [{"name": a.org or o.get("name", ""), "title": a.title or o.get("title", "")}]
        fields.add("organizations")
    if a.note:
        p["biographies"] = [{"value": a.note, "contentType": "TEXT_PLAIN"}]
        fields.add("biographies")
    if not fields:
        sys.exit("Nothing to update.")
    r = s.patch(f"{API}/{a.resource}:updateContact",
                params={"updatePersonFields": ",".join(sorted(fields)), "personFields": MASK}, json=p)
    r.raise_for_status()
    return summary(r.json())


PHONE_TYPES = {"mobile": "mobile", "cell": "mobile", "work": "work", "fax": "workFax", "home": "home"}


def person_from_card(c):
    p = {}
    name = {k: v for k, v in (("givenName", c.get("given_name")), ("familyName", c.get("family_name")),
                              ("honorificPrefix", c.get("prefix"))) if v}
    if name:
        p["names"] = [name]
    if c.get("alt_name"):
        p["nicknames"] = [{"value": c["alt_name"]}]
    org = {k: v for k, v in (("name", c.get("org")), ("department", c.get("department")),
                             ("title", c.get("title"))) if v}
    if org:
        p["organizations"] = [org]
    if c.get("phones"):
        p["phoneNumbers"] = [{"value": ph["number"],
                              "type": PHONE_TYPES.get(str(ph.get("type", "work")).lower(), "other")}
                             for ph in c["phones"]]
    if c.get("emails"):
        p["emailAddresses"] = [{"value": e["address"], "type": str(e.get("type", "work")).lower()}
                               for e in c["emails"]]
    if c.get("urls"):
        p["urls"] = [{"value": u} for u in c["urls"]]
    a = c.get("address")
    if a:
        adr = {k: a[src] for k, src in (("streetAddress", "street"), ("city", "city"), ("region", "region"),
                                        ("postalCode", "postcode"), ("country", "country")) if a.get(src)}
        if adr:
            p["addresses"] = [dict(adr, type="work")]
    if c.get("note"):
        p["biographies"] = [{"value": c["note"], "contentType": "TEXT_PLAIN"}]
    if "names" not in p and "nicknames" not in p:
        sys.exit("create: the card has no name (given_name/family_name/alt_name).")
    return p


def all_contacts(s):
    out, token = [], None
    while True:
        params = {"personFields": MASK, "pageSize": 1000}
        if token:
            params["pageToken"] = token
        r = s.get(f"{API}/people/me/connections", params=params)
        r.raise_for_status()
        j = r.json()
        out += [summary(x) for x in j.get("connections", [])]
        token = j.get("nextPageToken")
        if not token:
            return out


def create(s, a):
    with (sys.stdin if a.file == "-" else open(a.file, encoding="utf-8")) as f:
        card = json.load(f)
    p = person_from_card(card)
    wanted = {e["value"].lower() for e in p.get("emailAddresses", [])}
    if wanted and not a.force:
        # Walk the whole contact list: searchContacts lags behind recent creates.
        hits = [h for h in all_contacts(s) if wanted & {x.lower() for x in h["emails"]}]
        if hits:
            print(json.dumps({"exists": hits}, ensure_ascii=False, indent=2), flush=True)
            sys.exit(f"create: {', '.join(sorted(wanted))} already on {hits[0]['resourceName']}; "
                     "use update (or --force for a separate contact).")
    r = s.post(f"{API}/people:createContact", params={"personFields": MASK + ",addresses,urls,nicknames"},
               json=p)
    r.raise_for_status()
    return summary(r.json())


def main():
    # Thai names on stdout: Windows hands a legacy code page to a piped stream.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("search")
    sp.add_argument("query")
    cp = sub.add_parser("create")
    cp.add_argument("file", help="business-card JSON file, or - for stdin")
    cp.add_argument("--force", action="store_true", help="create even if the email is already on a contact")
    up = sub.add_parser("update")
    up.add_argument("resource")
    up.add_argument("--add-email")
    up.add_argument("--add-phone")
    up.add_argument("--given")
    up.add_argument("--family")
    up.add_argument("--org")
    up.add_argument("--title")
    up.add_argument("--note")
    a = ap.parse_args()
    s = session()
    out = {"search": lambda: search(s, a.query), "create": lambda: create(s, a),
           "update": lambda: update(s, a)}[a.cmd]()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
