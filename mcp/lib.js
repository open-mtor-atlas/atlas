// Data access and queries for the mTOR Atlas MCP server.
//
// Everything here reads the Atlas's public, static JSON API
// (https://mtor-atlas.org/api/v1/). There is no Atlas-side search endpoint:
// the lists are small, so they are downloaded once, cached, and filtered here.
// Nothing is invented or inferred: every returned object is an API record or a
// subset of one, and every study carries its evidence code WITH its label and
// the note that the code describes the kind of study, not its quality.
import { readFile } from 'node:fs/promises';
import path from 'node:path';

export const DEFAULT_BASE = 'https://mtor-atlas.org/api/v1';
const TTL_MS = 60 * 60 * 1000;

export class Atlas {
  constructor(base = process.env.ATLAS_API_BASE || DEFAULT_BASE) {
    this.base = base.replace(/\/+$/, '');
    this.cache = new Map();
  }

  isLocal() { return !/^https?:\/\//i.test(this.base); }

  async raw(rel) {
    const hit = this.cache.get(rel);
    if (hit && Date.now() - hit.t < TTL_MS) return hit.v;
    let v;
    if (this.isLocal()) {
      const root = this.base.replace(/^file:\/\//, '');
      v = JSON.parse(await readFile(path.join(root, rel), 'utf-8'));
    } else {
      const res = await fetch(`${this.base}/${rel}`, { headers: { accept: 'application/json' } });
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`Atlas API ${res.status} for ${rel}`);
      v = await res.json();
    }
    this.cache.set(rel, { t: Date.now(), v });
    return v;
  }

  async list(name) { return (await this.raw(`${name}.json`))?.data ?? []; }
  async meta() { return this.raw('meta.json'); }
  async one(kind, id) {
    if (!/^[A-Za-z0-9._-]+$/.test(id)) return null;   // no path tricks
    try { return (await this.raw(`${kind}/${id}.json`))?.data ?? null; }
    catch (e) { if (this.isLocal() && e.code === 'ENOENT') return null; throw e; }
  }
}

// ------------------------------------------------------------------ helpers
const norm = (s) => String(s ?? '').toLowerCase().normalize('NFKD')
  .replace(/[̀-ͯ]/g, '').replace(/α/g, 'alpha').replace(/β/g, 'beta');
const tokens = (q) => norm(q).split(/[^a-z0-9]+/).filter((t) => t.length > 1);

/** Simple AND-of-tokens match with a field-weighted score. */
function score(q, fields) {
  const ts = tokens(q);
  if (!ts.length) return 1;
  let total = 0;
  for (const t of ts) {
    let best = 0;
    for (const [text, w] of fields) {
      const n = norm(text);
      if (!n) continue;
      if (new RegExp(`(^|[^a-z0-9])${t}([^a-z0-9]|$)`).test(n)) best = Math.max(best, 2 * w);
      else if (n.includes(t)) best = Math.max(best, w);
    }
    if (!best) return 0;
    total += best;
  }
  return total;
}

export const CODE_ORDER = ['S', 'H', 'A', 'M', 'R', 'PP', 'RT'];

// ------------------------------------------------------------------ queries
export async function searchStudies(atlas, { query, evidence_code, entity, year_from, year_to, limit = 20 }) {
  let rows = await atlas.list('studies');
  if (evidence_code?.length) rows = rows.filter((s) => evidence_code.includes(s.evidence?.code));
  if (year_from) rows = rows.filter((s) => Number(s.year) >= year_from);
  if (year_to) rows = rows.filter((s) => Number(s.year) <= year_to);
  if (entity) {
    const e = await resolveEntity(atlas, entity);
    if (!e) return { note: `No entity matching "${entity}" in the Atlas.`, results: [] };
    const full = await atlas.one('entities', e.id);
    const keep = new Set((full?.studies ?? []).map((s) => s.sid));
    rows = rows.filter((s) => keep.has(s.sid));
  }
  const scored = rows.map((s) => [score(query, [[s.title, 3], [s.finding, 2], [s.sid, 3],
    [s.authors, 1], [s.journal, 1], [s.model_system, 1], [s.category, 1]]), s])
    .filter(([sc]) => sc > 0)
    .sort((a, b) => b[0] - a[0] || Number(b[1].year ?? 0) - Number(a[1].year ?? 0));
  return { total_matches: scored.length, results: scored.slice(0, limit).map(([, s]) => s) };
}

export async function resolveEntity(atlas, q) {
  const all = await atlas.list('entities');
  const n = norm(q);
  return all.find((e) => e.id === q) ||
    all.find((e) => norm(e.name) === n) ||
    all.find((e) => (e.synonyms ?? []).some((s) => norm(s) === n)) ||
    all.map((e) => [score(q, [[e.name, 3], [(e.synonyms ?? []).join(' '), 2]]), e])
      .filter(([s]) => s > 0).sort((a, b) => b[0] - a[0])[0]?.[1] || null;
}

export async function searchEntities(atlas, { query, type, limit = 20 }) {
  let rows = await atlas.list('entities');
  if (type) rows = rows.filter((e) => norm(e.type) === norm(type));
  const scored = rows.map((e) => [score(query, [[e.name, 3], [(e.synonyms ?? []).join(' '), 2], [e.description, 1]]), e])
    .filter(([s]) => s > 0).sort((a, b) => b[0] - a[0] || b[1].study_count - a[1].study_count);
  return { total_matches: scored.length, results: scored.slice(0, limit).map(([, e]) => e) };
}

function touches(r, id, name) {
  return [r.source, r.target].some((x) => (id && x.entity === id) || norm(x.name) === norm(name));
}

export async function findRelations(atlas, { entity, source, target, effect, contested_only, strongest_at_least, limit = 50 }) {
  let rows = await atlas.list('relations');
  const pick = async (q) => { const e = await resolveEntity(atlas, q); return { id: e?.id ?? null, name: e?.name ?? q }; };
  if (entity) { const e = await pick(entity); rows = rows.filter((r) => touches(r, e.id, e.name)); }
  if (source) { const e = await pick(source); rows = rows.filter((r) => r.source.entity === e.id || norm(r.source.name) === norm(e.name)); }
  if (target) { const e = await pick(target); rows = rows.filter((r) => r.target.entity === e.id || norm(r.target.name) === norm(e.name)); }
  if (effect) rows = rows.filter((r) => r.effect === effect);
  if (contested_only) rows = rows.filter((r) => r.contested || r.evidence.conflicting.length);
  if (strongest_at_least) {
    const lim = CODE_ORDER.indexOf(strongest_at_least);
    rows = rows.filter((r) => { const c = CODE_ORDER.indexOf(r.evidence.strongest?.code); return c >= 0 && c <= lim; });
  }
  return { total_matches: rows.length, results: rows.slice(0, limit) };
}

async function studyCards(atlas, sids) {
  const all = new Map((await atlas.list('studies')).map((s) => [s.sid, s]));
  return sids.map((sid) => all.get(sid)).filter(Boolean).map((s) => ({
    sid: s.sid, title: s.title, year: s.year, journal: s.journal, evidence: s.evidence,
    model_system: s.model_system, finding: s.finding, doi: s.doi, pmid: s.pmid, url: s.url,
  }));
}

export async function evidenceBetween(atlas, { a, b }) {
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
  return {
    resolved: { a: ea?.name ?? null, b: eb?.name ?? null },
    direct_relations: out,
    note: out.length ? undefined
      : 'The Atlas has no direct curated edge between these two. That is a statement about this curated corpus, not about the literature; check find_relations on each entity for indirect routes.',
  };
}

export async function findContradictions(atlas, { entity, limit = 50 }) {
  const { results } = await findRelations(atlas, { entity, contested_only: true, limit });
  const out = [];
  for (const r of results) {
    out.push({ id: r.id, claim: r.claim, contested: r.contested, consensus: r.confidence.consensus,
      boundary: r.boundary, note: r.note,
      supporting_studies: await studyCards(atlas, r.evidence.supporting),
      conflicting_studies: await studyCards(atlas, r.evidence.conflicting) });
  }
  return { total: out.length, results: out };
}

export async function listQuestions(atlas, { kind }) {
  let rows = await atlas.list('questions');
  if (kind) rows = rows.filter((q) => q.kind === kind);
  return rows.map((q) => ({ id: q.id, kind: q.kind, title: q.title, category: q.category,
    evidence_stands_at: q.evidence_stands_at, still_open: q.still_open, url: q.url }));
}
