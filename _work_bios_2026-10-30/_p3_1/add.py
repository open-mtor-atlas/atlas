import json,sys,os
out='patch3_1.json'
cur=json.load(open(out)) if os.path.exists(out) else {}
new=json.load(open(sys.argv[1]))
cur.update(new)
json.dump(cur,open(out,'w'),ensure_ascii=False,indent=1)
print(len(cur),'keys')
