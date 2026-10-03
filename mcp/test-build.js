// Offline test of the one-build cache in lib.js (no network).
// Simulates the CDN serving an older copy of one file after a deploy, and a
// deploy landing while the server is warm.  Run: node test-build.js
import { Atlas } from './lib.js';

const B = (commit, snap) => ({ api_version: '1.0.0', source_commit: commit, corpus_snapshot: snap });
const A1 = B('aaaa', '2026-10-03T20:00:00+0200');
const B2 = B('bbbb', '2026-10-03T20:31:00+0200');
const C3 = B('cccc', '2026-10-03T21:39:00+0200');

let site, staleOnce, log = [];
globalThis.fetch = async (url) => {
  const u = new URL(url); const rel = u.pathname.replace('/api/v1/', ''); const bust = u.search !== '';
  log.push(rel + (bust ? '?' : ''));
  let build = site;
  if (!bust && staleOnce[rel]) { build = staleOnce[rel]; }            // CDN keeps an old copy, no-query URL only
  const body = rel === 'meta.json' ? { ...build, counts: {} } : { meta: build, data: [{ id: rel, from: build.source_commit }] };
  return { status: 200, ok: true, json: async () => body };
};

let fail = 0;
const check = (name, cond) => { console.log((cond ? 'ok   ' : 'FAIL ') + name); if (!cond) fail++; };

// 1) stale CDN copy of studies.json is not mixed in
site = B2; staleOnce = { 'studies.json': A1 };
let at = new Atlas('https://x.test/api/v1');
const s1 = await at.list('studies');
check('stale studies.json re-fetched past CDN', s1[0].from === 'bbbb' && log.includes('studies.json?'));
const e1 = await at.list('entities');
check('entities from same build', e1[0].from === 'bbbb');

// 2) deploy lands while warm: a newer file moves the whole cache
site = C3; staleOnce = {};
const r1 = await at.list('relations');
check('newer build adopted', r1[0].from === 'cccc' && at.build.commit === 'cccc');
const s2 = await at.list('studies');
check('cache dropped, studies re-read from new build', s2[0].from === 'cccc');

// 3) meta re-check after TTL drops the cache
at.metaAt = 0; site = B('dddd', '2026-10-03T22:00:00+0200');
const e2 = await at.list('entities');
check('meta TTL picks up next deploy', e2[0].from === 'dddd');

// 4) a copy that stays stale is returned but not cached
site = B('eeee', '2026-10-03T23:00:00+0200');
at = new Atlas('https://x.test/api/v1'); await at.meta();
globalThis.fetch = (orig => async (url) => { const r = await orig(url); const j = await r.json();
  if (url.includes('questions.json')) { j.meta = A1; j.data = [{ from: 'aaaa' }]; } return { ...r, json: async () => j }; })(globalThis.fetch);
const q = await at.list('questions');
check('stubborn stale copy not cached', q[0].from === 'aaaa' && !at.cache.has('questions.json'));

// 5) DST: +0100 snapshot later than +0200 one is recognised as newer
at = new Atlas('https://x.test/api/v1');
globalThis.fetch = async (url) => { const rel = new URL(url).pathname.replace('/api/v1/', '');
  const m = rel === 'meta.json' ? B('w1', '2026-10-25T02:30:00+0200') : B('w2', '2026-10-25T02:10:00+0100');
  return { status: 200, ok: true, json: async () => rel === 'meta.json' ? m : { meta: m, data: [{ from: m.source_commit }] } }; };
const d = await at.list('studies');
check('DST offset compared as time, not text', d[0].from === 'w2' && at.build.commit === 'w2');

console.log(fail ? `FAILED ${fail}` : 'ALL OK'); process.exit(fail ? 1 : 0);
