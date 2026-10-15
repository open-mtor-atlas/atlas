// Regression test against the REAL corpus: the searches that returned nothing
// or too little before 1.3.2 (found 14-15 Oct 2026, after ChatGPT answered that
// "Claudio De Virgilio" is not in the Atlas while his profile page lists two
// studies). Needs the Atlas API: the live site, or a local build via
//   ATLAS_API_BASE=/path/to/dist/api/v1 node test-corpus.js
// Expectations name studies that are in the corpus, not exact counts, so the
// test survives the corpus growing.
import { Atlas, searchStudies, searchEntities, searchAuthors, getAuthor, listQuestions, findStudy } from './lib.js';

const at = new Atlas();
let fail = 0;
const check = (name, cond, extra) => { console.log((cond ? 'ok   ' : 'FAIL ') + name + (!cond && extra !== undefined ? '  ' + JSON.stringify(extra).slice(0, 240) : '')); if (!cond) fail++; };
const S = async (q, o = {}) => searchStudies(at, { query: q, limit: 50, ...o });
const sids = (r) => r.results.map((s) => s.sid);
const n = async (q) => (await S(q)).total_matches;

// people
const dv = await S('Claudio De Virgilio');
check('"Claudio De Virgilio" finds PAN2013 and NIC2023', ['PAN2013', 'NIC2023'].every((x) => sids(dv).includes(x)), sids(dv));
const ds = await S('David Sabatini');
check('"David Sabatini" finds the Sabatini DM studies', ds.total_matches >= 40, [ds.total_matches, ds.matched_as]);
const ws = await S('Xiang Wang Zzyzx'); // no such person: the surname-initial fallback must not invent hits
check('unknown full name returns nothing', ws.total_matches === 0, sids(ws));
const au = await searchAuthors(at, { query: 'Claudio De Virgilio' });
check('search_authors: profile with both studies', au.results[0]?.id === 'claudio-de-virgilio' && au.results[0].studies.length >= 2, au.results[0]);
check('search_authors: by corpus form too', (await searchAuthors(at, { query: 'De Virgilio C' })).results[0]?.id === 'claudio-de-virgilio');
check('search_authors: by lab city', (await searchAuthors(at, { query: 'Fribourg' })).results.some((a) => a.id === 'claudio-de-virgilio'));
check('search_authors: author-list name without a profile', (await searchAuthors(at, { query: 'Panchaud' })).in_author_lists.some((x) => x.corpus_name === 'Panchaud N'));
const ga = await getAuthor(at, 'Claudio De Virgilio');
check('get_author: full name -> profile + study cards', ga?.study_cards?.length >= 2 && ga.orcid === '0000-0001-8826-4323', ga && Object.keys(ga));

// identifiers
check('PMID finds the study', sids(await S('23716719')).join() === 'PAN2013');
check('DOI finds the study', sids(await S('10.1126/scisignal.2004112')).join() === 'PAN2013');
check('doi.org URL finds the study', sids(await S('https://doi.org/10.1126/scisignal.2004112')).join() === 'PAN2013');
check('unknown PMID says so', /No study with PMID/.test((await S('11111111')).note ?? ''));
check('get_study path: PMID and DOI resolve', (await findStudy(at, '23716719'))?.sid === 'PAN2013' && (await findStudy(at, '10.1126/SCISIGNAL.2004112'))?.sid === 'PAN2013');

// synonyms and linked entities
const linked = async (e) => (await S(undefined, { entity: e })).total_matches;
check('"sirolimus" finds every study linked to Rapamycin', await n('sirolimus') >= await linked('Rapamycin'), [await n('sirolimus'), await linked('Rapamycin')]);
check('"EIF4EBP1" finds every study linked to 4E-BP1', await n('EIF4EBP1') >= await linked('4E-BP1'), [await n('EIF4EBP1'), await linked('4E-BP1')]);
// ranking: the abstract field is weak, so the top of "rapamycin" is about rapamycin, not "target of rapamycin"
const top = (await S('rapamycin', { limit: 20 })).results;
check('top 20 for "rapamycin" all name it in title or finding', top.every((s) => /rapamycin|sirolimus|rapalog/i.test(s.title + ' ' + s.finding)), top.filter((s) => !/rapamycin|sirolimus|rapalog/i.test(s.title + ' ' + s.finding)).map((s) => s.sid));
check('"RRAGA" finds Rag GTPase studies', await n('RRAGA') >= 10, await n('RRAGA'));
check('"GATOR1" finds the linked studies, not only those naming it', await n('GATOR1') > 8, await n('GATOR1'));
check('"Npr2" finds PAN2013 through its abstract', sids(await S('Npr2')).includes('PAN2013'));

// word forms
check('"ageing" == "aging"', await n('ageing') === await n('aging'), [await n('ageing'), await n('aging')]);
check('"amino acids" >= "amino acid"', await n('amino acids') >= await n('amino acid'), [await n('amino acids'), await n('amino acid')]);
check('"mice" >= "mouse"', await n('mice') >= await n('mouse'), [await n('mice'), await n('mouse')]);
check('"Mus musculus" finds mouse studies', await n('Mus musculus') >= await n('mouse'), [await n('Mus musculus'), await n('mouse')]);
check('"Saccharomyces cerevisiae" finds yeast studies', await n('Saccharomyces cerevisiae') >= 7, await n('Saccharomyces cerevisiae'));
check('"rapalogs" entity search finds something', (await searchEntities(at, { query: 'rapalogs' })).total_matches >= 1);

// questions
const q = await listQuestions(at, { query: 'rapamycin' });
check('list_questions takes a query', q.total_matches >= 1 && q.total_matches < 24, q.total_matches);

// empty result explains itself
const none = await S('zzqqxx nonexistentword');
check('empty result says what was searched', none.total_matches === 0 && /Searched:/.test(none.note) && /search_authors/.test(none.note), none.note);

console.log(fail ? `FAILED ${fail}` : 'ALL OK'); process.exit(fail ? 1 : 0);
