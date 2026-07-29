#!/bin/bash
# deploy.sh -- run after atlas_data/studies_baked.json (and optionally
# atlas_data/gaps_baked.json) have been written from an Airtable MCP fetch.
# Bakes index.html, rebuilds the search index, commits, and pushes.
#
# This repo's .git/index.lock has repeatedly gotten stuck (likely OneDrive/AV
# holding a handle on the Windows side) in a way this sandbox's FUSE bridge to
# the Windows folder cannot delete, even though the same lock is harmless and
# self-clears when deploy.bat runs natively on Windows. So: try the normal
# `git add`/`git commit` path first; if it fails because of index.lock, fall
# back to plumbing commands (hash-object/mktree/commit-tree/update-ref) which
# never touch the index file at all.
set -e
cd "$(dirname "$0")"

echo "=== stamp + bake from atlas_data/*_baked.json ==="
python3 bake_from_mcp.py

echo
echo "=== scientific claim calibration gate ==="
if ! python3 validate_claims.py --strict --json atlas_data/claim_validation.json; then
    echo "ABORTED: validate_claims.py found claims stronger than the evidence behind them."
    echo "Fix the wording (or the tier), or re-run without --strict once each finding is reviewed."
    exit 1
fi

echo
echo "=== pathway model gate (Pathway & Mechanism 2.0) ==="
# Dvě nezávislé branky. Validátor hlídá kalibraci a integritu modelu,
# smoke test hlídá, že se to skutečně vykreslí a že trasy učí to, co mají.
# Ani jedna nenahrazuje druhou: přeznačení RAG-MTORC1 z "recruitment" na
# "activation" projde validátorem a padne na smoke testu.
if ! python3 validate_pathway.py --strict; then
    echo "ABORTED: pathway/model.json failed the scientific calibration gate."
    exit 1
fi
if command -v node >/dev/null 2>&1; then
    if ! node pathway/smoke_test.js; then
        echo "ABORTED: pathway explorer smoke test failed."
        exit 1
    fi
else
    echo "  (node not available - skipping the 1150-assertion explorer smoke test)"
fi

echo
echo "=== rebuild deep-search chunk index (local only) ==="
python3 atlas_fulltext/build_chunk_index.py || echo "  (chunk index build failed - continuing with existing chunk_index.json)"

echo
echo "=== commit + push ==="
rm -f .git/index.lock 2>/dev/null || true

if git add index.html atlas_fulltext/chunk_index.json 2>/tmp/gitadd.err && \
   git commit -m "Atlas update $(date -u +'%Y-%m-%d %H:%M:%S UTC') (automated)" 2>/tmp/gitcommit.err; then
    echo "committed via normal git add/commit"
else
    echo "normal commit path failed (likely stuck index.lock) - falling back to plumbing commit"
    cat /tmp/gitadd.err /tmp/gitcommit.err 2>/dev/null || true

    H_INDEX=$(git hash-object -w index.html)
    H_CHUNK=$(git hash-object -w atlas_fulltext/chunk_index.json)
    NEW_SUBTREE=$(git ls-tree HEAD:atlas_fulltext | sed "s#blob [0-9a-f]*\(\tchunk_index.json\)#blob $H_CHUNK\1#" | git mktree)
    NEW_TOP=$(git ls-tree HEAD | sed "s#100644 blob [0-9a-f]*\(\tindex.html\)#100644 blob $H_INDEX\1#; s#040000 tree [0-9a-f]*\(\tatlas_fulltext\)#040000 tree $NEW_SUBTREE\1#" | git mktree)
    NEW_COMMIT=$(GIT_AUTHOR_NAME="golfparada2" GIT_AUTHOR_EMAIL="golfparada2@users.noreply.github.com" \
      GIT_COMMITTER_NAME="golfparada2" GIT_COMMITTER_EMAIL="golfparada2@users.noreply.github.com" \
      git commit-tree "$NEW_TOP" -p HEAD -m "Atlas update $(date -u +'%Y-%m-%d %H:%M:%S UTC') (automated, plumbing commit)")
    git update-ref refs/heads/main "$NEW_COMMIT"
    echo "committed via plumbing: $NEW_COMMIT"
fi

git push origin main 2>/tmp/gitpush.err || true
cat /tmp/gitpush.err 2>/dev/null || true

echo
echo "=== verifying push actually landed (local ref-tracking update can fail even when the push itself succeeds) ==="
LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(git ls-remote origin main | cut -f1)
if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
    echo "PUSH CONFIRMED: origin/main is now $REMOTE_SHA"
    echo "=== done. live in ~1 min at https://open-mtor-atlas.github.io/atlas/ ==="
else
    echo "PUSH FAILED: local HEAD $LOCAL_SHA != origin/main $REMOTE_SHA"
    exit 1
fi
