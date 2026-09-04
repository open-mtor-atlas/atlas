#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch6.py -- Ukol 11.4: fix the one-directional answers<->question
cross-link gap the 2026-08-29 audit found. The existing fix (GAP_TO_ANSWER,
2026-08-29) only covered ONE hand-verified 1:1 pair; this session's own
scan found 2 more question pages cited by 5 different answer pages total,
which is a many-to-one relationship, not a 1:1 pair -- so the right fix is
a general reverse index (same pattern as ANSWERS_BY_SID/GAPS_BY_SID from
Ukol 2), not more hand-picked pairs."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "build_pages.py"
    with open(path, encoding="utf-8") as f:
        src = f.read()

    MARKER = "# --- SEO P0 Ukol 11.4 (2026-09-02): answers->question backlinks"
    if MARKER in src:
        sys.exit("Already patched (marker found) -- aborting.")

    orig_len = len(src)

    # 1) new reverse-index helper, right after ANSWERS_BY_SID.
    anchor1 = "ANSWERS_BY_SID = _load_answer_citations()\n"
    assert src.count(anchor1) == 1, "ANSWERS_BY_SID anchor not found/unique"
    helper = f'''{MARKER} ---


def _load_answer_gap_backlinks():
    """Reverse index {{question-slug: [(answer_title, answer_url), ...]}} --
    which /answers/ pages link to a given /question/ page. Same source-of-
    truth approach as _load_answer_citations() (grep the published /answers/
    HTML, since it has no separate machine-readable source) but matching
    /question/ links instead of /study/ links.

    Supersedes the old hand-picked GAP_TO_ANSWER dict (2026-08-29, exactly
    one pair): that fix assumed every gap<->answer relationship is a clean
    1:1 pair, but this session's audit (Ukol 11.4) found questions cited by
    MULTIPLE different answer pages -- a many-to-one relationship a single
    hardcoded pair can't express. This index handles both cases uniformly
    and never goes stale when a new /answers/ page is added, unlike the
    hardcoded dict."""
    out = {{}}
    base = os.path.join(HERE, "answers")
    if not os.path.isdir(base):
        return out
    for slug in sorted(os.listdir(base)):
        fp = os.path.join(base, slug, "index.html")
        if not os.path.isfile(fp):
            continue
        try:
            text = open(fp, encoding="utf-8").read()
        except OSError:
            continue
        m = re.search(r"<h1>(.*?)</h1>", text, re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else slug
        url = f"{{SITE}}/answers/{{slug}}/"
        for qslug in set(re.findall(r"/question/([a-z0-9-]+)/", text)):
            out.setdefault(qslug, []).append((title, url))
    return out


ANSWER_GAP_BACKLINKS = _load_answer_gap_backlinks()


'''
    src = src.replace(anchor1, anchor1 + "\n\n" + helper, 1)

    # 2) remove the now-superseded hand-picked-pair dict (2026-08-29) --
    # ANSWER_GAP_BACKLINKS above covers this pair automatically plus every
    # other one, so keeping GAP_TO_ANSWER around would be unused dead code.
    old_dict = (
        '# 2026-08-29 -- cross-link narrow scope: jen dvojice, kde téma opravdu 1:1\n'
        '# odpovídá (ne automatické párování, ručně ověřeno). Přidává odkaz z\n'
        '# hypothesis/gap stránky zpátky na existující answers/ stránku se stejným\n'
        '# tématem -- opravuje jednosměrný cross-link zjištěný v Search Surface Audit\n'
        '# 2026-08-29 (forward link answers->question už existoval, tenhle je reverse).\n'
        'GAP_TO_ANSWER = {\n'
        '    "is-autophagy-actually-required-for-the-mammalian-lifespan-benefit": (\n'
        '        "autophagy-required-lifespan",\n'
        '        "Is autophagy actually required for the lifespan benefit?",\n'
        '    ),\n'
        '}\n\n'
    )
    assert src.count(old_dict) == 1, "GAP_TO_ANSWER dict definition anchor not found/unique"
    new_dict = (
        f'{MARKER} (removal): the hand-picked pair above (2026-08-29) is now\n'
        f'# handled generally by ANSWER_GAP_BACKLINKS, defined earlier in this file\n'
        f'# alongside ANSWERS_BY_SID -- see gap_page() below. ---\n\n'
    )
    src = src.replace(old_dict, new_dict, 1)

    # 3) gap_page(): replace the single hand-picked-pair lookup with the
    # general reverse index, rendering ALL matching answers (1 or many).
    old2 = (
        '    if slug in GAP_TO_ANSWER:\n'
        '        aslug, atitle = GAP_TO_ANSWER[slug]\n'
        '        body.append(f\'<p class="meta">Direct plain-language answer: \'\n'
        '                    f\'<a href="{SITE}/answers/{e(aslug)}/">{e(atitle)}</a></p>\')\n'
    )
    assert src.count(old2) == 1, "GAP_TO_ANSWER lookup anchor not found/unique"
    new2 = (
        '    backlinks = ANSWER_GAP_BACKLINKS.get(slug, [])\n'
        '    if backlinks:\n'
        '        label = "Discussed in the plain-language answer" if len(backlinks) == 1 \\\n'
        '            else "Discussed in these plain-language answers"\n'
        '        items = " · ".join(f\'<a href="{e(u)}">{e(t)}</a>\' for t, u in backlinks)\n'
        '        body.append(f\'<p class="meta">{label}: {items}</p>\')\n'
    )
    src = src.replace(old2, new2, 1)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

    check = open(path, encoding="utf-8").read()
    assert len(check) == len(src), "post-write length mismatch: %d != %d" % (len(check), len(src))
    print(f"Patched {path}: {orig_len} -> {len(src)} bytes.")


if __name__ == "__main__":
    main()
