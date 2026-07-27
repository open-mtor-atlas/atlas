#!/usr/bin/env python3
"""
check_token.py -- ověří, že AIRTABLE_TOKEN je nastavený a pořád platí.

    py check_token.py

Netiskne token, jen jeho prefix a délku. Nic nezapisuje.
"""
import os, sys, json, urllib.request

BASE = "appt2U6ObDHUcRlrj"
TOKEN = os.environ.get("AIRTABLE_TOKEN")

if not TOKEN:
    print("AIRTABLE_TOKEN NENÍ nastavený v tomto okně.")
    print()
    print("Pozor na past: `set AIRTABLE_TOKEN=...` platí jen pro to jedno okno cmd.")
    print("Pro trvalé nastavení použij:")
    print("    setx AIRTABLE_TOKEN patXXXXXXXX")
    print("a pak otevři NOVÉ okno cmd (setx se do stávajícího nepropíše).")
    print()
    print("Bez něj deploy.bat bake tiše přeskočí a nasadí stará data.")
    sys.exit(1)

print("Token nalezen: %s... (%d znaků)" % (TOKEN[:8], len(TOKEN)))

def call(path):
    req = urllib.request.Request(
        "https://api.airtable.com/v0/%s" % path,
        headers={"Authorization": "Bearer " + TOKEN},
    )
    return json.load(urllib.request.urlopen(req, timeout=20))

try:
    d = call("%s/Studies?maxRecords=3&fields%%5B%%5D=Study_ID&fields%%5B%%5D=PMID" % BASE)
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", "replace")[:300]
    print("\nTOKEN NEFUNGUJE -- HTTP %s" % e.code)
    if e.code == 401:
        print("  401 = token je neplatný nebo byl zrušen. Vytvoř nový na")
        print("  https://airtable.com/create/tokens")
    elif e.code == 403:
        print("  403 = token existuje, ale nemá přístup k této bázi nebo mu chybí")
        print("  scope data.records:read. Uprav ho na airtable.com/create/tokens.")
    elif e.code == 404:
        print("  404 = báze %s není v scope tokenu." % BASE)
    print("  odpověď: %s" % body)
    sys.exit(1)
except Exception as e:
    print("\nSpojení selhalo: %s" % e)
    sys.exit(1)

print("Token PLATÍ -- báze je čitelná.")
for r in d.get("records", []):
    f = r.get("fields", {})
    print("   %-14s PMID=%s" % (f.get("Study_ID", "?"), f.get("PMID") or "-"))

# Kolik studií báze skutečně má -- kontrola proti tomu, co je v baked JSON.
try:
    total, offset = 0, None
    while True:
        p = "%s/Studies?pageSize=100&fields%%5B%%5D=Study_ID" % BASE
        if offset:
            p += "&offset=" + offset
        d2 = call(p)
        total += len(d2.get("records", []))
        offset = d2.get("offset")
        if not offset:
            break
    print("\nAirtable obsahuje %d studií." % total)
    baked = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "atlas_data", "studies_baked.json")
    if os.path.exists(baked):
        n = len(json.load(open(baked, encoding="utf-8")))
        print("studies_baked.json obsahuje %d studií." % n)
        if n != total:
            print("=> ROZDÍL %d. Spusť bake (deploy.bat s nastaveným tokenem)." % (total - n))
        else:
            print("=> Sedí, bake je aktuální.")
except Exception as e:
    print("(počet studií se nepodařilo zjistit: %s)" % e)
