#!/usr/bin/env python3
"""
indexnow_ping.py -- notify Bing/Yandex/Seznam (IndexNow protocol) that URLs
changed or are new. Google does NOT participate in IndexNow (it only reads
sitemap.xml + crawls normally), so this is a Bing/Seznam/Yandex-only lever --
run it in addition to, not instead of, the normal Google Search Console
sitemap resubmission / URL Inspection workflow.

WHY THIS EXISTS
---------------
Added 2026-08-23 as part of an indexation push. IndexNow is a single free
ping that fans out to every participating engine at once (Bing, Yandex,
Seznam.cz, Naver) via api.indexnow.org. It costs nothing, has no daily quota
like GSC's URL Inspection tool, and is safe to run after every deploy.

SETUP (one-time, already done 2026-08-23)
-------------------------------------------
A key file was added at the repo root: b776efc62f29fa8493b94373aa71b565.txt
containing just that key. It must be LIVE at
https://mtor-atlas.org/b776efc62f29fa8493b94373aa71b565.txt before this
script's pings will validate -- i.e. it needs to go out in a normal
deploy.bat run first. Until then, running this script will get a 403 from
the IndexNow API (key file not found), which is expected and harmless.

USAGE (after deploy.bat has shipped the key file at least once)
-----------------------------------------------------------------
    py indexnow_ping.py              # pings all URLs from every sitemap-*.xml
    py indexnow_ping.py --dry-run    # just prints the URL list and count, sends nothing

Safe to run after every future deploy -- IndexNow has no meaningful rate
limit for a site this size, and re-pinging an unchanged URL is a no-op for
the search engines on the other end.
"""
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = "mtor-atlas.org"
KEY = "b776efc62f29fa8493b94373aa71b565"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
ENDPOINT = "https://api.indexnow.org/indexnow"
DRY = "--dry-run" in sys.argv

SITEMAP_FILES = [
    "sitemap-home.xml", "sitemap-studies.xml", "sitemap-entities.xml",
    "sitemap-questions.xml", "sitemap-authors.xml", "sitemap-answers.xml",
]


def collect_urls():
    urls = []
    for fname in SITEMAP_FILES:
        path = os.path.join(HERE, fname)
        if not os.path.exists(path):
            print(f"  (skip, not found: {fname})")
            continue
        text = open(path, encoding="utf-8").read()
        found = re.findall(r"<loc>(.*?)</loc>", text)
        urls.extend(found)
    # de-dupe, keep order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main():
    urls = collect_urls()
    print(f"Collected {len(urls)} URLs from sitemaps.")
    if DRY:
        for u in urls[:20]:
            print(" ", u)
        if len(urls) > 20:
            print(f"  ... and {len(urls) - 20} more")
        print("DRY RUN -- nothing sent.")
        return

    if not urls:
        print("No URLs found, aborting.")
        return

    # IndexNow accepts up to 10,000 URLs per POST -- one batch is enough here.
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"IndexNow response: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"IndexNow HTTPError {e.code}: {body}")
        if e.code == 403:
            print(
                "403 usually means the key file isn't live yet at "
                f"{KEY_LOCATION} -- run deploy.bat first, then retry."
            )
    except Exception as e:
        print(f"IndexNow request failed: {e}")


if __name__ == "__main__":
    main()
