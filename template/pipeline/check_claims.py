#!/usr/bin/env python3
"""Gate: every promise the film makes is sourced to what the product really does.

  npm run check:claims

Reads film/claims.md (a table: id, claim, source, status) and every string
the film shows or says: LINES and COPY in src/timeline.ts.

Fails (exit 1) when:
  - a line or an on-screen string points at a claim id the ledger lacks
  - a claim in use has no source, or a status other than OK
  - a banned word (film.config.json bannedWords) appears in anything the
    viewer reads or hears
  - any .tsx file under src/ hard-codes visible text (JSX text, a displayed
    string literal, or a text-like prop) instead of reading it from COPY:
    text outside COPY escapes this check, so it is not allowed

Reserved claim kinds that need no ledger row: story (fiction inside the
film), brand (name, tagline, URL), label (UI chrome that promises nothing),
legal (disclaimers).
"""
import json
import os
import re

import common as C

RESERVED = {"story", "brand", "label", "legal"}
cfg = C.cfg()
tl = C.timeline()
ledger_path = os.path.join(C.ROOT, "film", "claims.md")
if not os.path.exists(ledger_path):
    C.die("no film/claims.md: write the claims ledger first (see the skill's step 3)")

rows = {}
for line in open(ledger_path, encoding="utf-8"):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) >= 4 and re.fullmatch(r"[A-Z]+\d+", cells[0]):
        rows[cells[0]] = {"claim": cells[1], "source": cells[2], "status": cells[3]}

used = []
for L in tl["lines"]:
    used.append((L["claim"], f"line {L['id']}", L["text"]))
    if L.get("tts"):
        used.append((L["claim"], f"line {L['id']} (tts)", L["tts"]))
for k, v in tl["copy"].items():
    used.append((v["claim"], f"COPY.{k}", v["text"]))

fails, warns = [], []
for cid, where, text in used:
    if cid in RESERVED:
        continue
    r = rows.get(cid)
    if not r:
        fails.append(f"{where} points at claim {cid}, which film/claims.md does not have")
        continue
    if not r["source"] or r["source"].upper() in {"TODO", "TBD", "?", "-"}:
        fails.append(f"{where}: claim {cid} has no source")
    if r["status"].upper() != "OK":
        fails.append(f"{where}: claim {cid} has status '{r['status']}', not OK")

banned = cfg.get("bannedWords", [])
for cid, where, text in used:
    for b in banned:
        if re.search(r"(?<![\w-])" + re.escape(b) + r"(?![\w-])", text, re.IGNORECASE):
            fails.append(f"{where}: banned word '{b}' in \"{text}\"")

# visible text must come from COPY: no text hard-coded in any .tsx under src/
r = C.run(["node", "pipeline/jsx-text.cjs", "src"], cwd=C.ROOT)
for hit in json.loads(r.stdout):
    fails.append(f"{os.path.relpath(hit['file'], C.ROOT)}:{hit['line']}: hard-coded visible text \"{hit['text']}\" (put it in COPY)")

in_use = {c for c, _, _ in used}
for cid in rows:
    if cid not in in_use:
        warns.append(f"claim {cid} is in the ledger but nothing on screen or in the voice uses it")

for w in warns:
    print(f"WARN  {w}")
for f in fails:
    print(f"FAIL  {f}")
print(f"check:claims: {len(rows)} ledger rows, {len(used)} strings checked: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
raise SystemExit(1 if fails else 0)
