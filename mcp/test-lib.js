// Offline test of the query layer (lib.js) and the tool definitions (tools.js).
// No network: fetch is replaced by a small SYNTHETIC Atlas (ids such as TST001
// and the text of the claims are made up for this test and say nothing about
// mTOR biology). Run: node test-lib.js
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { Atlas, searchStudies, searchEntities, resolveEntity, findContradictions, listQuestions, atlasAbout, evidenceBetween, searchAuthors, getAuthor, findStudy } from './lib.js';
import { createServer } from './tools.js';

// ------------------------------------------------------------- synthetic data
const BUILD = { api_version: '1.0.0', source_commit: 'test0001', corpus_snapshot: '2026-10-12T22:59:14+0200' };
const EV = { code: 'M', label: 'Molecular - cells, biochemistry, structure', note: 'this describes the kind of study, not its quality' };
const study = (n, over = {}) => ({ sid: `TST${String(n).padStart(3, '0')}`, title: `Test study ${n} on leucine sensing`, year: 2000 + n,
  journal: 'Test Journal', authors: `Tester ${n}`, evidence: EV, model_system: 'Cells', category: 'Test',
  finding: `Synthetic finding ${n}.`, doi: `10.0000/test.${n}`, pmid: String(9000000 + n), url: `https://example.test/study/TST${String(n).padStart(3, '0')}/`, ...over });
const studies = [1, 2, 3, 4, 5, 6].map((n) => study(n));
studies.push(study(7, { title: 'Rapamycin lifespan in mice', finding: 'Synthetic finding about lifespan.', evidence: { ...EV, code: 'A' } }));

const entity = (id, name, over = {}) => ({ id, name, type: 'Gene/Protein', synonyms: [], description: `Synthetic entity ${name}.`, study_count: 1, relation_count: 1, ...over });
const entities = [
  entity('raptor', 'Raptor', { synonyms: ['raptor', 'RPTOR', 'KOG1'], study_count: 19 }),
  entity('energy-cellular-stress', 'Energy & cellular stress', { type: 'Condition', description: 'Falling ATP. Acts partly through raptor and through AMPK.' }),
  entity('rheb', 'Rheb', { synonyms: ['RHEB1'] }),
  entity('mtorc1', 'mTORC1', { description: 'Synthetic complex.' }),
];

const LONG = 'The gap is real and narrow. It concerns one comparison that nobody has run. ' + 'More detail follows here and it goes on for a while. '.repeat(12);
const questions = [
  { id: 'H1', kind: 'open-question', title: 'Q one', category: 'c', evidence_stands_at: 'Mechanism in cells', still_open: LONG, url: 'https://example.test/q/H1/' },
  { id: 'H2', kind: 'open-question', title: 'Q two', category: 'c', evidence_stands_at: 'Lifespan in mice', still_open: 'Short text.', url: 'https://example.test/q/H2/' },
  { id: 'F1', kind: 'frontier', title: 'Q three', category: 'c', evidence_stands_at: 'Mechanism in cells', still_open: LONG, url: 'https://example.test/q/F1/' },
];

const rel = (id, over = {}) => ({ id, claim: `Claim ${id}`, effect: 'activates', contested: false,
  source: { entity: 'rheb', name: 'Rheb' }, target: { entity: 'mtorc1', name: 'mTORC1' },
  confidence: { consensus: 'emerging' }, boundary: 'Short boundary.', note: '',
  evidence: { supporting: ['TST001'], conflicting: [], strongest: { code: 'M' } }, ...over });
const BOUNDARY = 'Scope: synthetic. ' + 'This boundary text is long on purpose so that the brief mode has something to cut. '.repeat(8);
const relations = [
  rel('LEU-LARS', { contested: true, note: 'CONTESTED with LEU-SESN2. Synthetic.', evidence: { supporting: ['TST001'], conflicting: [], strongest: { code: 'M' } } }),
  rel('LARS-RAG', { contested: true, boundary: BOUNDARY, note: 'See LEU-LARS.', evidence: { supporting: ['TST001'], conflicting: [], strongest: { code: 'M' } } }),
  rel('LEU-SESN2', { contested: true, note: 'See LEU-LARS.', evidence: { supporting: ['TST002'], conflicting: [], strongest: { code: 'M' } } }),
  rel('AMPK-ULK1', { contested: true, evidence: { supporting: ['TST003', 'TST004'], conflicting: ['TST005'], strongest: { code: 'M' } } }),
  rel('4EBP1-MITO', { contested: false, evidence: { supporting: ['TST006'], conflicting: ['TST001'], strongest: { code: 'M' } } }),
  rel('RHEB-MTORC1'),
];
const META = { ...BUILD, name: "Test Atlas", dataset_version: '0.0.0', counts: { studies: studies.length, relations: relations.length, contested_relations: 4 } };

// ----------------------------------------------------------------- fake fetch
let site;                                  // { meta, studies, entities, relations, questions }
let fetches;
globalThis.fetch = async (url) => {
  const rel_ = new URL(url).pathname.replace('/api/v1/', '');
  fetches.push(rel_);
  const wrap = (data) => ({ status: 200, ok: true, json: async () => ({ meta: site.meta, data }) });
  if (rel_ === 'meta.json') return { status: 200, ok: true, json: async () => ({ ...site.meta }) };
  if (['studies.json', 'entities.json', 'relations.json', 'questions.json'].includes(rel_)) return wrap(site[rel_.replace('.json', '')]);
  if (['authors.json', 'search-index.json'].includes(rel_) && site[rel_]) return wrap(site[rel_]);
  const m = rel_.match(/^(entities|relations|questions)\/(.+)\.json$/);
  const hit = m && site[m[1]].find((x) => x.id === m[2]);
  if (hit) return wrap(m[1] === 'entities' ? { ...hit, studies: studies.slice(0, 3), relations: [] } : hit);
  return { status: 404, ok: false, json: async () => null };
};
const fresh = () => { site = { meta: { ...META }, studies, entities, relations, questions }; fetches = []; return new Atlas('https://x.test/api/v1'); };

let fail = 0;
const check = (name, cond, extra) => { console.log((cond ? 'ok   ' : 'FAIL ') + name + (!cond && extra !== undefined ? '  ' + JSON.stringify(extra).slice(0, 200) : '')); if (!cond) fail++; };

// ------------------------------------- 1. counts agree with each other (point 1)
let at = fresh();
const about = await atlasAbout(at);
check('atlas_about keeps the Atlas own fields', about.counts.contested_relations === 4 && about.dataset_version === '0.0.0');
check('derived_counts: flagged / conflicting / either', about.derived_counts.relations_marked_contested === 4
  && about.derived_counts.relations_with_conflicting_studies === 2 && about.derived_counts.relations_contested_or_conflicting === 5, about.derived_counts);
const all = await findContradictions(at, {});
check('find_contradictions total equals derived "either"', all.total === about.derived_counts.relations_contested_or_conflicting && all.breakdown.flagged_contested === 4 && all.breakdown.conflicting_studies_only === 1, all.breakdown);
check('each result has a status', all.results.every((r) => r.status === (r.contested ? 'contested' : 'conflicting-studies-only')));
const only = await findContradictions(at, { only_contested: true });
check('only_contested drops conflicting-studies-only', only.total === 4 && only.results.every((r) => r.contested));

// ------------------------- 2. contested without a counterpart is visible (point 2)
const leu = all.results.find((r) => r.id === 'LEU-LARS');
check('LEU-LARS flagged conflicting_studies_missing', leu.conflicting_studies_missing === true && /no conflicting study/.test(leu.data_note), leu);
check('LEU-LARS names LEU-SESN2 as a mentioned relation', leu.named_in_text?.map((x) => x.id).join() === 'LEU-SESN2', leu.named_in_text);
check('no self-mention, no mention when there is none', !all.results.find((r) => r.id === 'AMPK-ULK1').named_in_text);
check('AMPK-ULK1 has both sides and no missing flag', !all.results.find((r) => r.id === 'AMPK-ULK1').conflicting_studies_missing);

// -------------------------------------------- 3. entity search noise (point 3)
const rap = await searchEntities(at, { query: 'raptor' });
check('raptor ranks first, match_field name', rap.results[0].id === 'raptor' && rap.results[0].match_field === 'name', rap.results.map((r) => [r.id, r.match_field]));
const noise = rap.results.find((r) => r.id === 'energy-cellular-stress');
check('description-only hit is labelled, with a note', noise?.match_field === 'description' && /description/.test(rap.note ?? ''), noise);
const rapName = await searchEntities(at, { query: 'raptor', match: 'name' });
check('match="name" removes the description-only hit', rapName.total_matches === 1 && rapName.results[0].id === 'raptor' && !rapName.note);
const syn = await searchEntities(at, { query: 'KOG1' });
check('synonym hit is found and labelled', syn.results[0].id === 'raptor' && syn.results[0].match_field === 'synonym', syn.results[0]);
check('type filter still works', (await searchEntities(at, { query: 'raptor', type: 'Condition' })).results.map((r) => r.id).join() === 'energy-cellular-stress');
check('resolveEntity: id, name, synonym, fuzzy', (await Promise.all([resolveEntity(at, 'raptor'), resolveEntity(at, 'RPTOR'), resolveEntity(at, 'mtorc1'), resolveEntity(at, 'cellular stress')])).map((e) => e?.id).join() === 'raptor,raptor,mtorc1,energy-cellular-stress');

// ------------------------- ranking is the same as the old implementation (point 4)
const oldScore = (q, fields) => { // copied from lib.js before the index was introduced
  const nrm = (s) => String(s ?? '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/α/g, 'alpha').replace(/β/g, 'beta');
  const ts = nrm(q).split(/[^a-z0-9]+/).filter((t) => t.length > 1);
  if (!ts.length) return 1;
  let total = 0;
  for (const t of ts) {
    let best = 0;
    for (const [text, w] of fields) { const n = nrm(text); if (!n) continue;
      if (new RegExp(`(^|[^a-z0-9])${t}([^a-z0-9]|$)`).test(n)) best = Math.max(best, 2 * w); else if (n.includes(t)) best = Math.max(best, w); }
    if (!best) return 0;
    total += best;
  }
  return total;
};
let same = true;
for (const q of ['leucine', 'rapamycin lifespan', 'test study 3', 'tst004', 'synthetic', 'nothing here', '']) {
  const old = studies.map((s) => [oldScore(q, [[s.title, 3], [s.finding, 2], [s.sid, 3], [s.authors, 1], [s.journal, 1], [s.model_system, 1], [s.category, 1]]), s])
    .filter(([sc]) => sc > 0).sort((a, b) => b[0] - a[0] || Number(b[1].year ?? 0) - Number(a[1].year ?? 0)).map(([, s]) => s.sid);
  const now = (await searchStudies(at, { query: q, limit: 50 })).results.map((s) => s.sid);
  if (old.join() !== now.join()) { same = false; console.log('  differs for', JSON.stringify(q), old, now); }
}
check('searchStudies order identical to the previous scoring', same);
for (const q of ['raptor', 'stress', 'complex', 'rheb', 'ampk']) {
  const old = entities.map((e) => [oldScore(q, [[e.name, 3], [(e.synonyms ?? []).join(' '), 2], [e.description, 1]]), e])
    .filter(([s]) => s > 0).sort((a, b) => b[0] - a[0] || b[1].study_count - a[1].study_count).map(([, e]) => e.id);
  const now = (await searchEntities(at, { query: q })).results.map((e) => e.id);
  if (old.join() !== now.join()) { same = false; console.log('  entity differs for', q, old, now); }
}
check('searchEntities order identical to the previous scoring', same);
const before = fetches.length;
for (let i = 0; i < 20; i++) { await searchStudies(at, { query: 'leucine' }); await searchEntities(at, { query: 'raptor' }); }
check('repeat searches do not fetch again', fetches.length === before, fetches.slice(before));
// the index follows the build: a deploy with new data must not serve the old index
site = { ...site, meta: { ...META, source_commit: 'test0002', corpus_snapshot: '2026-10-13T08:00:00+0200' }, entities: [entity('newone', 'Newone')] };
at.metaAt = 0;
check('index is replaced when a new build arrives', (await searchEntities(at, { query: 'newone' })).results[0]?.id === 'newone' && (await searchEntities(at, { query: 'raptor' })).total_matches === 0);

// ------------------------------------------------ 5, 6. brief + paging (questions)
at = fresh();
const qs = await listQuestions(at, {});
check('list_questions is paged like the others', qs.total_matches === 3 && qs.offset === 0 && qs.next_offset === null && Array.isArray(qs.results), Object.keys(qs));
const q1 = qs.results.find((q) => q.id === 'H1');
check('brief (default) shortens long still_open at a sentence', q1.still_open_truncated === true && q1.still_open.length < 300 && q1.still_open.startsWith('The gap is real and narrow.') && /\.\s?(\.\.\.)?$/.test(q1.still_open), q1.still_open);
check('short text is left alone, no flag', qs.results.find((q) => q.id === 'H2').still_open === 'Short text.' && !('still_open_truncated' in qs.results.find((q) => q.id === 'H2')));
check('note points to get_question when shortened', /get_question/.test(qs.note));
const full = await listQuestions(at, { brief: false });
check('brief=false returns the full text', full.results[0].still_open === LONG && !full.note);
const p1 = await listQuestions(at, { limit: 2 }), p2 = await listQuestions(at, { limit: 2, offset: p1.next_offset });
check('limit / offset / next_offset', p1.results.length === 2 && p1.next_offset === 2 && p2.results.length === 1 && p2.next_offset === null && [...p1.results, ...p2.results].map((q) => q.id).join() === 'H1,H2,F1');
check('kind filter still works', (await listQuestions(at, { kind: 'frontier' })).results.map((q) => q.id).join() === 'F1');

// -------------------------------------- 7. contradictions can be paged to the end
const seen = [];
let off = 0, pages = 0, last;
do { last = await findContradictions(at, { limit: 2, offset: off }); seen.push(...last.results.map((r) => r.id)); off = last.next_offset; pages++; } while (off !== null && pages < 10);
check('paging reaches every contested relation exactly once', pages === 3 && new Set(seen).size === 5 && seen.length === 5 && last.next_offset === null, seen);
check('first page reports where the rest starts', (await findContradictions(at, { limit: 2 })).next_offset === 2);

// ------------------------------------------- 8. a study is not repeated in full
const dup = (r) => r.results.flatMap((x) => [...x.supporting_studies, ...x.conflicting_studies]).filter((c) => c.sid === 'TST001');
const d = await findContradictions(at, {});
const cards = dup(d);
check('TST001 appears several times but in full only once', cards.length === 3 && cards.filter((c) => c.finding).length === 1, cards.map((c) => [c.finding ? 'full' : 'stub', c.full_card_in]));
const stub = cards.find((c) => !c.finding);
check('a stub keeps sid, title, evidence code with its label, url and where the card is', stub.sid && stub.title && stub.evidence?.label && stub.evidence?.note && stub.url && stub.full_card_in === 'LEU-LARS', stub);
check('dedupe=false sends every card in full', dup(await findContradictions(at, { dedupe: false })).every((c) => c.finding));
const eb = await evidenceBetween(at, { a: 'Rheb', b: 'mTORC1' });
check('evidence_between dedupes too, and can be switched off', eb.direct_relations.length === 6
  && eb.direct_relations.flatMap((r) => r.supporting_studies).filter((c) => c.finding).length < eb.direct_relations.flatMap((r) => r.supporting_studies).length
  && (await evidenceBetween(at, { a: 'Rheb', b: 'mTORC1', dedupe: false })).direct_relations.flatMap((r) => r.supporting_studies).every((c) => c.finding));

// ---------------------------------- 5. brief for contradictions, boundary intact by default
const lr = (r) => r.results.find((x) => x.id === 'LARS-RAG');
check('boundary is complete by default', lr(await findContradictions(at, {})).boundary === BOUNDARY);
const bf = lr(await findContradictions(at, { brief: true }));
check('brief shortens boundary and says so', bf.boundary.length < 300 && bf.text_truncated === true && /get_relation/.test((await findContradictions(at, { brief: true })).note));

// ------------------- 9. search beyond the summary record (1.3.2, 15 Oct 2026)
at = fresh();
check('a missing search-index.json is fetched once per build', (await searchStudies(at, { query: 'leucine' }), await searchStudies(at, { query: 'leucine' }), fetches.filter((f) => f === 'search-index.json').length === 1), fetches);
check('PMID query returns exactly that study', (await searchStudies(at, { query: '9000003' })).results.map((s) => s.sid).join() === 'TST003');
check('DOI query (doi.org URL, any case) returns that study', (await searchStudies(at, { query: 'https://doi.org/10.0000/TEST.4' })).results.map((s) => s.sid).join() === 'TST004');
const miss = await searchStudies(at, { query: '9999999' });
check('unknown PMID: empty with a note', miss.total_matches === 0 && /No study with PMID 9999999/.test(miss.note), miss);
check('findStudy by sid, PMID, DOI', (await Promise.all(['tst002', '9000002', '10.0000/test.2'].map((q) => findStudy(at, q)))).every((s) => s?.sid === 'TST002'));
const nothing = await searchStudies(at, { query: 'qqqzzz' });
check('no match explains what was searched and that search-index was missing', /Searched:/.test(nothing.note) && /search-index\.json was not available/.test(nothing.note), nothing.note);
// a person named with given name first: author lists say "Tester 5"? no -- use a realistic form
site = { ...site, studies: [...studies, study(8, { authors: 'Panchaud N; De Virgilio C et al.' }), study(9, { authors: 'Sabatini DM; Kim DH' })] };
at = new Atlas('https://x.test/api/v1'); fetches = [];
const fb = await searchStudies(at, { query: 'David Sabatini' });
check('full name falls back to the author-list form "sabatini d"', fb.results.map((s) => s.sid).join() === 'TST009' && /sabatini d/.test(fb.matched_as), fb);
check('the fallback does not fire for unrelated words', (await searchStudies(at, { query: 'David Smith' })).total_matches === 0);
// with search-index.json and authors.json present
site = { ...site, entities: [...entities, entity('rapamycin', 'Rapamycin', { type: 'Drug', synonyms: ['Sirolimus'] })],
  'search-index.json': [{ sid: 'TST008', entities: ['rapamycin'], authors: ['claudio-de-virgilio'], author_names: ['Claudio De Virgilio'], text: 'We identified Iml1 with Npr2 and Npr3.' }],
  'authors.json': [{ id: 'claudio-de-virgilio', name: 'Claudio De Virgilio', corpus_name: 'De Virgilio C', orcid: '0000-0001-8826-4323', lab: 'University of Fribourg', lab_url: null, role: null, studies: ['TST008'], url: 'https://example.test/author/claudio-de-virgilio/' }] };
at = new Atlas('https://x.test/api/v1'); fetches = [];
check('full name of a profiled author finds the study', (await searchStudies(at, { query: 'Claudio De Virgilio' })).results.map((s) => s.sid).join() === 'TST008');
check('synonym of a linked entity finds the study', (await searchStudies(at, { query: 'sirolimus' })).results.map((s) => s.sid).includes('TST008'));
check('a word from the abstract finds the study', (await searchStudies(at, { query: 'Npr2' })).results.map((s) => s.sid).join() === 'TST008');
check('plural and British spelling fold', (await searchStudies(at, { query: 'leucines' })).total_matches === (await searchStudies(at, { query: 'leucine' })).total_matches);
const sa = await searchAuthors(at, { query: 'Fribourg' });
check('search_authors by lab', sa.results[0]?.id === 'claudio-de-virgilio' && sa.results[0].study_count === 1, sa);
check('search_authors lists author-list names without a profile', (await searchAuthors(at, { query: 'Panchaud' })).in_author_lists.map((x) => x.corpus_name).join() === 'Panchaud N');
check('get_author by corpus form and by ORCID', (await getAuthor(at, 'De Virgilio C'))?.study_cards?.[0]?.sid === 'TST008' && (await getAuthor(at, '0000-0001-8826-4323'))?.id === 'claudio-de-virgilio');
check('list_questions query filters and ranks', (await listQuestions(at, { query: 'Lifespan mice' })).results.map((q) => q.id).join() === 'H2');

// -------------------------------------- the tools themselves (schemas, defaults)
const [ct, st] = InMemoryTransport.createLinkedPair();
const server = createServer(fresh());
await server.connect(st);
const c = new Client({ name: 'lib-test', version: '0' });
await c.connect(ct);
const call = async (name, args) => { const r = await c.callTool({ name, arguments: args }); return { err: !!r.isError, j: (() => { try { return JSON.parse(r.content[0].text); } catch { return r.content[0].text; } })() }; };
const listed = Object.fromEntries((await c.listTools()).tools.map((t) => [t.name, t.inputSchema.properties ?? {}]));
check('schemas expose the new parameters', 'offset' in listed.list_questions && 'limit' in listed.list_questions && 'brief' in listed.list_questions
  && 'offset' in listed.find_contradictions && 'only_contested' in listed.find_contradictions && 'match' in listed.search_entities
  && 'offset' in listed.search_entities && 'dedupe' in listed.evidence_between);
check('tool: atlas_about carries derived_counts', (await call('atlas_about', {})).j.derived_counts?.relations_contested_or_conflicting === 5);
const tq = await call('list_questions', {});
check('tool: list_questions returns the page object with defaults', !tq.err && tq.j.total_matches === 3 && tq.j.results[0].still_open_truncated === true, tq.j);
const tc = await call('find_contradictions', { limit: 2 });
check('tool: find_contradictions pages', !tc.err && tc.j.returned === 2 && tc.j.next_offset === 2 && tc.j.breakdown.flagged_contested === 4, tc.j);
const te = await call('search_entities', { query: 'raptor' });
check('tool: search_entities labels matches', !te.err && te.j.results[0].match_field === 'name' && te.j.results.find((r) => r.id === 'energy-cellular-stress').match_field === 'description');
check('tool: unknown study is still an error', (await call('get_study', { sid: 'NOPE0000' })).err === true);
check('tool: search_authors and get_author are registered', 'query' in listed.search_authors && 'author' in listed.get_author && 'query' in listed.list_questions);
// Tolerant input (1.3.1): aliases, numbers sent as text, limits above the maximum.
check('get_study accepts study_id and id as aliases of sid', /TST001/i.test((await call('get_study', { study_id: 'tst001' })).j) && /TST002/.test((await call('get_study', { id: 'TST002' })).j)); // the synthetic Atlas has no study files: the id reaching the lookup is the proof
check('get_study without any id is a clear error', (await call('get_study', {})).err === true);
check('get_entity accepts id as alias of entity', (await call('get_entity', { id: 'raptor' })).err === false);
const tl = await call('list_questions', { kind: 'frontier', limit: '2' });
check('limit sent as text is accepted', !tl.err && tl.j.total_matches === 1 && tl.j.results.length === 1, tl.j);
const tb = await call('search_entities', { query: 'raptor', limit: 1000 });
check('limit above the maximum is capped, not an error', !tb.err && tb.j.results.length >= 1, tb.j);

// ------------------------------------------------ 1.3.3: clip, curation flags, counts
{
  const PAR = 'First sentence is short and complete. Second sentence (a long aside, with e.g. details; ' + 'and more; '.repeat(40) + ') ends later. Third one.';
  const q2 = [{ id: 'H9', kind: 'open-question', title: 'Q', category: 'c', evidence_stands_at: 'x', still_open: PAR, url: 'u' }];
  at = fresh(); site.questions = q2;
  const lq = await listQuestions(at, {});
  const so = lq.results[0].still_open;
  check('clip: no cut inside parentheses or at ";"', lq.results[0].still_open_truncated === true && so === 'First sentence is short and complete. ...' || (!/\([^)]*$/.test(so.replace(/ \.\.\.$/, '')) && !/;/.test(so)), so);
  const lq2 = await listQuestions((at = fresh(), site.questions = questions, at), { kind: 'open-question', limit: 1 });
  check('clip: keeps several whole sentences up to ~320 chars', lq2.results[0].still_open.length > 100 && lq2.results[0].still_open.length <= 330 && /\. \.\.\.$/.test(lq2.results[0].still_open), lq2.results[0].still_open);

  at = fresh();
  site.relations = [...relations, rel('CUR-ONLY', { contested: false, curation_contested: true, consensus_contested: false, note: 'See LEU-LARS.' })];
  const fc = await findContradictions(at, {});
  const cur = fc.results.find((r) => r.id === 'CUR-ONLY');
  check('curation-contested relation is listed with its own status', cur?.status === 'flagged-in-curation' && cur.curation_contested === true && cur.conflicting_studies_missing === true, cur);
  check('breakdown counts curation-only relations', fc.breakdown.flagged_curation_or_consensus_only === 1 && fc.total === 6, fc.breakdown);
  check('named_in_text present, data_note says a mention is not evidence', cur.named_in_text?.[0]?.id === 'LEU-LARS' && /not mean/.test(cur.data_note), cur);

  at = fresh();
  site.meta = { ...META, counts: { ...META.counts, contested_or_conflicting_relations: 5 } };
  const ab = await atlasAbout(at);
  check('atlas_about does not repeat counts the Atlas reports itself', ab.derived_counts === undefined && ab.counts.contested_or_conflicting_relations === 5, ab);
}
await c.close();

console.log(fail ? `FAILED ${fail}` : 'ALL OK'); process.exit(fail ? 1 : 0);
