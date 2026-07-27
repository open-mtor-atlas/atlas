#!/usr/bin/env python3
"""Stamp the 'last updated' timestamp (ATLAS_UPDATED) in index.html to now (UTC).
Called by deploy.bat and sync_airtable.py so the footer reflects the real build time.

Writes atomically (temp file + fsync + os.replace) and re-reads the published
file to verify it matches byte-for-byte and still ends with </html> before
declaring success. This repo lives in a OneDrive-synced folder that has
repeatedly truncated large writes to index.html mid-file (and, it turns out,
truncated writes to these very deploy scripts too) -- a plain write()+fsync()
is NOT enough to catch that. This script retries a few times and raises
(non-zero exit) instead of silently leaving a truncated file for deploy.bat
to commit and push."""
import re, os, sys, time, datetime, json

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def write_verified(path, content, expect_suffix="</html>", attempts=5):
    expected_len = len(content.encode("utf-8"))
    last_err = None
    for attempt in range(1, attempts + 1):
        tmp = path + ".tmp%d" % os.getpid()
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            with open(tmp, encoding="utf-8") as f:
                check = f.read()
            if len(check.encode("utf-8")) != expected_len or not check.rstrip().endswith(expect_suffix):
                raise RuntimeError(
                    "pre-publish verification failed (attempt %d): wrote %d bytes, read back %d, tail=%r"
                    % (attempt, expected_len, len(check.encode("utf-8")), check[-80:])
                )
            os.replace(tmp, path)
            with open(path, encoding="utf-8") as f:
                final = f.read()
            if len(final.encode("utf-8")) != expected_len or not final.rstrip().endswith(expect_suffix):
                raise RuntimeError(
                    "post-publish verification failed (attempt %d): expected %d bytes, found %d, tail=%r"
                    % (attempt, expected_len, len(final.encode("utf-8")), final[-80:])
                )
            return
        except Exception as e:
            last_err = e
            print("  stamp_updated.write_verified: attempt %d/%d failed: %s" % (attempt, attempts, e))
            time.sleep(2)
    raise RuntimeError("stamp_updated.write_verified: all %d attempts failed: %s" % (attempts, last_err))


def _const_len(h, name):
    """Length of a top-level `const NAME = [...]` array literal inside index.html."""
    m = re.search(r"const %s = (\[.*?\]);\n" % name, h, re.S)
    if not m:
        return None
    try:
        return len(json.loads(m.group(1)))
    except Exception:
        return None


def refresh_counts(h):
    """Re-derive the study/entity counts that are written into the markup.

    Most counts on the page are computed at runtime from ATLAS_STUDIES, so they
    are always right in a browser. These five are not, and had drifted:

      * the three <meta> descriptions and the JSON-LD "about N studies" blurb
        are read by crawlers, Google snippets and link previews, where no JS
        ever runs -- nothing else will ever correct them;
      * ipyStudyCount / atlasStatStudies / atlasStatEntities are static
        fallbacks that JS overwrites on load, so they only show to a reader
        without JS -- but a wrong number is worse than no number.

    Baking them here means they cannot go stale again: every deploy stamps them
    from the data actually in the file.
    """
    n_studies = _const_len(h, "ATLAS_STUDIES")
    n_entities = _const_len(h, "ATLAS_ENTITIES")
    if not n_studies or not n_entities:
        print("  refresh_counts: could not read ATLAS_STUDIES/ATLAS_ENTITIES - counts left alone")
        return h
    subs = [
        (r"\d+\+ curated mTOR studies", "%d+ curated mTOR studies" % n_studies),
        (r"about \d+ studies rated by evidence tier",
         "about %d studies rated by evidence tier" % n_studies),
        (r'(<span id="ipyStudyCount">)\d+(</span>)', r"\g<1>%d\g<2>" % n_studies),
        (r'(<span id="atlasStatStudies">)\d+(</span>)', r"\g<1>%d\g<2>" % n_studies),
        (r'(<span id="atlasStatEntities">)\d+(</span>)', r"\g<1>%d\g<2>" % n_entities),
    ]
    hits = 0
    for pat, rep in subs:
        h, n = re.subn(pat, rep, h)
        hits += n
    print("  refresh_counts: %d spots stamped (%d studies, %d entities)"
          % (hits, n_studies, n_entities))
    return h


def main():
    h = open(p, encoding="utf-8").read()
    if not h.rstrip().endswith("</html>"):
        sys.exit(
            "ABORT: index.html does not currently end with </html> (tail: %r) -- "
            "refusing to stamp/deploy a file that's already truncated. "
            "Restore a known-good index.html before re-running." % h[-80:]
        )
    h2, n = re.subn(r'const ATLAS_UPDATED = "[^"]*";', f'const ATLAS_UPDATED = "{ts}";', h, count=1)
    h2 = refresh_counts(h2)
    write_verified(p, h2, expect_suffix="</html>")
    print(("stamped" if n else "ATLAS_UPDATED not found -"), "last updated:", ts)


if __name__ == "__main__":
    main()
