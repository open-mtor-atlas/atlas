#!/usr/bin/env python3
"""
indexnow_ping.py -- notify Bing/Yandex/Seznam (IndexNow protocol) that URLs
changed, are new, or were removed. Google does NOT participate in IndexNow
(it only reads sitemap.xml + crawls normally), so this is a Bing/Seznam/
Yandex-only lever.

2026-09-24: PINGUJE JEN ZMENENE URL
-----------------------------------
Do 24. 9. skript pri kazdem deployi poslal vsechny URL ze sitemap, a to
dvakrat (jednou z deploy.bat nad V1, jednou z deploy_v2.bat nad dist/).
Bing Webmaster Tools ukazal 94 tis. odeslanych URL za mesic pro web s ~740
adresami. IndexNow je urceny pro zmeny, ne pro opakovane hlaseni celeho webu.

Jak to ted funguje:
  * Pro kazdou URL ze sitemap se spocita hash jejiho HTML v servirovanem
    adresari (dist/), po odstraneni casovych razitek. Footer kazde stranky
    nese "Page last updated <time ...>" s casem buildu; ten se meni pri
    kazdem deployi i kdyz obsah ne (~346 stranek na kazdy deploy), takze
    se pred hashovanim vyhazuje.
  * Hashe z minuleho uspesneho pingu jsou v .indexnow_state.json vedle
    tohoto skriptu (v .gitignore, stav je lokalni pro Petruv stroj).
  * Pinguji se jen URL nove, zmenene, nebo zmizele ze sitemap (IndexNow
    chce i odstranene adresy, aby je vyhledavac mohl vyradit).
  * Stav se ulozi az po HTTP 200/202. Kdyz ping selze, pristi deploy ty
    same URL zkusi znovu.
  * Prvni beh bez stavoveho souboru jen zalozi stav a nic neposle (Bing uz
    web zna cely). Vynutit plny ping: --all.
  * Bez --dir (tj. volani z deploy.bat nad V1) skript nic neposila: web se
    od 9. 9. servuje z Atlas_v2/dist pres deploy_v2.bat, V1 koren uz neni
    to, co vyhledavac uvidi. Vynutit stare chovani: --force-v1.

USAGE
    py indexnow_ping.py --dir <dist>             # pingne jen zmeny
    py indexnow_ping.py --dir <dist> --dry-run   # vypise, co by poslal
    py indexnow_ping.py --dir <dist> --all       # pingne vse a prepise stav

Key file b776efc62f29fa8493b94373aa71b565.txt must be live at the site root.
"""
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = "mtor-atlas.org"
BASE = f"https://{HOST}/"
KEY = "b776efc62f29fa8493b94373aa71b565"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
ENDPOINT = "https://api.indexnow.org/indexnow"
STATE_FILE = os.path.join(HERE, ".indexnow_state.json")

ARGS = sys.argv[1:]
DRY = "--dry-run" in ARGS
ALL = "--all" in ARGS
FORCE_V1 = "--force-v1" in ARGS

SRC = None
if "--dir" in ARGS:
    SRC = os.path.abspath(ARGS[ARGS.index("--dir") + 1])

# Casova razitka, ktera se meni s kazdym buildem a nejsou zmenou obsahu.
VOLATILE = [
    re.compile(r"<time\b[^>]*>.*?</time>", re.S),
    re.compile(r'"dateModified"\s*:\s*"[^"]*"'),
    re.compile(r'<meta[^>]+(?:article:modified_time|og:updated_time)[^>]*>', re.I),
]


def sitemap_files(src):
    """Vsechny dilci sitemapy v adresari, ne rucni seznam (viz 9. 9. 2026)."""
    return [f for f in sorted(os.listdir(src))
            if f.startswith("sitemap") and f.endswith(".xml") and f != "sitemap.xml"]


def collect_urls(src):
    urls, seen = [], set()
    files = sitemap_files(src)
    if not files:
        print(f"  ! v {src} nejsou zadne sitemap-*.xml")
    for fname in files:
        text = open(os.path.join(src, fname), encoding="utf-8").read()
        for u in re.findall(r"<loc>\s*(.*?)\s*</loc>", text):
            if u not in seen:
                seen.add(u)
                urls.append(u)
    return urls


def url_to_file(src, url):
    if not url.startswith(BASE):
        return None
    rel = url[len(BASE):].split("#")[0].split("?")[0]
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    path = os.path.join(src, *rel.split("/"))
    if os.path.isdir(path):
        path = os.path.join(path, "index.html")
    return path if os.path.isfile(path) else None


def content_hash(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    for rx in VOLATILE:
        text = rx.sub("", text)
    text = text.replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"  ! stav {STATE_FILE} nejde precist ({e}), beru jako prazdny")
        return None


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=0, sort_keys=True)
    os.replace(tmp, STATE_FILE)


def send(urls):
    """Posle URL po davkach (limit IndexNow je 10 000). True = vse prijato."""
    ok = True
    for i in range(0, len(urls), 10000):
        payload = {"host": HOST, "key": KEY, "keyLocation": KEY_LOCATION,
                   "urlList": urls[i:i + 10000]}
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                print(f"IndexNow response: HTTP {resp.status}")
                ok = ok and resp.status in (200, 202)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            print(f"IndexNow HTTPError {e.code}: {body}")
            if e.code == 403:
                print(f"403 usually means the key file isn't live at {KEY_LOCATION}.")
            ok = False
        except Exception as e:
            print(f"IndexNow request failed: {e}")
            ok = False
    return ok


def main():
    if SRC is None and not FORCE_V1:
        print("IndexNow: bez --dir nic neposilam. Web se servuje z Atlas_v2/dist "
              "a pinguje ho deploy_v2.bat (jen zmenene URL). Stare chovani: --force-v1.")
        return
    src = SRC or HERE

    urls = collect_urls(src)
    print(f"Collected {len(urls)} URLs from sitemaps in {src}.")
    if not urls:
        print("No URLs found, aborting.")
        return

    current = {}
    missing = 0
    for u in urls:
        p = url_to_file(src, u)
        if p is None:
            missing += 1
            current[u] = "nofile"
        else:
            current[u] = content_hash(p)
    if missing:
        print(f"  ! {missing} URL ze sitemap nema soubor v {src} (hash 'nofile')")

    old = load_state()
    if old is None and not ALL:
        print("IndexNow: stavovy soubor neexistuje, zakladam ho a nic neposilam "
              "(Bing web zna cely). Plny ping: --all.")
        if not DRY:
            save_state(current)
        return

    old = old or {}
    if ALL:
        changed, removed = list(urls), []
    else:
        changed = [u for u in urls if old.get(u) != current[u]]
        removed = [u for u in old if u not in current]
    to_send = changed + removed
    print(f"IndexNow: {len(changed)} novych/zmenenych, {len(removed)} odstranenych, "
          f"{len(urls) - len(changed)} beze zmeny.")
    for u in to_send[:15]:
        print("  ", u)
    if len(to_send) > 15:
        print(f"   ... a dalsich {len(to_send) - 15}")

    if not to_send:
        print("IndexNow: neni co poslat.")
        return
    if DRY:
        print("DRY RUN -- nothing sent, state not changed.")
        return
    if send(to_send):
        save_state(current)
        print("IndexNow: stav ulozen.")
    else:
        print("IndexNow: ping neprosel, stav nechavam, pristi deploy to zkusi znovu.")


if __name__ == "__main__":
    main()
