#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reconcile_with_origin.py -- pull in whatever someone else pushed, WITHOUT
throwing away what this machine just built.

WHY THIS EXISTS
---------------
deploy.bat does not merge. It backs index.html up, moves HEAD to origin/main
with a mixed reset, restores the backup over the top and commits. That is fine
when nobody else pushed in the meantime, and silently destructive when they
did -- so a gate was added that simply ABORTED:

    ABORTED: index.html on GitHub has changed since your last sync.
    Fix: git pull origin main, reconcile or reapply your edits ...

"Reapply your edits by hand" is not a real instruction when the edits are a
667 KB machine-generated ATLAS_STUDIES line. This script does the reconciling
so the deploy can carry on.

WHAT IT DOES
------------
Three-way merge, per file, using:

    base   = merge-base(HEAD, origin/main)   -- what our edits are based on
    theirs = origin/main                     -- what somebody else pushed
    ours   = the working tree                -- what this machine just built

Only files that CHANGED UPSTREAM (base -> origin/main) are looked at; a file
nobody else touched needs no reconciling, whatever we did to it.

    ours == base            -> take theirs      (we never touched it)
    ours == theirs          -> nothing to do    (same edit, already in sync)
    generated artifact      -> keep ours        (see GENERATED_WHOLESALE)
    otherwise               -> git merge-file 3-way
                                 clean            -> keep the merge
                                 conflict, but every conflicting line on both
                                 sides is a machine-stamped line -> keep ours
                                 for those hunks  (see MACHINE_LINE)
                                 real conflict    -> STOP, touch nothing

Then, and only if every file resolved, it moves HEAD to origin/main with a
MIXED reset -- exactly what deploy.bat did at this point anyway -- so the
commit that follows is a clean fast-forward carrying merged content.

PLAN-THEN-APPLY: nothing is written until every path has resolved. A conflict
leaves the working tree byte-for-byte as it was, so a failed run is a no-op
you can re-run after fixing it, not a half-merged mess.

WHAT IT DELIBERATELY WILL NOT DO
--------------------------------
* Never rewrites deploy.bat / *.cmd / *.ps1. cmd.exe reads a batch file by byte
  offset as it runs; rewriting the script that is currently executing is the
  exact hazard documented at the top of deploy.bat. If one of those changed
  upstream we stop and tell you to pull by hand.
* Never resolves a real conflict for you. Two humans editing the same prose
  needs a human.
* Never touches history beyond the mixed reset deploy.bat was going to do
  anyway. No rebase, no merge commit, no force anything.

Exit codes:  0 = reconciled (or nothing to do)   1 = conflicts, nothing written
             2 = git/repo problem
"""

import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.abspath(__file__))
REMOTE_REF = "origin/main"


# --------------------------------------------------------------------------
# Policy tables
# --------------------------------------------------------------------------

# Files we NEVER auto-write, because doing so can break the running process
# or is otherwise not ours to decide.
NEVER_WRITE_SUFFIXES = (".bat", ".cmd", ".ps1")

# Wholly machine-generated artifacts. These are re-derived from Airtable, from
# pathway/model.json or from the corpus by bake_from_mcp.py / sync_airtable.py /
# build_pages.py / build_chunk_index.py. A textual merge of two different
# generator runs is meaningless -- one of them is simply newer. If we
# regenerated it in this session, ours is the newer one and wins; if we did not
# touch it, the `ours == base` rule above already took theirs.
#
# Matched as path prefixes (posix separators) or exact names.
GENERATED_WHOLESALE_PREFIXES = (
    "atlas_data/",
    "atlas_fulltext/chunk_index.json",
    "atlas_fulltext/chunks.jsonl",
    "atlas_fulltext/raw/",
    "atlas_rag/index/",
    "academy_data/_sid_to_lesson.json",
)
GENERATED_WHOLESALE_NAMES = (
    "sitemap.xml",
    "sitemap-home.xml",
    "sitemap-studies.xml",
    "sitemap-entities.xml",
    "sitemap-authors.xml",
    "sitemap-questions.xml",
    "sitemap-answers.xml",
    "sitemap-academy.xml",
    "llms.txt",
)
# Pre-rendered page trees written by build_pages.py. Same argument: generated,
# so newer wins rather than merged.
GENERATED_PAGE_DIRS = (
    "study", "gene", "complex", "drug", "disease", "outcome", "process",
    "intervention", "nutrient", "organelle", "condition", "author",
    "question", "browse", "answers", "glossary", "about", "academy",
)

# Lines inside index.html that are stamped by a script rather than written by a
# human. If BOTH sides of a merge conflict consist only of these, the conflict
# is two generator runs disagreeing -- not two people disagreeing -- so ours
# (the newer bake) wins and deploy.bat's stamp_updated.py / prerender_tabs.js
# re-derive them a few steps later anyway.
MACHINE_LINE = (
    re.compile(r"^\s*const ATLAS_(STUDIES|ENTITIES|EVENTS|GAPS|UPDATED)\s*="),
    re.compile(r"<!--/?PRERENDER:"),
    re.compile(r'id="lastUpdated"'),
    re.compile(r'id="ipyStudyCount"'),
    re.compile(r'id="atlasStatStudies"'),
    re.compile(r'id="atlasStatEntities"'),
    re.compile(r"\d+\+ curated mTOR studies"),
    re.compile(r"about \d+ studies rated by evidence tier"),
)


def is_generated_wholesale(path):
    p = path.replace("\\", "/")
    if p in GENERATED_WHOLESALE_NAMES:
        return True
    for pref in GENERATED_WHOLESALE_PREFIXES:
        if p == pref or p.startswith(pref):
            return True
    top = p.split("/", 1)[0]
    if len(p.split("/")) > 1 and top in GENERATED_PAGE_DIRS:
        return True
    return False


def is_machine_line(line):
    return any(rx.search(line) for rx in MACHINE_LINE)


# --------------------------------------------------------------------------
# Canonicalising machine stamps before the merge
# --------------------------------------------------------------------------
#
# WHY: the very first real-world run of this script hit a false conflict.
# Upstream had deleted a hand-written <p> from the About bio; the <footer> with
# <span id="lastUpdated"> sits on the NEXT line, and our bake had re-stamped
# that footer. Two adjacent changed lines are one diff hunk, so a prose deletion
# and a timestamp collided and the merge stopped for a human -- on a difference
# no human ever made.
#
# Fix: before merging, rewrite every machine-stamped value in base and theirs to
# whatever OURS says. Those lines then become identical on all three sides and
# cannot conflict, so the merge only ever sees the genuine human edits. This is
# safe by construction because the stamps are re-derived a few steps later by
# stamp_updated.py / prerender_tabs.js, and the ATLAS_* constants come straight
# from the Airtable bake this machine just ran - i.e. ours IS the newer data.

# Whole-line constants: unique anchors, one line each (the arrays are single
# lines, up to ~670 KB of them).
LINE_ANCHORS = (
    re.compile(rb"^const ATLAS_STUDIES = "),
    re.compile(rb"^const ATLAS_ENTITIES = "),
    re.compile(rb"^const ATLAS_EVENTS = "),
    re.compile(rb"^const ATLAS_GAPS = "),
    re.compile(rb"^const ATLAS_UPDATED = "),
)

# Inline stamped values: keep the surrounding human text mergeable, swap only
# the generated value. (pattern, number-of-groups-wrapping-the-value)
VALUE_SUBS = (
    re.compile(rb'(<span id="lastUpdated">)([^<]*)(</span>)'),
    re.compile(rb'(<span id="ipyStudyCount">)(\d+)(</span>)'),
    re.compile(rb'(<span id="atlasStatStudies">)(\d+)(</span>)'),
    re.compile(rb'(<span id="atlasStatEntities">)(\d+)(</span>)'),
    re.compile(rb"()(\d+)(\+ curated mTOR studies)"),
    re.compile(rb"(about )(\d+)( studies rated by evidence tier)"),
)

PRERENDER_BLOCK = re.compile(
    rb"<!--PRERENDER:([A-Za-z0-9_-]+)-->.*?<!--/PRERENDER:\1-->", re.S)


def canonicalise_generated(text, ours):
    """Rewrite machine-stamped regions of `text` to match `ours`.

    Byte-in, byte-out. A pattern absent from either side is simply skipped, so
    this is a no-op on files that carry none of these stamps.
    """
    if not text or not ours:
        return text

    # 1. Whole-line constants.
    our_lines = ours.split(b"\n")
    lines = text.split(b"\n")
    for anchor in LINE_ANCHORS:
        our_line = next((l for l in our_lines if anchor.match(l)), None)
        if our_line is None:
            continue
        for idx, l in enumerate(lines):
            if anchor.match(l):
                lines[idx] = our_line
                break
    text = b"\n".join(lines)

    # 2. Pre-rendered blocks, matched by their tab id.
    our_blocks = {m.group(1): m.group(0) for m in PRERENDER_BLOCK.finditer(ours)}
    if our_blocks:
        def swap(m):
            return our_blocks.get(m.group(1), m.group(0))
        text = PRERENDER_BLOCK.sub(swap, text)

    # 3. Inline stamped values.
    for rx in VALUE_SUBS:
        our_m = rx.search(ours)
        if not our_m:
            continue
        our_val = our_m.group(2)
        text = rx.sub(lambda m: m.group(1) + our_val + m.group(3), text)

    return text


# --------------------------------------------------------------------------
# git helpers
# --------------------------------------------------------------------------

def git(*args, **kw):
    """Run git, return (rc, stdout_bytes, stderr_text)."""
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false"] + list(args),
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", "replace")


def git_text(*args):
    rc, out, err = git(*args)
    return rc, out.decode("utf-8", "replace").strip(), err


def blob_at(rev, path):
    """Bytes of `path` at `rev`, or None if it does not exist there."""
    rc, out, _ = git("cat-file", "blob", "%s:%s" % (rev, path))
    return out if rc == 0 else None


def exists_at(rev, path):
    rc, _, _ = git("rev-parse", "--verify", "--quiet", "%s:%s" % (rev, path))
    return rc == 0


def worktree_blob_sha(path):
    """Index-normalised sha of the working-tree file, or None if absent.

    --path makes git apply .gitattributes' clean filter, so a CRLF working file
    hashes to the LF blob git actually stores. Without it this comparison
    depends on core.autocrlf and reports phantom differences.
    """
    full = os.path.join(REPO, path)
    if not os.path.exists(full):
        return None
    rc, out, _ = git_text("hash-object", "--path=%s" % path, "--", path)
    return out if rc == 0 else None


def sha_at(rev, path):
    rc, out, _ = git_text("rev-parse", "--verify", "--quiet", "%s:%s" % (rev, path))
    return out if rc == 0 else None


def is_binary(data):
    return b"\x00" in (data or b"")[:8192]


# --- line endings ---------------------------------------------------------
#
# .gitattributes pins `* text=auto eol=lf`, so git STORES text as LF and the
# working tree is supposed to be LF too. In practice index.html drifts to CRLF
# -- stamp_updated.py and friends open it in Python text mode, which on Windows
# writes \r\n. Nobody notices, because `git hash-object --path=` applies the
# clean filter and the blob comes out identical either way.
#
# A three-way merge does notice. Feeding a CRLF working file against two LF
# blobs makes every single line differ, so merge-file reports the entire file
# as one 6700-line conflict. That is exactly what the first version of this
# script did. So: merge in repo form (LF), write back in whatever form the file
# already had. We fix nothing we were not asked to fix.
#
# Done by hand rather than via `git hash-object -w` + `cat-file` because writing
# objects into .git from the Cowork FUSE bridge is unreliable - see the note at
# the bottom of deploy.bat.

def to_repo_form(data):
    """CRLF -> LF, idempotent. What git stores for a `text eol=lf` file."""
    return data.replace(b"\r\n", b"\n")


def detect_eol(data):
    """The file's own dominant line ending, so we can write it back unchanged."""
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n")
    return b"\r\n" if crlf and crlf * 2 >= lf else b"\n"


def to_worktree_form(data_lf, eol):
    if eol == b"\r\n":
        return data_lf.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return data_lf


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------

CONFLICT_START = re.compile(rb"^<{7} ")
CONFLICT_MID = re.compile(rb"^={7}$")
CONFLICT_BASE = re.compile(rb"^\|{7}")
CONFLICT_END = re.compile(rb"^>{7} ")


def three_way(ours_bytes, base_bytes, theirs_bytes):
    """Return (merged_bytes, had_conflicts) using git merge-file."""
    tmp = tempfile.mkdtemp(prefix="atlas_merge_")
    try:
        po = os.path.join(tmp, "ours")
        pb = os.path.join(tmp, "base")
        pt = os.path.join(tmp, "theirs")
        for p, b in ((po, ours_bytes), (pb, base_bytes), (pt, theirs_bytes)):
            with open(p, "wb") as fh:
                fh.write(b)
        proc = subprocess.run(
            ["git", "merge-file", "--diff3",
             "-L", "ours (this machine)", "-L", "base (last common)",
             "-L", "theirs (origin/main)", po, pb, pt],
            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode < 0:
            return None, True
        with open(po, "rb") as fh:
            merged = fh.read()
        return merged, proc.returncode > 0
    finally:
        for name in ("ours", "base", "theirs"):
            try:
                os.unlink(os.path.join(tmp, name))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def resolve_machine_conflicts(merged):
    """Take OUR side of any conflict hunk whose content is machine-stamped.

    Returns (bytes, unresolved_hunks, machine_hunks_resolved). A hunk qualifies
    only if EVERY non-empty line on both the ours side and the theirs side
    matches MACHINE_LINE -- one line of real prose anywhere in the hunk and we
    refuse to touch it.
    """
    out = []
    lines = merged.split(b"\n")
    i = 0
    unresolved = 0
    resolved = 0
    while i < len(lines):
        if not CONFLICT_START.match(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        # Collect the hunk: <<<<<<< ours ||||||| base ======= theirs >>>>>>>
        i += 1
        ours, base, theirs = [], [], []
        bucket = ours
        closed = False
        while i < len(lines):
            ln = lines[i]
            if CONFLICT_BASE.match(ln):
                bucket = base
            elif CONFLICT_MID.match(ln):
                bucket = theirs
            elif CONFLICT_END.match(ln):
                closed = True
                i += 1
                break
            else:
                bucket.append(ln)
            i += 1
        if not closed:
            # Malformed; bail out and let the caller treat it as unresolved.
            out.extend([b"<<<<<<< ours (this machine)"] + ours + base + theirs)
            unresolved += 1
            continue

        def all_machine(chunk):
            real = [l for l in chunk if l.strip()]
            return bool(real) and all(
                is_machine_line(l.decode("utf-8", "replace")) for l in real
            )

        ours_ok = all_machine(ours) or not [l for l in ours if l.strip()]
        theirs_ok = all_machine(theirs) or not [l for l in theirs if l.strip()]
        if ours_ok and theirs_ok:
            out.extend(ours)
            resolved += 1
        else:
            out.extend([b"<<<<<<< ours (this machine)"] + ours +
                       [b"||||||| base (last common)"] + base +
                       [b"======="] + theirs +
                       [b">>>>>>> theirs (origin/main)"])
            unresolved += 1
    return b"\n".join(out), unresolved, resolved


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def changed_upstream(base, remote):
    """[(status, path)] for base -> remote, NUL-separated so spaces are safe."""
    rc, out, err = git("diff", "--name-status", "-z", base, remote)
    if rc != 0:
        print("ERROR: git diff %s..%s failed: %s" % (base, remote, err))
        sys.exit(2)
    parts = out.split(b"\x00")
    items = []
    i = 0
    while i < len(parts):
        st = parts[i].decode("utf-8", "replace")
        if not st:
            i += 1
            continue
        code = st[0]
        if code in ("R", "C"):
            # rename/copy: <status>\0<from>\0<to>
            if i + 2 >= len(parts):
                break
            src = parts[i + 1].decode("utf-8", "replace")
            dst = parts[i + 2].decode("utf-8", "replace")
            items.append(("D", src))
            items.append(("A", dst))
            i += 3
        else:
            if i + 1 >= len(parts):
                break
            items.append((code, parts[i + 1].decode("utf-8", "replace")))
            i += 2
    return items


# Locks a killed or bridged git leaves behind. deploy.bat deletes these
# unconditionally as its very first git-related step, so inside a deploy they
# are already gone. Running this script STANDALONE skipped that, and the first
# real run died on exactly that: a stale .git/index.lock left by a Cowork
# sandbox session, which cannot unlink files under .git through the FUSE bridge.
# The merge had already been written to disk, but `git reset` failed, so HEAD
# never moved and the subsequent push was rejected as non-fast-forward.
KNOWN_LOCKS = (
    os.path.join(".git", "index.lock"),
    os.path.join(".git", "ORIG_HEAD.lock"),
    os.path.join(".git", "HEAD.lock"),
    os.path.join(".git", "refs", "heads", "main.lock"),
    os.path.join(".git", "refs", "remotes", "origin", "main.lock"),
    os.path.join(".git", "objects", "maintenance.lock"),
)


def check_locks(clear):
    """Report (or clear) stale git locks. Returns True if any still block us."""
    present = [p for p in KNOWN_LOCKS if os.path.exists(os.path.join(REPO, p))]
    if not present:
        return False
    if clear:
        left = []
        for p in present:
            try:
                os.unlink(os.path.join(REPO, p))
            except OSError as e:
                left.append((p, e))
        if not left:
            print("    cleared %d stale git lock(s)." % len(present))
            return False
        present = [p for p, _ in left]
    print("")
    print("    ABORTED: git lock file(s) present - every git write would fail:")
    for p in present:
        print("      %s" % p)
    print("")
    print("    These are almost always stale: a killed git, or a Cowork sandbox")
    print("    session that created a file under .git but could not unlink it.")
    print("    If no git process is actually running, delete them and re-run:")
    print("")
    print("        Remove-Item .git\\index.lock -Force          # PowerShell")
    print("        del /f /q .git\\index.lock                   # cmd.exe")
    print("")
    print("    Or re-run this script with --clear-locks. deploy.bat already")
    print("    deletes them before it gets here, so a normal deploy is unaffected.")
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    quiet = "--quiet" in sys.argv

    rc, _, err = git("rev-parse", "--git-dir")
    if rc != 0:
        print("ERROR: not a git repository: %s" % err)
        return 2

    # Fail loudly and early rather than half-way through, with the merge on disk
    # and HEAD left behind.
    if check_locks("--clear-locks" in sys.argv):
        return 2

    if "--no-fetch" not in sys.argv:
        rc, _, err = git("fetch", "origin")
        if rc != 0:
            print("ERROR: git fetch origin failed: %s" % err)
            print("       Check your network / credentials and re-run.")
            return 2

    rc, head, _ = git_text("rev-parse", "HEAD")
    if rc != 0:
        print("ERROR: cannot resolve HEAD.")
        return 2
    rc, remote, _ = git_text("rev-parse", REMOTE_REF)
    if rc != 0:
        print("ERROR: cannot resolve %s -- has the remote ever been fetched?" % REMOTE_REF)
        return 2
    rc, base, _ = git_text("merge-base", "HEAD", REMOTE_REF)
    if rc != 0:
        print("ERROR: no common ancestor between HEAD and %s." % REMOTE_REF)
        return 2

    if base == remote:
        if not quiet:
            if head == remote:
                print("    in sync with %s - nothing to reconcile." % REMOTE_REF)
            else:
                print("    %s has nothing new; you are ahead by local commits." % REMOTE_REF)
        return 0

    items = changed_upstream(base, remote)
    if not items:
        if not quiet:
            print("    no file changes upstream - nothing to reconcile.")
        return 0

    print("    %s moved on: %d file(s) changed upstream since %s"
          % (REMOTE_REF, len(items), base[:8]))

    plan = []          # (kind, path, payload)
    conflicts = []     # (path, reason)
    notes = []

    for status, path in items:
        if path.lower().endswith(NEVER_WRITE_SUFFIXES):
            conflicts.append((
                path,
                "changed upstream, and this script never rewrites .bat/.cmd/.ps1 "
                "- cmd.exe is reading deploy.bat by byte offset right now"))
            continue

        base_sha = sha_at(base, path)
        their_sha = sha_at(remote, path)
        our_sha = worktree_blob_sha(path)

        # --- upstream deleted the file -----------------------------------
        if status == "D" or their_sha is None:
            if our_sha is None:
                notes.append("%s: deleted upstream, already gone here" % path)
                continue
            if our_sha == base_sha:
                plan.append(("delete", path, None))
                notes.append("%s: deleted upstream, we had no local change -> deleting" % path)
            else:
                conflicts.append((path, "deleted upstream but modified here"))
            continue

        # --- upstream added the file --------------------------------------
        if base_sha is None:
            if our_sha is None:
                plan.append(("checkout", path, None))
                notes.append("%s: new upstream -> taking theirs" % path)
            elif our_sha == their_sha:
                notes.append("%s: new upstream, identical here" % path)
            else:
                conflicts.append((path, "added upstream and a different file exists here"))
            continue

        # --- upstream modified the file -----------------------------------
        if our_sha is None:
            conflicts.append((path, "modified upstream but missing/deleted here"))
            continue
        if our_sha == base_sha:
            plan.append(("checkout", path, None))
            notes.append("%s: changed upstream, untouched here -> taking theirs" % path)
            continue
        if our_sha == their_sha:
            notes.append("%s: same change on both sides" % path)
            continue

        # Both sides changed it.
        if is_generated_wholesale(path):
            notes.append("%s: generated artifact changed on both sides -> keeping "
                         "ours, it is the newer build" % path)
            continue

        base_b = blob_at(base, path)
        their_b = blob_at(remote, path)
        with open(os.path.join(REPO, path), "rb") as fh:
            our_raw = fh.read()

        if is_binary(base_b) or is_binary(their_b) or is_binary(our_raw):
            conflicts.append((path, "binary file changed on both sides - cannot merge"))
            continue

        # Merge in repo form (LF); remember how the file is written on disk so
        # we can put it back exactly as we found it.
        eol = detect_eol(our_raw)
        our_b = to_repo_form(our_raw)
        base_b = to_repo_form(base_b)
        their_b = to_repo_form(their_b)

        # Neutralise machine stamps on the other two sides so a re-baked
        # timestamp cannot collide with a human edit on the adjacent line.
        base_c = canonicalise_generated(base_b, our_b)
        their_c = canonicalise_generated(their_b, our_b)
        if their_c == our_b:
            notes.append("%s: only machine-stamped values differed -> keeping this build"
                         % path)
            continue

        merged, had_conflict = three_way(our_b, base_c, their_c)
        if merged is None:
            conflicts.append((path, "git merge-file failed"))
            continue
        if not had_conflict:
            plan.append(("write", path, to_worktree_form(merged, eol)))
            notes.append("%s: merged cleanly - their edits on top of this build" % path)
            continue

        merged2, unresolved, resolved = resolve_machine_conflicts(merged)
        if unresolved == 0:
            plan.append(("write", path, to_worktree_form(merged2, eol)))
            notes.append("%s: merged; %d machine-stamped hunk(s) resolved in favour of "
                         "this build - stamp_updated.py re-derives them below" % (path, resolved))
        else:
            conflicts.append((
                path,
                "%d conflicting hunk(s) contain hand-written content - a human has to "
                "decide" % unresolved))

    if not quiet:
        for n in notes:
            print("      %s" % n)

    if conflicts:
        print("")
        print("    ABORTED: could not reconcile automatically. NOTHING was changed.")
        print("")
        for path, why in conflicts:
            print("      %-46s %s" % (path, why))
        print("")
        print("    Resolve by hand, e.g.:")
        print("        git stash push -- <the file>      # park your version")
        print("        git pull origin main              # take theirs")
        print("        git stash pop                     # replay yours, fix markers")
        print("    then re-run deploy.bat.")
        return 1

    if dry_run:
        print("")
        print("    --dry-run: %d change(s) planned, nothing written." % len(plan))
        return 0

    # ---------------- apply -------------------------------------------------
    for kind, path, payload in plan:
        full = os.path.join(REPO, path)
        if kind == "checkout":
            rc, _, err = git("checkout", remote, "--", path)
            if rc != 0:
                print("    ERROR: could not check out %s from %s: %s" % (path, REMOTE_REF, err))
                return 2
        elif kind == "delete":
            rc, _, err = git("rm", "-q", "--", path)
            if rc != 0:
                try:
                    os.unlink(full)
                except OSError as e:
                    print("    ERROR: could not delete %s: %s" % (path, e))
                    return 2
        elif kind == "write":
            # Same write discipline as bake_from_mcp.py: temp file, fsync,
            # atomic replace, read back and compare. This folder is
            # OneDrive-synced and has silently truncated large writes before.
            d = os.path.dirname(full) or REPO
            fd, tmp = tempfile.mkstemp(dir=d, prefix=".reconcile_", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, full)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            with open(full, "rb") as fh:
                if fh.read() != payload:
                    print("    ERROR: %s did not survive the write intact - aborting "
                          "before anything is committed." % path)
                    return 2

    # Move HEAD to origin/main WITHOUT touching the working tree. This is the
    # same mixed reset deploy.bat performs a few steps later; doing it here
    # means the commit that follows sits cleanly on top of what everyone else
    # pushed, and carries the merged content we just wrote.
    #
    # If HEAD carries local commits that were never pushed, this flattens them:
    # their history goes away, their CONTENT survives only because it is sitting
    # in the working tree, which the mixed reset does not touch. That is exactly
    # what deploy.bat has always done here. Before relying on it, prove the
    # assumption -- if any file HEAD tracks is missing from the working tree,
    # the reset really would lose it, so stop instead.
    rc, ahead, _ = git_text("rev-list", "--count", "%s..HEAD" % remote)
    if rc == 0 and ahead.isdigit() and int(ahead) > 0:
        rc2, gone, _ = git_text("diff", "--name-only", "--diff-filter=D", "HEAD")
        if rc2 == 0 and gone:
            print("")
            print("    ABORTED: %s local commit(s) are unpushed, and these tracked files"
                  % ahead)
            print("    are missing from the working tree, so flattening HEAD would lose them:")
            for line in gone.splitlines():
                print("      %s" % line)
            print("")
            print("    Push or stash those commits first, then re-run.")
            return 1
        print("    note: %s unpushed local commit(s) will be folded into the next"
              % ahead)
        print("          commit as working-tree changes - no content is lost.")

    rc, _, err = git("reset", "--mixed", remote)
    if rc != 0:
        print("    ERROR: git reset --mixed %s failed: %s" % (REMOTE_REF, err))
        print("")
        print("    Your files ARE merged on disk, but HEAD did not move - so a push")
        print("    now would be rejected as non-fast-forward. Nothing is lost and")
        print("    nothing is half-done: the merge is idempotent, so once the git")
        print("    error above is fixed just re-run this script - it will produce")
        print("    byte-for-byte the same files and then move HEAD.")
        check_locks(False)
        return 2

    print("    reconciled: HEAD now at %s with their changes merged in." % remote[:8])
    return 0


if __name__ == "__main__":
    sys.exit(main())
