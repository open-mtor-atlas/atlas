"""extract_base64_images.py -- 2026-09-05

Vytahne base64 obrazky z index.html a atlas_data/author_bios_baked.json do
img/people/ a nahradi je cestami. Duvod: 100 fotek autoru bylo vlozeno primo
do HTML jako data: URI, coz delalo 52 % velikosti index.html (1,83 MB z 3,53 MB)
a znovu se stahovalo na kazde ze 47 author stranek. Jako soubory je prohlizec
i CDN nacachuji.

Pojmenovani je kanonicky odvozene z author_bios_baked.json; v index.html se
nahrazuje podle SHODY OBSAHU (sha1 base64), takze obe vrstvy ukazuji na tytez
soubory a nevznikaji duplicity.

Idempotentni -- opakovane spusteni nic nezmeni. Po spusteni je nutne prepocitat
staticke stranky (build_pages.py), aby i ony odkazovaly na soubory.
"""
import json, re, os, base64, unicodedata, hashlib, collections

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
os.makedirs("img/people", exist_ok=True)

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()

# 1) kanonicka jmena z baked JSON
P = "atlas_data/author_bios_baked.json"
raw = open(P, encoding="utf-8").read()
d = json.loads(raw)
by_content = {}          # sha1(base64) -> "/img/people/x.jpg"
n = collections.Counter()
for key, o in d.items():
    if not isinstance(o, dict): continue
    name = slug(o.get("full") or key)
    for field, suffix in (("photo", ""), ("thumb", "-thumb")):
        v = o.get(field)
        if not (isinstance(v, str) and v.startswith("data:image")): continue
        m = re.match(r"data:image/([a-z+]+);base64,(.+)$", v, re.S)
        ext = {"jpeg": "jpg"}.get(m.group(1), m.group(1))
        fn = "img/people/%s%s.%s" % (name, suffix, ext)
        open(fn, "wb").write(base64.b64decode(m.group(2) + "==="))
        by_content[hashlib.sha1(m.group(2).encode()).hexdigest()] = "/" + fn
        o[field] = "/" + fn
        n[field] += 1
open(P, "w", encoding="utf-8", newline="\n").write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")

# 2) index.html: nahrad podle shody obsahu, jinak zaloz novy soubor
h = open("index.html", encoding="utf-8").read()
extra = 0
def repl(m):
    global extra
    fmt, b64 = m.group(1), m.group(2)
    k = hashlib.sha1(b64.encode()).hexdigest()
    if k in by_content:
        return by_content[k]
    ext = {"jpeg": "jpg", "svg+xml": "svg"}.get(fmt, fmt)
    fn = "img/people/misc-%s.%s" % (k[:10], ext)
    open(fn, "wb").write(base64.b64decode(b64 + "==="))
    by_content[k] = "/" + fn
    extra += 1
    return "/" + fn

before = len(h)
h = re.sub(r'data:image/([a-z+]+);base64,([A-Za-z0-9+/=]+)', repl, h)
open("index.html", "w", encoding="utf-8", newline="\n").write(h)

print("z JSON:", dict(n), "| navic jen v index.html:", extra)
print("index.html: %.2f MB -> %.2f MB" % (before/1e6, len(h)/1e6))
print("souboru: %d, duplicit obsahu: %d" % (
    len(os.listdir("img/people")),
    sum(c-1 for c in collections.Counter(
        hashlib.md5(open("img/people/"+f,"rb").read()).hexdigest()
        for f in os.listdir("img/people")).values() if c > 1)))
