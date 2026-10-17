// Data access and queries for the mTOR Atlas MCP server.
//
// Everything here reads the Atlas's public, static JSON API
// (https://mtor-atlas.org/api/v1/). There is no Atlas-side search endpoint:
// the lists are small, so they are downloaded once, cached, and filtered here.
// Nothing is invented or inferred: every returned object is an API record or a
// subset of one, and every study carries its evidence code WITH its label and
// the note that the code describes the kind of study, not its quality.
// No top-level Node imports: the same file runs in Node (npm package) and in
// Cloudflare Workers (remote server). Local-folder reading is loaded lazily.

export const DEFAULT_BASE = 'https://mtor-atlas.org/api/v1';

// One build at a time (2026-10-03). Every API file carries the build it came
// from (meta.source_commit, meta.corpus_snapshot). Two things could otherwise
// hand a client a mix of builds after a deploy:
//   1. this server's own cache, which used to keep each file for an hour on
//      its own clock, so studies.json could be one build and entities.json
//      the next;
//   2. the CDN in front of GitHub Pages, which caches each URL separately for
//      up to 10 minutes (cache-control: max-age=600).
// So the cache now belongs to one build: meta.json is re-checked every
// META_TTL_MS, and a new commit there drops everything cached. A file whose
// commit differs from the current build is never mixed in silently: an older
// copy is re-fetched past the CDN cache, a newer one means a deploy happened
// and the whole cache moves to it.
const META_TTL_MS = 5 * 60 * 1000;
const STALE_RETRIES = 2;
const RETRY_DELAY_MS = 1500;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const buildOf = (v) => {
  const m = v?.meta ?? v;          // meta.json has the fields at top level
  if (!m?.source_commit) return null;
  // "2026-10-03T21:39:25+0200" -> epoch ms; the offset changes with daylight
  // saving, so the strings themselves must not be compared.
  const t = Date.parse(String(m.corpus_snapshot ?? '').replace(/([+-]\d\d)(\d\d)$/, '$1:$2'));
  return { commit: m.source_commit, snapshot: Number.isFinite(t) ? t : 0 };
};

export class Atlas {
  constructor(base = globalThis.process?.env?.ATLAS_API_BASE || DEFAULT_BASE) {
    this.base = base.replace(/\/+$/, '');
    this.cache = new Map();
    this.build = null;        // { commit, snapshot } the cache belongs to
    this.metaAt = 0;          // when meta.json was last checked
  }

  isLocal() { return !/^https?:\/\//i.test(this.base); }

  async fetchJson(rel, bust) {
    const url = `${this.base}/${rel}` + (bust ? `?build=${encodeURIComponent(bust)}` : '');
    const res = await fetch(url, { headers: { accept: 'application/json' }, cache: 'no-store' });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`Atlas API ${res.status} for ${rel}`);
    return res.json();
  }

  adopt(build) {
    if (this.build?.commit !== build.commit) this.cache.clear();
    this.build = build;
  }

  /** Re-read meta.json at most every META_TTL_MS; a new build empties the cache. */
  async syncBuild() {
    if (this.isLocal() || Date.now() - this.metaAt < META_TTL_MS) return;
    const meta = await this.fetchJson('meta.json', this.build ? String(Date.now()) : null);
    this.metaAt = Date.now();
    const b = buildOf(meta);
    if (b && (!this.build || b.snapshot >= this.build.snapshot)) this.adopt(b);
    if (meta) this.cache.set('meta.json', meta);
  }

  async raw(rel) {
    if (this.isLocal()) {
      if (this.cache.has(rel)) return this.cache.get(rel);
      const { readFile } = await import('node:fs/promises');
      const path = await import('node:path');
      const root = this.base.replace(/^file:\/\//, '');
      const v = JSON.parse(await readFile(path.join(root, rel), 'utf-8'));
      this.cache.set(rel, v);
      return v;
    }
    await this.syncBuild();
    if (this.cache.has(rel)) return this.cache.get(rel);
    let v = await this.fetchJson(rel);
    for (let i = 0; v && i <= STALE_RETRIES; i++) {
      const b = buildOf(v);
      if (!b || !this.build || b.commit === this.build.commit) break;
      if (b.snapshot > this.build.snapshot) {      // a deploy happened since meta was read
        this.adopt(b); this.metaAt = Date.now(); this.cache.delete('meta.json');
        break;
      }
      if (i === STALE_RETRIES) break;               // still an old CDN copy: give up, see below
      await sleep(RETRY_DELAY_MS);
      v = await this.fetchJson(rel, this.build.commit);   // query string = separate CDN cache key
    }
    const b = buildOf(v);
    // Only cache what belongs to the current build; a stubborn stale copy is
    // returned once (better than failing the tool call) but never kept.
    if (v && (!b || !this.build || b.commit === this.build.commit)) this.cache.set(rel, v);
    return v;
  }

  async list(name) { return (await this.raw(`${name}.json`))?.data ?? []; }
  /** A list that an older Atlas build may not have yet (authors, search-index: 15 Oct 2026). Missing = []. */
  async optList(name) {
    // A missing file is remembered for the current build (the cache is
    // emptied when a new build arrives), so it is not re-fetched per search.
    const rel = `${name}.json`;
    try {
      const v = await this.raw(rel);
      if (v == null) { this.cache.set(rel, { data: [] }); return []; }
      return v.data ?? [];
    } catch (e) {
      if (e?.code === 'ENOENT') { this.cache.set(rel, { data: [] }); return []; }
      throw e;
    }
  }
  async meta() {
    if (!this.isLocal()) { await this.syncBuild(); if (this.cache.has('meta.json')) return this.cache.get('meta.json'); }
    return this.raw('meta.json');
  }
  async one(kind, id) {
    if (!/^[A-Za-z0-9._-]+$/.test(id)) return null;   // no path tricks
    try { return (await this.raw(`${kind}/${id}.json`))?.data ?? null; }
    catch (e) { if (this.isLocal() && e.code === 'ENOENT') return null; throw e; }
  }
}

// ------------------------------------------------------------------ helpers
// British spellings fold into US ones on both sides (text and query), so
// "ageing" finds the 61 studies that say "aging" (before: 20). 15 Oct 2026.
const SPELL = [[/ageing/g, 'aging'], [/tumour/g, 'tumor'], [/signalling/g, 'signaling'], [/haem/g, 'hem'],
  [/behaviour/g, 'behavior'], [/oestr/g, 'estr'], [/ischaem/g, 'ischem'], [/oedema/g, 'edema']];
const norm = (s) => {
  let n = String(s ?? '').toLowerCase().normalize('NFKD')
    .replace(/[̀-ͯ]/g, '').replace(/α/g, 'alpha').replace(/β/g, 'beta');
  for (const [re, to] of SPELL) n = n.replace(re, to);
  return n;
};
// Latin species names in a query map to the words model_system uses
// ("Mus musculus" found nothing; model_system says "Mouse").
const LATIN = [['mus musculus', 'mouse'], ['rattus norvegicus', 'rat'], ['saccharomyces cerevisiae', 'yeast'],
  ['schizosaccharomyces pombe', 'yeast'], ['homo sapiens', 'human'], ['caenorhabditis elegans', 'elegans'],
  ['drosophila melanogaster', 'drosophila'], ['danio rerio', 'zebrafish']];
const tokens = (q) => {
  let n = norm(q);
  for (const [a, b] of LATIN) n = n.split(a).join(b);
  return n.split(/[^a-z0-9]+/).filter((t) => t.length > 1);
};
// A query word also matches its singular ("amino acids" found 22 studies,
// "amino acid" 45; substring matching only ever helped the singular).
const IRREGULAR = { mice: 'mouse', mouse: 'mice', analyses: 'analysis', children: 'child' };
function variants(t) {
  const v = [t];
  if (IRREGULAR[t]) v.push(IRREGULAR[t]);
  if (t.length > 4 && t.endsWith('ies')) v.push(t.slice(0, -3) + 'y');
  else if (t.length > 4 && /(ss|x|ch|sh)es$/.test(t)) v.push(t.slice(0, -2));
  else if (t.length > 3 && t.endsWith('s') && !/(ss|us|is)$/.test(t)) v.push(t.slice(0, -1));
  return v;
}

// Search indexes are built once per list. The list array itself is the key, so
// an index lives exactly as long as the cached build it was made from: a new
// build replaces the array and the old index is garbage-collected with it.
const memos = new WeakMap();
function memo(rows, key, build) {
  let m = memos.get(rows);
  if (!m) { m = new Map(); memos.set(rows, m); }
  if (!m.has(key)) m.set(key, build());
  return m.get(key);
}

/** Normalise the searchable fields of one record once: [text, weight, name]. Empty fields stay as null so positions are stable. */
const prepare = (fields) => fields.map(([text, w, name]) => {
  const n = norm(text);
  return n ? { n, words: new Set(n.split(/[^a-z0-9]+/)), w, name } : null;
});

/**
 * AND-of-tokens match with a field-weighted score: every token must hit some
 * field, a whole-word hit counts double a substring hit. `field` is the
 * weakest (last-listed) field that was needed to satisfy all tokens, so a
 * result that only matches in a description says so.
 */
function scoreIdx(ts, pf) {
  if (!ts.length) return { score: 1, field: null };
  let total = 0, weakest = -1;
  for (const t of ts) {
    let best = 0, at = -1;
    for (const v of variants(t)) {
      pf.forEach((f, i) => {
        if (!f) return;
        const s = f.words.has(v) ? 2 * f.w : f.n.includes(v) ? f.w : 0;
        if (s > best) { best = s; at = i; }
      });
    }
    if (!best) return { score: 0, field: null };
    total += best; weakest = Math.max(weakest, at);
  }
  return { score: total, field: pf[weakest]?.name ?? null };
}

export const CODE_ORDER = ['S', 'H', 'A', 'M', 'R', 'PP', 'RT'];

/**
 * Shorten long prose at a sentence boundary. Never cuts inside parentheses,
 * never at ";", never alters text that already fits. Keeps whole sentences up
 * to `max` characters (default 320); a first sentence longer than that is cut
 * at the last space outside parentheses.
 */
function clip(text, max = 320) {
  if (typeof text !== 'string' || text.length <= max) return { text, truncated: false };
  let depth = 0, lastEnd = -1, lastSpace = -1;
  for (let i = 0; i < max; i++) {
    const c = text[i];
    if (c === '(' || c === '[') depth++;
    else if (c === ')' || c === ']') depth = Math.max(0, depth - 1);
    else if (depth === 0) {
      if (c === ' ') lastSpace = i;
      if ('.!?'.includes(c) && /\s/.test(text[i + 1] ?? '') && /[A-Z0-9("']/.test(text.slice(i + 1).trimStart()[0] ?? '')) lastEnd = i;
    }
  }
  const out = lastEnd >= 20 ? text.slice(0, lastEnd + 1) : text.slice(0, Math.max(lastSpace, 1));
  return { text: `${out} ...`, truncated: true };
}

// ------------------------------------------------------------------ queries
/** One page of results, with the offset for the next page when there is one. */
function page(rows, offset = 0, limit = 20) {
  const results = rows.slice(offset, offset + limit);
  const next = offset + results.length;
  return { total_matches: rows.length, offset, results, next_offset: next < rows.length ? next : null };
}

/**
 * The study index. Until 1.3.1 it held only the summary record, so a study was
 * not found by its PMID or DOI, by a synonym of a linked entity ("sirolimus"),
 * by an entity that the title does not name (303 of 447 studies), by the full
 * name of a profiled author ("Claudio De Virgilio" vs "De Virgilio C") or by a
 * word from its abstract. search-index.json (Atlas API, 15 Oct 2026) carries
 * the missing links; without it the index falls back to the summary fields.
 */
async function studyIndex(atlas) {
  const all = await atlas.list('studies');
  const extra = await atlas.optList('search-index');
  const ents = extra.length ? await atlas.list('entities') : [];
  // keyed also by the search-index size: the same list with and without it are different indexes
  return memo(all, `search:${extra.length}`, () => {
    const bySid = new Map(extra.map((x) => [x.sid, x]));
    const eText = new Map(ents.map((e) => [e.id, [e.name, ...(e.synonyms ?? [])].join(' ')]));
    const ix = all.map((s) => {
      const x = bySid.get(s.sid) ?? {};
      return { s, pf: prepare([[s.title, 3, 'title'], [s.finding, 2, 'finding'], [s.sid, 3, 'sid'],
        [[s.pmid, s.pmcid, s.doi, s.registry_id].filter(Boolean).join(' '), 3, 'identifier'],
        [[s.authors, ...(x.author_names ?? [])].filter(Boolean).join('; '), 1, 'authors'],
        [s.journal, 1, 'journal'], [s.model_system, 1, 'model_system'], [s.category, 1, 'category'],
        [(x.entities ?? []).map((id) => eText.get(id)).filter(Boolean).join(' ; '), 1, 'linked_entity'],
        [x.text, 0.5, 'abstract']]) };
    });
    ix.full = extra.length > 0;
    return ix;
  });
}

/** A query that is a study identifier: PMID, DOI (bare, doi: or doi.org URL), PMCID, trial registry id. */
function idQuery(q) {
  const v = String(q ?? '').trim();
  let m;
  if ((m = v.match(/^(?:pmid:?\s*)?(\d{5,9})$/i))) return { field: 'pmid', value: m[1], label: 'PMID' };
  if ((m = v.match(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)?(10\.\d{4,9}\/\S+)$/i))) return { field: 'doi', value: m[1].toLowerCase(), label: 'DOI' };
  if (/^PMC\d+$/i.test(v)) return { field: 'pmcid', value: v.toUpperCase(), label: 'PMCID' };
  if (/^(NCT\d{8}|ISRCTN\d+)$/i.test(v)) return { field: 'registry_id', value: v.toUpperCase(), label: 'registry id' };
  return null;
}
const idOf = (s, field) => (field === 'doi' ? String(s.doi ?? '').toLowerCase() : String(s[field] ?? '').toUpperCase());

/** A study by Atlas ID, PMID, DOI, PMCID or registry id; null when the corpus does not hold it. */
export async function findStudy(atlas, q) {
  const all = await atlas.list('studies');
  const v = String(q ?? '').trim();
  const sid = all.find((s) => s.sid === v.toUpperCase());
  if (sid) return sid;
  const id = idQuery(v);
  return id ? all.find((s) => idOf(s, id.field) === id.value.toUpperCase() || idOf(s, id.field) === id.value) ?? null : null;
}

/**
 * Author-name forms of a query that names a person by given name and surname.
 * Study author lists use "Surname Initials" ("Sabatini DM"), so "David
 * Sabatini" is tried as "sabatini d". Several people can share that form.
 */
function nameForms(ts) {
  if (ts.length < 2 || ts.length > 5 || ts.some((t) => /\d/.test(t))) return [];
  const esc = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const out = [];
  for (let i = 1; i < ts.length; i++) {
    const sur = ts.slice(i).join(' ');
    out.push({ form: `${sur} ${ts[0][0]}`, re: new RegExp(`(^|[;,])\\s*${esc(sur)} ${ts[0][0]}[a-z]*(?=[\\s;,.]|$)`) });
  }
  return out;
}

const SEARCHED = 'title, finding, authors (as written in the paper\'s author list, e.g. "De Virgilio C", plus the full names of authors with a profile), '
  + 'PMID / DOI / PMCID / registry id, linked entities with their synonyms, journal, model system, category and the abstract excerpt';
const NOT_FOUND = 'Not found here means not in this curated corpus, not that the work does not exist. '
  + 'Before saying a person or paper is not in the Atlas, check search_authors / get_author for people and get_study with a PMID or DOI for papers.';

const entityIndex = (all) => memo(all, 'search', () => all.map((e) => ({
  e, nm: norm(e.name), syn: (e.synonyms ?? []).map(norm),
  // name, synonyms, description: in this order, so slice(0, 2) is "names only"
  pf: prepare([[e.name, 3, 'name'], [(e.synonyms ?? []).join(' '), 2, 'synonym'], [e.description, 1, 'description']]),
})));

export async function searchStudies(atlas, { query, evidence_code, entity, year_from, year_to, limit = 20, offset = 0 }) {
  const id = idQuery(query);
  if (id) {
    const hit = await findStudy(atlas, query);
    const out = page(hit ? [hit] : [], 0, 1);
    out.matched_as = id.label;
    if (!hit) out.note = `No study with ${id.label} ${id.value} in the Atlas. ${NOT_FOUND}`;
    return out;
  }
  const full = await studyIndex(atlas);
  let ix = full;
  if (evidence_code?.length) ix = ix.filter((x) => evidence_code.includes(x.s.evidence?.code));
  if (year_from) ix = ix.filter((x) => Number(x.s.year) >= year_from);
  if (year_to) ix = ix.filter((x) => Number(x.s.year) <= year_to);
  if (entity) {
    const e = await resolveEntity(atlas, entity);
    if (!e) return { note: `No entity matching "${entity}" in the Atlas.`, total_matches: 0, offset, results: [], next_offset: null };
    const full = await atlas.one('entities', e.id);
    const keep = new Set((full?.studies ?? []).map((s) => s.sid));
    ix = ix.filter((x) => keep.has(x.s.sid));
  }
  const ts = tokens(query);
  const scored = ix.map((x) => [scoreIdx(ts, x.pf).score, x.s])
    .filter(([sc]) => sc > 0)
    .sort((a, b) => b[0] - a[0] || Number(b[1].year ?? 0) - Number(a[1].year ?? 0));
  let out = page(scored.map(([, s]) => s), offset, limit);
  if (!out.total_matches && ts.length) {
    // "David Sabatini" -> author list form "Sabatini D…"
    for (const f of nameForms(ts)) {
      const hits = ix.filter((x) => f.re.test(norm(x.s.authors))).map((x) => x.s)
        .sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0));
      if (hits.length) {
        out = page(hits, offset, limit);
        out.matched_as = `author "${f.form}…"`;
        out.note = `Matched as an author in the author-list form "${f.form}…" (surname + first initial). `
          + 'Several people can share that form; search_authors / get_author tell them apart where the Atlas has a profile.';
        return out;
      }
    }
  }
  if (!out.total_matches) {
    out.note = `No study matched all the words. Searched: ${SEARCHED}. ${NOT_FOUND}`
      + (full.full ? '' : ' (search-index.json was not available, so linked entities, profiled author names and abstracts were not searched.)');
  }
  return out;
}

// ------------------------------------------------------------------ authors
/** Corpus author forms ("Panchaud N") -> study ids, from the author lists as the website builds them. */
const authorListIndex = (all) => memo(all, 'authorList', () => {
  const idx = new Map();
  for (const s of all) {
    for (const part of String(s.authors ?? '').split(';')) {
      const name = part.replace(/\s*et al\.?\s*$/i, '').trim();
      if (name) { if (!idx.has(name)) idx.set(name, []); idx.get(name).push(s.sid); }
    }
  }
  return idx;
});

/**
 * People. `results` are authors with a profile page (full name, corpus form,
 * ORCID, lab, their studies); `in_author_lists` are names that appear in study
 * author lists without a profile.
 */
export async function searchAuthors(atlas, { query, limit = 20, offset = 0 }) {
  const au = await atlas.optList('authors');
  const ts = tokens(query);
  const forms = nameForms(ts);
  const ix = memo(au, 'search', () => au.map((a) => ({ a, nc: norm(a.corpus_name),
    pf: prepare([[a.name, 3, 'name'], [a.corpus_name, 3, 'corpus_name'], [a.orcid, 3, 'orcid'], [a.lab, 1, 'lab'], [a.role, 0.5, 'role']]) })));
  const scored = [];
  for (const x of ix) {
    const r = scoreIdx(ts, x.pf);
    if (r.score > 0) scored.push([r.score, r.field, x.a]);
    else if (forms.some((f) => f.re.test(x.nc))) scored.push([1, 'corpus_name', x.a]);
  }
  scored.sort((a, b) => b[0] - a[0] || b[2].studies.length - a[2].studies.length);
  const out = page(scored.map(([, field, a]) => ({ ...a, study_count: a.studies.length, match_field: field })), offset, limit);
  const profiled = new Set(au.map((a) => a.corpus_name));
  const loose = [];
  for (const [name, sids] of authorListIndex(await atlas.list('studies'))) {
    if (profiled.has(name)) continue;
    const n = norm(name);
    if (scoreIdx(ts, prepare([[name, 1, 'n']])).score > 0 || forms.some((f) => f.re.test(n))) loose.push({ corpus_name: name, studies: sids });
  }
  loose.sort((a, b) => b.studies.length - a.studies.length);
  out.in_author_lists = loose.slice(0, 20);
  if (loose.length > 20) out.in_author_lists_total = loose.length;
  out.note = 'results = people with a profile page. in_author_lists = the same words in study author lists (form "Surname Initials") '
    + 'without a profile; one such form can stand for several people. Some author lists are shortened to first and last author ("et al."), '
    + 'so a middle author may be missing.' + (au.length ? '' : ' authors.json was not available, so no profiles were searched.');
  return out;
}

/** One profiled author by id, full name, corpus form or ORCID, with study cards. */
export async function getAuthor(atlas, q) {
  const au = await atlas.optList('authors');
  const n = norm(q).trim();
  let a = au.find((x) => x.id === q || x.orcid === q || norm(x.name) === n || norm(x.corpus_name) === n);
  if (!a) {
    const r = await searchAuthors(atlas, { query: q, limit: 2 });
    if (r.total_matches === 1) a = r.results[0];
  }
  if (!a) return null;
  return { ...a, study_count: a.studies.length, study_cards: await studyCards(atlas, a.studies) };
}

export async function resolveEntity(atlas, q) {
  const ix = entityIndex(await atlas.list('entities'));
  const n = norm(q);
  const exact = ix.find((x) => x.e.id === q) || ix.find((x) => x.nm === n) || ix.find((x) => x.syn.includes(n));
  if (exact) return exact.e;
  const ts = tokens(q);
  return ix.map((x) => [scoreIdx(ts, x.pf.slice(0, 2)).score, x.e])
    .filter(([s]) => s > 0).sort((a, b) => b[0] - a[0])[0]?.[1] || null;
}

/**
 * `match: "any"` (default) also searches descriptions, so a hit can be a
 * passing mention; every result says where it matched (`match_field`).
 * `match: "name"` keeps only names and synonyms.
 */
export async function searchEntities(atlas, { query, type, match = 'any', limit = 20, offset = 0 }) {
  const ix = entityIndex(await atlas.list('entities'));
  const ts = tokens(query);
  const depth = match === 'name' ? 2 : 3;
  const scored = [];
  for (const x of ix) {
    if (type && norm(x.e.type) !== norm(type)) continue;
    const r = scoreIdx(ts, x.pf.slice(0, depth));
    if (r.score > 0) scored.push([r, x.e]);
  }
  scored.sort((a, b) => b[0].score - a[0].score || b[1].study_count - a[1].study_count);
  const out = page(scored.map(([r, e]) => ({ ...e, match_field: r.field })), offset, limit);
  if (out.results.some((e) => e.match_field === 'description')) {
    out.note = 'match_field "description" means the term only appears in the description, not in the name or a synonym. Pass match="name" to keep names and synonyms only.';
  }
  return out;
}

function touches(r, id, name) {
  return [r.source, r.target].some((x) => (id && x.entity === id) || norm(x.name) === norm(name));
}

/** All relations matching the filters, unpaged. */
async function selectRelations(atlas, { entity, source, target, effect, contested_only, strongest_at_least }) {
  let rows = await atlas.list('relations');
  const pick = async (q) => { const e = await resolveEntity(atlas, q); return { id: e?.id ?? null, name: e?.name ?? q }; };
  if (entity) { const e = await pick(entity); rows = rows.filter((r) => touches(r, e.id, e.name)); }
  if (source) { const e = await pick(source); rows = rows.filter((r) => r.source.entity === e.id || norm(r.source.name) === norm(e.name)); }
  if (target) { const e = await pick(target); rows = rows.filter((r) => r.target.entity === e.id || norm(r.target.name) === norm(e.name)); }
  if (effect) rows = rows.filter((r) => r.effect === effect);
  if (contested_only) rows = rows.filter((r) => r.contested || r.curation_contested || r.consensus_contested || r.evidence.conflicting.length);
  if (strongest_at_least) {
    const lim = CODE_ORDER.indexOf(strongest_at_least);
    rows = rows.filter((r) => { const c = CODE_ORDER.indexOf(r.evidence.strongest?.code); return c >= 0 && c <= lim; });
  }
  return rows;
}

export async function findRelations(atlas, opts) {
  const { limit = 20, offset = 0 } = opts;
  return page(await selectRelations(atlas, opts), offset, limit);
}

async function studyCards(atlas, sids) {
  const all = await atlas.list('studies');
  const bySid = memo(all, 'bySid', () => new Map(all.map((s) => [s.sid, s])));
  return sids.map((sid) => bySid.get(sid)).filter(Boolean).map((s) => ({
    sid: s.sid, title: s.title, year: s.year, journal: s.journal, evidence: s.evidence,
    model_system: s.model_system, finding: s.finding, doi: s.doi, pmid: s.pmid, url: s.url,
  }));
}

/**
 * Within one answer, a study that shows up again (as support for one claim and
 * evidence against another, say) is sent in full once; later appearances keep
 * the sid, title, evidence code with its label and the url, and say where the
 * full card is.
 */
function dedupeCards(entries, listKeys, labelOf) {
  const first = new Map();
  for (const e of entries) {
    for (const k of listKeys) {
      e[k] = e[k].map((c) => {
        if (!first.has(c.sid)) { first.set(c.sid, labelOf(e)); return c; }
        return { sid: c.sid, title: c.title, year: c.year, evidence: c.evidence, url: c.url, full_card_in: first.get(c.sid) };
      });
    }
  }
}

export async function evidenceBetween(atlas, { a, b, dedupe = true }) {
  const ea = await resolveEntity(atlas, a), eb = await resolveEntity(atlas, b);
  const rows = await atlas.list('relations');
  const hit = (x, e, q) => (e && x.entity === e.id) || norm(x.name) === norm(e?.name ?? q);
  const direct = rows.filter((r) => (hit(r.source, ea, a) && hit(r.target, eb, b)) || (hit(r.source, eb, b) && hit(r.target, ea, a)));
  const out = [];
  for (const r of direct) {
    out.push({ relation: r,
      supporting_studies: await studyCards(atlas, r.evidence.supporting),
      conflicting_studies: await studyCards(atlas, r.evidence.conflicting) });
  }
  if (dedupe) dedupeCards(out, ['supporting_studies', 'conflicting_studies'], (e) => e.relation.id);
  return {
    resolved: { a: ea?.name ?? null, b: eb?.name ?? null },
    direct_relations: out,
    note: out.length ? undefined
      : 'The Atlas has no direct curated edge between these two. That is a statement about this curated corpus, not about the literature; check find_relations on each entity for indirect routes.',
  };
}

/** Other relation ids named in a relation's note or boundary text ("See LEU-LARS"), if they exist in the Atlas. Being named there does not mean the other relation holds the missing evidence. */
function mentionedRelations(r, byId) {
  const text = `${r.note ?? ''} ${r.boundary ?? ''}`;
  const seen = new Set();
  for (const m of text.match(/\b[A-Z0-9]+(?:-[A-Z0-9]+)+\b/g) ?? []) {
    if (m !== r.id && byId.has(m)) seen.add(m);
  }
  return [...seen].map((id) => ({ id, claim: byId.get(id).claim, contested: !!byId.get(id).contested }));
}

/**
 * Relations that are flagged contested or carry conflicting studies.
 * `breakdown` says how the total splits, so it can be compared with the
 * Atlas's own contested count. `only_contested` keeps just the flagged ones.
 */
export async function findContradictions(atlas, { entity, limit = 20, offset = 0, only_contested = false, brief = false, dedupe = true }) {
  const flagged = await selectRelations(atlas, { entity, contested_only: true });
  const curated = (r) => !!(r.curation_contested || r.consensus_contested);
  const breakdown = {
    flagged_contested: flagged.filter((r) => r.contested).length,
    flagged_curation_or_consensus_only: flagged.filter((r) => !r.contested && curated(r)).length,
    conflicting_studies_only: flagged.filter((r) => !r.contested && !curated(r)).length,
  };
  const p = page(only_contested ? flagged.filter((r) => r.contested || curated(r)) : flagged, offset, limit);
  const all = await atlas.list('relations');
  const byId = memo(all, 'byId', () => new Map(all.map((r) => [r.id, r])));
  const out = [];
  for (const r of p.results) {
    const conflicting = await studyCards(atlas, r.evidence.conflicting);
    const boundary = brief ? clip(r.boundary) : { text: r.boundary, truncated: false };
    const note = brief ? clip(r.note) : { text: r.note, truncated: false };
    const item = {
      id: r.id, claim: r.claim,
      status: r.contested ? 'contested' : curated(r) ? 'flagged-in-curation' : 'conflicting-studies-only',
      contested: r.contested, consensus: r.confidence?.consensus,
      boundary: boundary.text, note: note.text,
      supporting_studies: await studyCards(atlas, r.evidence.supporting),
      conflicting_studies: conflicting,
    };
    if (r.curation_contested !== undefined) item.curation_contested = !!r.curation_contested;
    if (r.consensus_contested !== undefined) item.consensus_contested = !!r.consensus_contested;
    if (boundary.truncated || note.truncated) item.text_truncated = true;
    if ((r.contested || curated(r)) && !conflicting.length) {
      item.conflicting_studies_missing = true;
      item.data_note = 'Flagged as contested, but the Atlas lists no conflicting study on this relation, so the other side is not in the structured data. '
        + 'Other relations named in its note or boundary are listed in named_in_text; being named there does not mean they hold the missing evidence.';
    }
    const named = mentionedRelations(r, byId);
    if (named.length) item.named_in_text = named;
    out.push(item);
  }
  if (dedupe) dedupeCards(out, ['supporting_studies', 'conflicting_studies'], (e) => e.id);
  const res = { total: p.total_matches, returned: out.length, offset: p.offset, next_offset: p.next_offset, breakdown, results: out };
  if (brief && out.some((x) => x.text_truncated)) res.note = 'boundary and note are shortened (text_truncated). Use get_relation for the full text, or pass brief=false.';
  return res;
}

/**
 * Atlas metadata. When the Atlas does not report contested_or_conflicting_relations itself, three counts are computed here from relations.json. The
 * Atlas's own `counts.contested_relations` counts the relations it flags;
 * find_contradictions also returns relations that only carry conflicting
 * studies, so its total is larger.
 */
export async function atlasAbout(atlas) {
  const meta = await atlas.meta();
  if (!meta) return meta;
  try {
    // Newer Atlas builds report these counts themselves; do not repeat them.
    if (meta.counts?.contested_or_conflicting_relations !== undefined) return meta;
    const rels = await atlas.list('relations');
    const withConflict = (r) => (r.evidence?.conflicting?.length ?? 0) > 0;
    return { ...meta, derived_counts: {
      relations_marked_contested: rels.filter((r) => r.contested).length,
      relations_with_conflicting_studies: rels.filter(withConflict).length,
      relations_contested_or_conflicting: rels.filter((r) => r.contested || withConflict(r)).length,
      note: 'Computed by this server from relations.json. counts.contested_relations is the Atlas\'s own figure; find_contradictions covers relations_contested_or_conflicting.',
    } };
  } catch {
    return meta;
  }
}

/**
 * One entity, compact: its own fields, the first `studies_limit` linked studies
 * as short cards, and every relation as a one-line claim. The full API record of
 * a hub such as mTORC1 is ~160 kB, too big for one tool answer.
 */
export async function getEntity(atlas, q, { studies_limit = 25 } = {}) {
  const e = await resolveEntity(atlas, q);
  if (!e) return null;
  const full = await atlas.one('entities', e.id);
  if (!full) return null;
  const { studies = [], relations = [], ...own } = full;
  return {
    ...own,
    studies: studies.slice(0, studies_limit).map((s) => ({
      sid: s.sid, title: s.title, year: s.year, evidence_code: s.evidence?.code, url: s.url })),
    studies_shown: Math.min(studies.length, studies_limit),
    relations: relations.map((r) => ({
      id: r.id, claim: r.claim, effect: r.effect, contested: r.contested,
      strongest_evidence: r.evidence?.strongest?.code ?? null })),
    note: studies.length > studies_limit
      ? `Showing ${studies_limit} of ${studies.length} studies. Use search_studies with entity="${own.name}" (and offset) for the rest, get_study or get_relation for details.`
      : 'Use get_study or get_relation for full records.',
  };
}

/** Paged. `brief` (default) shortens `still_open`; get_question has the full text. */
export async function listQuestions(atlas, { kind, query, brief = true, limit = 20, offset = 0 }) {
  let rows = await atlas.list('questions');
  if (kind) rows = rows.filter((q) => q.kind === kind);
  if (query) {
    const ts = tokens(query);
    const ix = memo(rows, 'search', () => rows.map((q) => ({ q, pf: prepare([[q.id, 3, 'id'], [q.title, 3, 'title'],
      [q.category, 1, 'category'], [q.evidence_stands_at, 1, 'evidence_stands_at'],
      [[q.gap, q.still_open, q.hypothesis, q.changed_since_written, q.how_to_test].filter(Boolean).join(' '), 1, 'text']]) })));
    rows = ix.map((x) => [scoreIdx(ts, x.pf).score, x.q]).filter(([sc]) => sc > 0).sort((a, b) => b[0] - a[0]).map(([, q]) => q);
  }
  const out = page(rows, offset, limit);
  out.results = out.results.map((q) => {
    const open = brief ? clip(q.still_open) : { text: q.still_open, truncated: false };
    return { id: q.id, kind: q.kind, title: q.title, category: q.category,
      evidence_stands_at: q.evidence_stands_at, still_open: open.text,
      ...(open.truncated ? { still_open_truncated: true } : {}), url: q.url };
  });
  if (out.results.some((q) => q.still_open_truncated)) out.note = 'still_open is shortened (still_open_truncated). Use get_question for the full text, or pass brief=false.';
  return out;
}
