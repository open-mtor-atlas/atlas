#!/usr/bin/env python3
"""Atlas Phase 3 - gap_finder.py
Joins the curated Entities knowledge graph to per-study evidence tiers and
surfaces knowledge gaps: evidence deserts, mechanism->outcome disconnects,
and contradiction candidates. Data-driven, reproducible.
"""
import json
from collections import defaultdict, Counter

# study_id (short code) -> tier / species, from Phase 0 data
recs=[json.loads(l) for l in open('studies_enriched.jsonl')]
def norm(c): return (c or '').replace(' ','').upper()
tier={}; species={}; title={}
for r in recs:
    sid=norm(r.get('Study_ID'))
    tier[sid]=r.get('Evidence_Tier','')
    species[sid]=r.get('Model','')
    title[sid]=r.get('Title','')

# curated graph: entity -> (type, [study codes])   (from Airtable Entities table)
G={
"Sestrin2":("Sensor",["SAX2015"]),
"CASTOR1":("Sensor",["CHA2016"]),
"SAMTOR":("Sensor",["GU2017"]),
"v-ATPase":("Sensor",["ZON2011"]),
"Rag GTPases":("Sensor/Regulator",["SAN2008","MUT2026","SAN2010","ZON2011","BAR2013"]),
"Ragulator":("Sensor/Regulator",["SAN2010","ZON2011","MAR2012"]),
"GATOR1":("Sensor/Regulator",["BAR2013","GU2017"]),
"GATOR2":("Sensor/Regulator",["BAR2013","CHA2016"]),
"Rheb":("Regulator",["TEE2003","SAN2010","SAN2007"]),
"TSC1/TSC2":("Regulator",["INO2002","TEE2003","KAP2004","KRU2010","CHE2008","GWI2008","HOW2017","INO2003"]),
"PRAS40":("Regulator",["SAN2007"]),
"DEPTOR":("Regulator",["PET2009"]),
"AMPK":("Regulator",["ZHO2001","LOF2011","KIM2011","GWI2008","HOW2017","INO2003"]),
"Raptor":("Core",["KIM2002","HARA2002","GWI2008","SAN2007","KIM2003","CUN2007","GUE2006"]),
"Rictor":("Core",["SAR2004","SAR2006","GUE2006"]),
"mLST8":("Core",["KIM2003","GUE2006"]),
"mTOR":("Core",["SAX2017","SAB1994","HEI1991","VEL2003","KAE2005","KIM2002","HARA2002","SAR2004","CHO1996","YAN2013","KIM2003"]),
"FKBP12":("Core",["CHO1996","YAN2013"]),
"S6K1":("Effector",["SEL2009","KIM2002","HARA2002"]),
"4E-BP1":("Effector",["THO2012","HSI2012","THO2009","LAB2015","ZID2009"]),
"Akt/PKB":("Effector",["SAR2005","CAN2002","INO2002","ROM2001","SAR2004","PET2009","SAR2006","FEL2009","SAN2007","GUE2006"]),
"ULK1":("Effector",["LOF2011","HOS2009","KIM2011"]),
"TFEB":("Effector",["SET2011","MAR2012"]),
"Atg5":("Effector",["PYO2013"]),
"PI3K":("Upstream",["CAN2002","INO2002"]),
"GH/IGF-1 axis":("Upstream",["BRO1996","FON2010"]),
# outcomes / diseases
"Longevity":("Outcome",["HAR2009","MAT2017","SOL2014","MIL2011","STR2012","SEL2009","KAP2004","VEL2003","BJE2010","BIT2016","URF2017","BLA2006","BAN2014","BRO1996","MEL2003","HAR2014","KAE2005","PYO2013","MOE2025","NCT05835999","LEE2024","HAN2025","ZID2009","WIL2012","JOH2013","KEN2016","FON2010","KRA2018","FLY2013","HAL2012","LIU2020","LAP2012"]),
"Immune function":("Outcome",["MAN2014","LEE2024","MAN2018","MAN2021","KRA2018"]),
"Cognition":("Outcome",["HAL2012"]),
"Cardiac aging":("Outcome",["FLY2013"]),
"Insulin resistance":("Outcome",["LAM2012","POU2013","NCT05835999","KEN2016"]),
"Skin aging":("Outcome",["CHU2019"]),
"Muscle growth":("Outcome",["ROM2001","DRU2009","MOE2025"]),
"Autophagy":("Process",["LOF2011","BJE2010","MEL2003","RAV2004","PYO2013","SET2011","MAR2012","HOS2009","KIM2011","SPI2010","CAC2010","LIU2020"]),
"Cellular senescence":("Process",["DEM2009","LAB2015","CHU2019"]),
"Alzheimer's disease":("Disease",["SPI2010","CAC2010","BAB2025"]),
"Huntington's disease":("Disease",["RAV2004","TAN2024"]),
"Tuberous sclerosis complex":("Disease",["FRA2013","BIS2013"]),
}

TR={'A':0,'B':1,'C':2,'D':3}
def besttier(codes):
    ts=[tier.get(norm(c),'') for c in codes]
    lets=[t[0] for t in ts if t and t[0] in TR]
    if not lets: return '?'
    return sorted(lets,key=lambda x:TR[x])[0]

print("="*70); print("ENTITY EVIDENCE PROFILE (best tier / tier counts / n)"); print("="*70)
rows=[]
for name,(typ,codes) in G.items():
    tc=Counter(tier.get(norm(c),'?')[0] if tier.get(norm(c)) else '?' for c in codes)
    rows.append((typ,name,besttier(codes),dict(tc),len(codes)))
for typ,name,bt,tc,n in sorted(rows,key=lambda x:(x[0],x[1])):
    print(f"[{typ:12}] {name:28} best={bt}  n={n:2}  tiers={tc}")

print(); print("="*70)
print("GAP 1 - NUTRIENT-SENSOR EVIDENCE DESERT")
print("(sensors/upstream regulators supported ONLY by tier D, and whether they")
print(" connect to ANY aging/longevity outcome)"); print("="*70)
outcome_codes=set()
for name,(typ,codes) in G.items():
    if typ in ("Outcome","Disease","Process"):
        outcome_codes|=set(norm(c) for c in codes)
long_codes=set(norm(c) for c in G["Longevity"][1])
sensors=[n for n,(t,c) in G.items() if t in("Sensor","Sensor/Regulator")]
for s in sensors:
    codes=[norm(c) for c in G[s][1]]
    bt=besttier(codes)
    in_long=[c for c in codes if c in long_codes]
    in_any_outcome=[c for c in codes if c in outcome_codes]
    print(f"{s:16} best={bt}  ->Longevity:{len(in_long)}  ->any outcome/disease/process:{len(in_any_outcome)}")

print(); print("="*70)
print("GAP 2 - CONTRADICTION / TENSION CANDIDATES in Longevity set")
print("="*70)
# flag longevity studies whose title/species suggests negative or caveated result
neg_kw=["limited","did not","no significant","failed","not extend","distinct from","dose"]
for c in G["Longevity"][1]:
    sid=norm(c); t=title.get(sid,'')
    if any(k in t.lower() for k in neg_kw):
        print(f"  {c:12} [{tier.get(sid,'?')[:1]}] {t[:80]}")

print(); print("="*70)
print("GAP 3 - HUMAN (tier A/B) EVIDENCE for LONGEVITY vs disease indications")
print("="*70)
hb=[c for c in G["Longevity"][1] if tier.get(norm(c),'')[:1] in('A','B')]
print("Longevity studies at tier A/B (human/systematic):",hb or "NONE with hard longevity endpoint")
