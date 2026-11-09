#!/usr/bin/env python3
"""Validate patch_N.json files and (with --apply) merge their bios into atlas_data/author_bios_baked.json.
Read-modify-write once, same serialisation as the existing file (indent=1, ensure_ascii=False, no trailing newline)."""
import json,glob,re,sys,os,unicodedata,collections
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
BIOS=os.path.join(ROOT,'atlas_data','author_bios_baked.json')
S={s['sid']:s for s in json.load(open(os.path.join(ROOT,'atlas_data','studies_baked.json'),encoding='utf-8'))}
raw=open(BIOS,'rb').read(); B=json.loads(raw.decode('utf-8'))
INVIS=re.compile('[​‌‍‎‏⁠⁡⁢⁣⁤﻿­‪-‮⁦-⁩]')
def scrub(x):
    if isinstance(x,str):
        x=INVIS.sub('',x).replace(' ',' ').replace(' ',' ').replace(' ',' ')
        x=x.replace('‘',"'").replace('’',"'").replace('“','"').replace('”','"')
        return unicodedata.normalize('NFC',x)
    if isinstance(x,list): return [scrub(i) for i in x]
    if isinstance(x,dict): return {scrub(k):scrub(v) for k,v in x.items()}
    return x
ALLOWED={'full','lab_name','role','mono','init','sub','story','highlights','orcid'}
problems=[]; merged={}; air=[]; unres=[]; photo=[]
for f in sorted(glob.glob(os.path.join(HERE,'patch_*.json'))):
    try: p=json.load(open(f,encoding='utf-8'))
    except Exception as e: problems.append((f,'invalid json',str(e))); continue
    for k,b in p.get('bios',{}).items():
        b=scrub(b)
        if k in B: problems.append((k,'already has bio','skipped')); continue
        if k in merged: problems.append((k,'duplicate across patches','skipped')); continue
        extra=set(b)-ALLOWED
        if extra: problems.append((k,'extra fields',sorted(extra))); b={a:v for a,v in b.items() if a in ALLOWED}
        miss=[a for a in ('full','role','init','mono','sub','story','highlights') if not b.get(a)]
        if miss: problems.append((k,'missing',miss)); continue
        txt=json.dumps(b,ensure_ascii=False)
        if re.search(r'https?://|@[A-Za-z0-9.-]+\.[a-z]{2,}',txt): problems.append((k,'url/email in text',''))
        if '—' in txt or '&mdash;' in txt: problems.append((k,'em dash','kept'))
        bad=[s for s in b['highlights'] if s not in S]
        if bad: problems.append((k,'unknown sid in highlights',bad)); continue
        if not isinstance(b['story'],list) or not all(isinstance(t,str) and t.strip() for t in b['story']): problems.append((k,'bad story','')); continue
        merged[k]=b
    for a in p.get('airtable',[]):
        if a['key'] in merged or True: air.append(scrub(a))
    unres+= [scrub(u) for u in p.get('unresolved',[])]; photo+=p.get('needs_photo',[])
air=[a for a in air if a['key'] in merged]
print('patches',len(glob.glob(os.path.join(HERE,'patch_*.json'))),'bios ok',len(merged),'airtable rows',len(air),'unresolved',len(unres),'needs_photo',len(photo))
print('problems:',len(problems))
for pr in problems[:60]: print('  ',pr)
print(collections.Counter(u['reason'].split(';')[0][:40] for u in unres).most_common(10))
json.dump({'bios':merged,'airtable':air,'unresolved':unres,'needs_photo':[k for k in photo if k in merged]},open(os.path.join(HERE,'merged_preview.json'),'w'),ensure_ascii=False,indent=1)
if '--apply' in sys.argv:
    if os.path.getmtime(BIOS)!=os.path.getmtime(BIOS): raise SystemExit('changed')
    B2=dict(B); B2.update(merged)
    out=json.dumps(B2,ensure_ascii=False,indent=1).encode('utf-8')
    open(BIOS+'.bak-2026-10-30','wb').write(raw)
    open(BIOS,'wb').write(out)
    print('written',len(B),'->',len(B2))
