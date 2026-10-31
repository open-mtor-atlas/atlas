#!/usr/bin/env python3
"""
fill_entity_ids.py -- doplní do Airtable (tabulka Entities) pole HGNC_ID a
UniProt_ID, a to jen tam, kde to UniProt potvrdí.

Zavedeno 2026-10-31 (konkurenční audit Atlasu, doporučení 4: stabilní
identifikátory entit). Airtable zůstává zdrojem pravdy; odtud jdou hodnoty
dál přes sync_airtable.py / map_entities_dump.py do entities_baked.json a do
API (entities/*.json -> "identifiers").

PRAVIDLA
--------
1. Mapa NAME_TO_SYMBOL níže obsahuje jen entity, které jsou JEDNÍM lidským
   genem/proteinem. Skupiny a komplexy (AMPK, PI3K, FoxO, Rag GTPases, Akt/PKB,
   TSC1/TSC2, v-ATPase, eIF4A, SREBP1/2, IRS-1/2, FLCN/FNIP1/2, ERK/RSK,
   PGC-1a/YY1), léky, nemoci, metabolity a drozofilí Salr tu NEJSOU a pole
   zůstává prázdné. Jedno ID u skupiny by tvrdilo víc, než Atlas ví.
2. Žádné ID se nepíše z paměti. Skript se pro každý symbol zeptá UniProtu
   (reviewed, Homo sapiens, gene_exact) a ID přijme jen když:
     - přišel právě jeden záznam,
     - jeho primární symbol genu přesně souhlasí s očekávaným,
     - záznam nese křížový odkaz na HGNC.
   Jinak entitu vypíše jako PROBLÉM a nezapíše nic.
3. Výchozí běh je suchý (dry-run): jen vypíše tabulku a uloží ji do
   atlas_data/entity_ids_proposed.csv. Zápis do Airtable dělá až --write.
4. Neprázdnou hodnotu v Airtable, která se liší od ověřené, skript nepřepíše
   (nahlásí KONFLIKT); přepsat jde jen s --force.

POUŽITÍ (Windows, ve složce repa; AIRTABLE_TOKEN musí být nastavený)
    py fill_entity_ids.py            # suchý běh
    py fill_entity_ids.py --write    # zapíše ověřené hodnoty do Airtable
Potom normální deploy_all.bat (sync_airtable.py pole stáhne).
"""
import csv, json, os, sys, time, urllib.error, urllib.parse, urllib.request

BASE = "appt2U6ObDHUcRlrj"
TABLE = "tblhFpLHVy1odzcbv"          # Entities
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(HERE, "atlas_data", "entity_ids_proposed.csv")

# Název entity v Airtable (přesně) -> schválený symbol lidského genu (HGNC).
NAME_TO_SYMBOL = {
    "mTOR": "MTOR",
    "Raptor": "RPTOR",
    "Rictor": "RICTOR",
    "mLST8": "MLST8",
    "PRAS40": "AKT1S1",
    "DEPTOR": "DEPTOR",
    "SIN1 / MAPKAP1": "MAPKAP1",
    "Rheb": "RHEB",
    "PIK3CA": "PIK3CA",
    "PTEN": "PTEN",
    "SGK1": "SGK1",
    "TBK1": "TBK1",
    "HIF-1α": "HIF1A",
    "eIF4E": "EIF4E",
    "alpha-synuclein (SNCA)": "SNCA",
    "Atg5": "ATG5",
    "PXR (NR1I2)": "NR1I2",
    "P-glycoprotein (ABCB1)": "ABCB1",
    "ULK1": "ULK1",
    "ITGA2 (Integrin alpha-2)": "ITGA2",
    "TFEB": "TFEB",
    "SLC7A5 (LAT1)": "SLC7A5",
    "LC3B (MAP1LC3B)": "MAP1LC3B",
    "FGF21": "FGF21",
    "LYCHOS (GPR155)": "GPR155",
    "Insulin": "INS",
    "Grb10": "GRB10",
    "PKM2": "PKM",                    # PKM2 je sestřihová izoforma genu PKM
    "PDCD4": "PDCD4",
    "MRPS17": "MRPS17",
    "ErbB3 (HER3)": "ERBB3",
    "USP7": "USP7",
    "SAMTOR": "BMT2",                 # dřívější C7orf60
    "p62/SQSTM1": "SQSTM1",
    "FKBP12": "FKBP1A",
    "CASTOR1": "CASTOR1",
    "SLC15A3": "SLC15A3",
    "TNKS2 (Tankyrase-2)": "TNKS2",
    "TBC1D7": "TBC1D7",
    "Sestrin2": "SESN2",
    "TAX1BP1": "TAX1BP1",
    "LKB1 (STK11)": "STK11",
    "SLC38A9": "SLC38A9",
    "Beclin-1 (BECN1)": "BECN1",
    "RUBCN (Rubicon)": "RUBCN",
    "PFKFB3": "PFKFB3",
    "PIP4K2A": "PIP4K2A",
    "TET1": "TET1",
    "REDD1 (DDIT4)": "DDIT4",
    "S6K1": "RPS6KB1",
    "GADD45alpha": "GADD45A",
    "4E-BP1": "EIF4EBP1",
    "Vps34 (PIK3C3)": "PIK3C3",
    "ASCL1": "ASCL1",
    "LARS (leucyl-tRNA synthetase)": "LARS1",
}


def http_json(url, headers=None, data=None, method=None, retries=4):
    """UniProt občas vrátí 500 nebo timeout; opakujeme s rostoucí pauzou.
    4xx (kromě 429) se neopakuje, to je chyba dotazu, ne výpadek."""
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers=headers or {}, data=data, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == retries:
                raise
        time.sleep(2 * attempt)


UNIPROT_RENAMED = set()


def uniprot_lookup(symbol):
    """Vrátí (uniprot, hgnc, problém). Přijme jen jednoznačnou shodu."""
    q = "gene_exact:%s AND reviewed:true AND organism_id:9606" % symbol
    url = ("https://rest.uniprot.org/uniprotkb/search?query=%s"
           "&fields=accession,gene_primary,gene_synonym,xref_hgnc&format=json&size=5"
           % urllib.parse.quote(q))
    try:
        d = http_json(url, {"Accept": "application/json"})
    except Exception as e:
        return None, None, "dotaz na UniProt selhal: %s" % e
    res = d.get("results", [])
    if len(res) != 1:
        return None, None, "UniProt vrátil %d záznamů (čekám 1)" % len(res)
    r = res[0]
    genes = r.get("genes") or [{}]
    prim = (genes[0].get("geneName") or {}).get("value", "")
    syns = [s.get("value", "") for s in genes[0].get("synonyms", [])]
    if prim != symbol and symbol not in syns:
        return None, None, "primární symbol v UniProtu je %r, čekám %r" % (prim, symbol)
    # UniProt někdy vede gen pod starším jménem (SAMTOR vs. HGNC BMT2). Symbol
    # musí být aspoň mezi synonymy a HGNC ID se bere z křížového odkazu, takže
    # je to správný záznam; rozdíl se jen vypíše.
    hg = [x["id"] for x in r.get("uniProtKBCrossReferences", []) if x.get("database") == "HGNC"]
    if len(hg) != 1 or not hg[0].startswith("HGNC:"):
        return None, None, "HGNC křížový odkaz: %r" % hg
    if prim != symbol:
        UNIPROT_RENAMED.add(r["primaryAccession"])
    return r["primaryAccession"], hg[0], ""


def airtable_headers():
    tok = os.environ.get("AIRTABLE_TOKEN")
    if not tok:
        sys.exit("AIRTABLE_TOKEN není nastavený (stejný jako pro sync_airtable.py).")
    return {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}


def airtable_entities():
    rows, offset = [], None
    while True:
        url = ("https://api.airtable.com/v0/%s/%s?pageSize=100"
               "&fields%%5B%%5D=Entity_Name&fields%%5B%%5D=HGNC_ID&fields%%5B%%5D=UniProt_ID" % (BASE, TABLE))
        if offset:
            url += "&offset=" + offset
        d = http_json(url, airtable_headers())
        rows += d["records"]
        offset = d.get("offset")
        if not offset:
            return rows


def main():
    write, force = "--write" in sys.argv, "--force" in sys.argv
    ents = {}
    for r in airtable_entities():
        ents[r["fields"].get("Entity_Name", "")] = r
    todo, problems, conflicts = [], [], []
    print("%-34s %-9s %-11s %-11s %s" % ("entita", "symbol", "UniProt", "HGNC", "stav"))
    for name, sym in NAME_TO_SYMBOL.items():
        rec = ents.get(name)
        if rec is None:
            problems.append((name, sym, "entita s tímto názvem není v Airtable"))
            print("%-34s %-9s %s" % (name, sym, "CHYBÍ V AIRTABLE"))
            continue
        up, hg, err = uniprot_lookup(sym)
        time.sleep(0.3)
        if err:
            problems.append((name, sym, err))
            print("%-34s %-9s PROBLÉM: %s" % (name, sym, err))
            continue
        cur_h = rec["fields"].get("HGNC_ID", "") or ""
        cur_u = rec["fields"].get("UniProt_ID", "") or ""
        state = "ok (už zapsáno)" if (cur_h, cur_u) == (hg, up) else "k zápisu"
        if state == "k zápisu" and up in UNIPROT_RENAMED:
            state += " (UniProt ho vede pod jiným symbolem)"
        if (cur_h and cur_h != hg) or (cur_u and cur_u != up):
            state = "KONFLIKT (v Airtable %s / %s)" % (cur_h, cur_u)
            conflicts.append(name)
        print("%-34s %-9s %-11s %-11s %s" % (name, sym, up, hg, state))
        if not state.startswith("ok") and (not state.startswith("KONFLIKT") or force):
            todo.append((rec["id"], name, sym, up, hg))

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["record_id", "entity", "symbol", "uniprot", "hgnc"])
        for t in todo:
            w.writerow(t)
    print("\nověřeno k zápisu: %d, problémů: %d, konfliktů: %d  (tabulka: %s)"
          % (len(todo), len(problems), len(conflicts), OUT_CSV))
    for n, s, e in problems:
        print("  PROBLÉM  %s (%s): %s" % (n, s, e))

    if not write:
        print("\nSuchý běh. Pro zápis do Airtable spusť znovu s --write.")
        return
    for i in range(0, len(todo), 10):
        chunk = todo[i:i + 10]
        body = {"records": [{"id": rid, "fields": {"HGNC_ID": hg, "UniProt_ID": up}}
                            for rid, _n, _s, up, hg in chunk]}
        http_json("https://api.airtable.com/v0/%s/%s" % (BASE, TABLE), airtable_headers(),
                  json.dumps(body).encode("utf-8"), "PATCH")
        print("zapsáno %d–%d z %d" % (i + 1, i + len(chunk), len(todo)))
        time.sleep(0.3)
    print("Hotovo. Další: deploy_all.bat (nebo py sync_airtable.py).")


if __name__ == "__main__":
    main()
