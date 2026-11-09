#!/usr/bin/env python3
"""Merge patch3_*.json (researched rewrites) into atlas_data/author_bios_baked.json.
Only text fields are replaced; photo/thumb/credit and any other field stay as they are.
Validates style, sids and the K13 lab location rules (imports Atlas_v2/scripts/gates.py).
--apply writes; without it only reports."""
import json,glob,re,sys,os,unicodedata,shutil
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
BIOS=os.path.join(ROOT,'atlas_data','author_bios_baked.json')
sys.path.insert(0,os.path.join(os.path.dirname(ROOT),'Atlas_v2','scripts'))
import gates
INVIS=re.compile('[​‌‍‎‏⁠-⁤﻿­‪-‮⁦-⁩]')
BANNED=re.compile(r'\b(renowned|leading|pioneer\w*|pivotal|landscape|delve\w*|crucial|notably|testament|groundbreaking|cutting-edge)\b',re.I)
def scrub(x):
    if isinstance(x,str):
        x=INVIS.sub('',x).replace(' ',' ').replace(' ',' ').replace(' ',' ')
        x=x.replace('‘',"'").replace('’',"'").replace('“','"').replace('”','"').replace('…','...')
        x=x.replace('—',', ').replace('&mdash;',', ')
        return unicodedata.normalize('NFC',x)
    if isinstance(x,list): return [scrub(i) for i in x]
    if isinstance(x,dict): return {k:scrub(v) for k,v in x.items()}
    return x
TEXT=('full','lab_name','lab_url','orcid','role','sub','story','highlights')
B=json.load(open(BIOS,encoding='utf-8'))
upd={}; side={}; probs=[]
for f in sorted(glob.glob(os.path.join(HERE,'patch3_*.json'))):
    try: p=json.load(open(f,encoding='utf-8'))
    except Exception as e: probs.append((os.path.basename(f),'invalid json',str(e))); continue
    for k,v in p.items():
        if k not in B: probs.append((k,'unknown key','')); continue
        v=scrub(v)
        side[k]={'sources':v.get('sources',[]),'note':v.get('note','')}
        new={a:v[a] for a in TEXT if v.get(a) not in (None,'',[],{})}
        miss=[a for a in ('role','sub','story','highlights','lab_name') if a not in new]
        if miss: probs.append((k,'missing',miss)); continue
        t=json.dumps({a:new[a] for a in ('role','sub','story','highlights')},ensure_ascii=False)
        if re.search(r'https?://|www\.|@[A-Za-z0-9-]+\.[a-z]{2,}',t): probs.append((k,'url/email in text','skip')); continue
        if BANNED.search(t): probs.append((k,'banned word',BANNED.search(t).group(0)))
        if set(new['highlights'])-set(B[k].get('highlights',{})): probs.append((k,'new sid in highlights',sorted(set(new['highlights'])-set(B[k]['highlights'])))); continue
        if 'orcid' in new and not re.fullmatch(r'\d{4}-\d{4}-\d{4}-\d{3}[\dX]',new['orcid']): probs.append((k,'bad orcid',new['orcid'])); new.pop('orcid')
        if 'lab_url' in new and not new['lab_url'].startswith('http'): new.pop('lab_url')
        loc=gates.lab_loc(new['lab_name'])
        if not loc: probs.append((k,'lab_name without location',new['lab_name'])); continue
        parts=[x.strip() for x in loc.split(',')]; c=parts[-1]
        if (len(parts)==1 and c not in gates.LAB_CITY_STATES) or c in gates.LAB_COUNTRY_FIX or (c in gates.LAB_THREE_PART and len(parts)!=3):
            probs.append((k,'K13 location',loc)); continue
        if not isinstance(new['story'],list) or not (1<=len(new['story'])<=5): probs.append((k,'story shape',len(new.get('story') or []))); continue
        upd[k]=new
B2={k:dict(b) for k,b in B.items()}
for k,new in upd.items(): B2[k].update(new)
# full K13 incl. city consistency
tmp='/tmp/k13root3'; os.makedirs(tmp+'/data',exist_ok=True)
json.dump(B2,open(tmp+'/data/author_bios_baked.json','w',encoding='utf-8'),ensure_ascii=False)
try: shutil.copy(os.path.join(ROOT,'atlas_data','lab_geo.json'),tmp+'/data/lab_geo.json')
except Exception: pass
gates.k13_lab_locations(tmp)
print('updates ok',len(upd),'problems',len(probs))
for pr in probs: print('  ',pr)
json.dump(side,open(os.path.join(HERE,'research_sources_2026-10-30.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
if '--apply' in sys.argv:
    raw=open(BIOS,'rb').read()
    if json.loads(raw.decode('utf-8'))!=B: raise SystemExit('bios changed on disk since read, rerun')
    open(BIOS+'.bak4-2026-10-30','wb').write(raw)
    open(BIOS,'wb').write(json.dumps(B2,ensure_ascii=False,indent=1).encode('utf-8'))
    print('written',len(upd))
