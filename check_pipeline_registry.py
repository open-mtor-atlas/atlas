"""Kontrola klinických registrů pro /pipeline/ (audit 18. 10. 2026).

Pro každé NCT v atlas_data/drug_pipeline.json -> "registry" přečte
ClinicalTrials.gov API v2 a porovná status, plánovaný start a počet účastníků
s tím, co stránka tvrdí.

Pravidla:
- `last_update` (datum poslední aktualizace V REGISTRU) se doplňuje vždy.
- `checked` (kdy jsme záznam ověřili) se posune JEN tam, kde registr souhlasí
  se stránkou. Když se něco změnilo, datum zůstává staré a skript vypíše
  WARNING: stránka pak dál poctivě říká, kdy byla data naposledy ověřená,
  a kurátor musí přepsat text karty ručně.
- Hlásí studie, kterým uplynul plánovaný start a pořád jsou "Not yet
  recruiting", a stáří `registry_checked` nad 31 dní.

Bez --write jen vypisuje. Síť: funguje z Windows stroje, ne z cloudového
sandboxu. Chyba sítě deploy NEZASTAVÍ (exit 0 s varováním); exit 1 jen při
--strict a nalezeném rozdílu.
"""
import argparse, datetime as dt, json, os, sys, urllib.request

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas_data", "drug_pipeline.json")
API = "https://clinicaltrials.gov/api/v2/studies/{}?fields=protocolSection.statusModule,protocolSection.designModule.enrollmentInfo,hasResults"
STATUS = {"NOT_YET_RECRUITING": "Not yet recruiting", "RECRUITING": "Recruiting",
          "ENROLLING_BY_INVITATION": "Enrolling by invitation", "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
          "COMPLETED": "Completed", "SUSPENDED": "Suspended", "TERMINATED": "Terminated",
          "WITHDRAWN": "Withdrawn", "UNKNOWN": "Unknown status"}
MAX_AGE_DAYS = 31


def fetch(nct):
    req = urllib.request.Request(API.format(nct), headers={"User-Agent": "mtor-atlas-registry-check"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    today = dt.date.today().isoformat()
    d = json.load(open(PATH, encoding="utf-8"))
    reg = d.get("registry") or {}
    diffs, notes, net_fail, changed = [], [], 0, False

    rc = d.get("registry_checked") or d.get("as_of")
    if rc and (dt.date.today() - dt.date.fromisoformat(rc)).days > MAX_AGE_DAYS:
        notes.append(f"registry_checked {rc} is older than {MAX_AGE_DAYS} days - monthly re-check is due")

    for nct, e in reg.items():
        try:
            j = fetch(nct)
        except Exception as ex:  # síť, 429, robots ... nic z toho nesmí shodit deploy
            net_fail += 1
            print(f"  {nct}: could not read registry ({ex.__class__.__name__}) - left unchanged")
            if e.get("status") == "Not yet recruiting" and e.get("start") and e["start"] < today:
                notes.append(f"{nct} ({e.get('drug', '')}): planned start {e['start']} has passed, stored status still not yet recruiting")
            continue
        sm = j.get("protocolSection", {}).get("statusModule", {})
        st = STATUS.get(sm.get("overallStatus", ""), sm.get("overallStatus", ""))
        start = (sm.get("startDateStruct") or {}).get("date")
        upd = (sm.get("lastUpdatePostDateStruct") or {}).get("date")
        enr = (j.get("protocolSection", {}).get("designModule", {}).get("enrollmentInfo") or {}).get("count")
        mine = []
        if st and st != e.get("status"):
            mine.append(f"status {e.get('status')!r} -> {st!r}")
        if e.get("start") and start and start != e["start"]:
            mine.append(f"start {e['start']} -> {start}")
        if e.get("enrolled") is not None and enr is not None and int(enr) != int(e["enrolled"]):
            mine.append(f"enrolled {e['enrolled']} -> {enr}")
        if e.get("results_posted") is False and j.get("hasResults"):
            mine.append("results are now posted")
        if upd and upd != e.get("last_update"):
            e["last_update"] = upd
            changed = True
        if mine:
            diffs.append(f"{nct} ({e.get('drug', '')}): " + "; ".join(mine))
        else:
            if e.get("checked") != today:
                e["checked"] = today
                changed = True
        if st == "Not yet recruiting" and start and start < today:
            notes.append(f"{nct} ({e.get('drug', '')}): planned start {start} has passed, still not yet recruiting")
        print(f"  {nct}: {st}, start {start}, enrolled {enr}, registry updated {upd}" + ("  <-- DIFFERS" if mine else ""))

    if not diffs and net_fail == 0 and reg:
        if d.get("registry_checked") != today:
            d["registry_checked"] = today
            changed = True
    for n in notes:
        print("  NOTE: " + n)
    for x in diffs:
        print("  WARNING: registry differs from /pipeline/ - edit the card text, then the date moves: " + x)
    if net_fail:
        print(f"  WARNING: {net_fail} registry record(s) could not be read; registry_checked not moved")
    if a.write and changed:
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
        json.load(open(tmp, encoding="utf-8"))
        os.replace(tmp, PATH)
        print("  drug_pipeline.json updated (last_update / checked only; card text untouched)")
    return 1 if (a.strict and diffs) else 0


if __name__ == "__main__":
    sys.exit(main())
