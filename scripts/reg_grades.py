#!/usr/bin/env python3
"""Prepare marks for entry in reg.buu.ac.th (บันทึกคะแนน), stdlib only.

The reg-grades skill drives the reg.buu.ac.th pages in the user's own browser
(Claude in Chrome); this script only turns a CSV of marks into what that
needs, and never touches the site.

    python3 reg_grades.py paste  marks.csv --item final [--group 1]
        -> per-group "studentID<TAB>score" lines for the Import File box
    python3 reg_grades.py fill   marks.csv --items att,hw,final --group 1 --item final --point 7
        -> JavaScript for the open EDIT Point:N page: fill + verify + Save
    python3 reg_grades.py readback marks.csv --items att,hw,final --group 1
        -> JavaScript that reads the saved columns back and compares them

marks.csv columns: student_id, group, then one column per score item (any
names; pass them with --items in the order they appear in reg). An empty cell
means "no mark" (absent, make-up, withdrawn): it is never entered and must
read back blank.

HARD-WON DETAILS (reg.buu.ac.th, verified Nov 2026):
- Score page (enrollpoint.asp): one row per student, cells[1] = 8-digit ID,
  point columns are cells[6 .. 6+nPoints-1], the row total follows. Clicking
  "EDIT Point:N" reloads with EDITCLASSPOINTID=N and turns that column into
  <input type=number step=any min=0 max=item total>, with a single "Save"
  submit button in the column header.
- Withdrawn (W) students are listed but get no input box.
- After Save the cell shows the number as the site formats it (0.93 -> ".93"),
  so compare numerically.
- reg recomputes T-score grades on every save; they are provisional until the
  item weights add up to 100 %.
"""
import argparse
import csv
import json
import sys

FILL_JS = r'''const E=__E__;const PID="__P__";const G="__G__";
const grp=(document.body.innerText.match(/กลุ่ม\s*(\d+)/)||[])[1];
const pid=(location.search.match(/EDITCLASSPOINTID=(\d+)/)||[])[1];
const inp=[...document.querySelectorAll('input[type=number]')];const got={};
inp.forEach(i=>{const id=i.closest('tr').cells[1].innerText.trim();
  if(id in E && grp===G && pid===PID){i.value=E[id];i.dispatchEvent(new Event('change',{bubbles:true}));}
  got[id]=i.value;});
const bad=Object.keys({...E,...got}).filter(k=>!(got[k]===''&&!(k in E))&&parseFloat(got[k])!==E[k]).map(k=>[k,got[k],E[k]]);
const missing=Object.keys(E).filter(k=>!(k in got));const invalid=inp.filter(i=>!i.checkValidity()).length;
let saved=false;
if(__SAVE__&&grp===G&&pid===PID&&!bad.length&&!missing.length&&!invalid){
  const b=[...document.querySelectorAll('input[type=submit],button')].filter(b=>(b.value||b.innerText).trim()==='Save');
  if(b.length===1){b[0].click();saved=true;}}
JSON.stringify({grp,pid,inputs:inp.length,bad,missing,invalid,saved})'''

READBACK_JS = r'''const E=__E__;
const np=new Set([...document.querySelectorAll('a')].map(a=>(a.href.match(/EDITCLASSPOINTID=(\d+)/)||[])[1]).filter(Boolean)).size;
const rows=[...document.querySelectorAll('tr')].filter(tr=>tr.cells.length>12&&/^\d{8}$/.test(tr.cells[1].innerText.trim()));
const K=__K__;const bad=[];const seen=new Set();
for(const tr of rows){const id=tr.cells[1].innerText.trim();seen.add(id);const t=6+np;
  const got=Array.from({length:K},(_,j)=>tr.cells[t-K+j].innerText.trim());const e=E[id];
  if(!e){if(got.some(x=>x!==''))bad.push([id,got,'not expected']);continue;}
  for(let j=0;j<K;j++){const x=got[j],y=e[j];if(y===''?x!=='':parseFloat(x)!==y)bad.push([id,j,x,y]);}}
JSON.stringify({group:(document.body.innerText.match(/กลุ่ม\s*(\d+)/)||[])[1],points:np,rows:rows.length,
  extra:[...seen].filter(k=>!(k in E)),missing:Object.keys(E).filter(k=>!seen.has(k)),bad})'''


def num(s):
    s = (s or "").strip()
    if s == "":
        return ""
    v = float(s)
    return int(v) if v == int(v) else v


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows or "student_id" not in rows[0] or "group" not in rows[0]:
        sys.exit("marks.csv needs columns student_id, group and one per score item")
    ids = [r["student_id"].strip() for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        sys.exit(f"duplicate student_id: {sorted(dup)}")
    return rows


def group_rows(rows, group):
    return [r for r in rows if str(r["group"]).strip().lstrip("0") == str(group).lstrip("0")]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["paste", "fill", "readback"])
    ap.add_argument("csv")
    ap.add_argument("--group", help="section/group number as shown on the reg page (กลุ่ม)")
    ap.add_argument("--item", help="column to enter (paste, fill)")
    ap.add_argument("--items", help="all of this lecturer's item columns, in reg order (readback)")
    ap.add_argument("--point", help="EDIT Point number of --item on this group's page (fill)")
    ap.add_argument("--no-save", action="store_true", help="fill and verify only, don't click Save")
    a = ap.parse_args()
    rows = load(a.csv)
    groups = [a.group] if a.group else sorted({r["group"].strip() for r in rows}, key=lambda g: int(g))

    if a.cmd == "paste":
        if not a.item:
            sys.exit("--item is required")
        for g in groups:
            lines = [f"{r['student_id'].strip()}\t{num(r[a.item])}" for r in group_rows(rows, g) if num(r[a.item]) != ""]
            print(f"# group {g}: {len(lines)} marks")
            print("\n".join(lines))
        return

    if not a.group:
        sys.exit("--group is required")
    rs = group_rows(rows, a.group)
    if not rs:
        sys.exit(f"no students in group {a.group}")
    if a.cmd == "fill":
        if not (a.item and a.point):
            sys.exit("--item and --point are required")
        e = {r["student_id"].strip(): num(r[a.item]) for r in rs if num(r[a.item]) != ""}
        print(FILL_JS.replace("__E__", json.dumps(e, separators=(",", ":")))
              .replace("__P__", str(a.point)).replace("__G__", str(int(a.group)))
              .replace("__SAVE__", "false" if a.no_save else "true"))
    else:
        if not a.items:
            sys.exit("--items is required")
        items = a.items.split(",")
        e = {r["student_id"].strip(): [num(r[i]) for i in items] for r in rs}
        print(READBACK_JS.replace("__E__", json.dumps(e, separators=(",", ":"))).replace("__K__", str(len(items))))


if __name__ == "__main__":
    main()
