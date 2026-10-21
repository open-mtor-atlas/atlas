// Tool definitions shared by the stdio server (index.js, npm package) and the
// remote Streamable HTTP server (worker/, Cloudflare Workers). One definition,
// so the two can never offer different tools or descriptions.
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import {
  CODE_ORDER, atlasAbout, searchStudies, searchEntities, getEntity, findRelations,
  evidenceBetween, findContradictions, listQuestions, findStudy, searchAuthors, getAuthor,
} from './lib.js';

// Keep equal to "version" in package.json and server.json (test.js checks it).
export const VERSION = '1.3.3';

// Names of the registered tools (test.js checks this list against listTools). The remote Worker uses it
// to keep probes that call an invented tool name out of the per-tool usage statistics.
export const TOOL_NAMES = ['atlas_about', 'search_studies', 'get_study', 'search_entities', 'get_entity',
  'find_relations', 'get_relation', 'evidence_between', 'find_contradictions', 'list_questions',
  'get_question', 'search_authors', 'get_author'];

export const INSTRUCTIONS = `Oliver's mTOR Atlas is a curated, evidence-labelled corpus of mTOR research (studies, entities, signed pathway relations, open questions).
How to use it well:
- Every study has an evidence code: S synthesis of human data, H human study, A animal model, M molecular/in vitro, R review, PP preprint, RT registered trial. The code describes the KIND of study, not its quality. Do not present an M finding as if it were shown in people.
- A relation is a claim (source -> effect -> target) with supporting and conflicting studies, boundary conditions, a consensus flag and a human-relevance grade. Quote the boundary when you use a relation.
- "Not in the Atlas" means not in this curated corpus, not "not known". Say so.
- An empty search is not proof that something is missing. Look up a person with search_authors or get_author, and a paper with get_study by PMID or DOI, before saying the Atlas does not have it.
- Cite the study or relation 'url' fields, and the dataset (doi:10.5281/zenodo.22059963) with the dataset_version, corpus_snapshot and source_commit from atlas_about. A dataset_version ending in "+unreleased" means the live data are newer than the archived Zenodo version; do not cite that version DOI for them.`;


/** A fresh MCP server with all Atlas tools, reading through `atlas`. */
export function createServer(atlas) {
  const server = new McpServer({ name: 'mtor-atlas', version: VERSION }, { instructions: INSTRUCTIONS });
  const RO = { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true };
  const ok = (obj) => ({ content: [{ type: 'text', text: JSON.stringify(obj, null, 1) }] });
  const missing = (what) => ({ content: [{ type: 'text', text: `${what} not found in the Atlas.` }], isError: true });
  const Code = z.enum(CODE_ORDER);
  // Clients often send numbers as text ("2") or ask for more than the maximum.
  // Accept the text form and cap the value instead of failing the call.
  const Int = (min, def) => { const t = z.coerce.number().int().min(min); return def === undefined ? t.optional() : t.default(def); };
  const cap = (a, max) => ({ ...a, limit: Math.min(a.limit, max) });

  server.registerTool('atlas_about', {
    title: 'About the Atlas', annotations: { ...RO, title: 'About the Atlas' },
    description: 'Dataset version, corpus snapshot date, counts, evidence-code legend and how to cite the dataset. When the Atlas does not report the contested and conflicting counts itself, derived_counts adds them, computed from the relations, so they can be compared with find_contradictions.',
  }, async () => ok(await atlasAbout(atlas)));

  server.registerTool('search_studies', {
    title: 'Search studies', annotations: { ...RO, title: 'Search studies' },
    description: 'Search the curated studies by keywords, optionally filtered by evidence code, a linked entity (gene, drug, disease...) and year range. Searches title, finding, authors (author-list form "Sabatini DM" and full names of profiled authors), PMID, DOI, PMCID, linked entities and their synonyms, journal, model system and the abstract excerpt. A query that is a PMID or DOI returns that study. Returns summary records with evidence codes and URLs.',
    inputSchema: {
      query: z.string().optional().describe('Keywords, e.g. "rapamycin lifespan mice", a person ("Claudio De Virgilio"), a PMID or a DOI. Omit to list by filters only.'),
      evidence_code: z.array(Code).optional().describe('Keep only these evidence codes, e.g. ["H","S"] for human evidence.'),
      entity: z.string().optional().describe('Only studies linked to this entity (name, synonym or id), e.g. "Rheb".'),
      year_from: Int(-10000), year_to: Int(-10000),
      limit: Int(1, 20).describe('Maximum 50; a larger value is capped at 50.'),
      offset: Int(0, 0).describe('For the next page: pass next_offset from the previous answer.'),
    },
  }, async (a) => ok(await searchStudies(atlas, cap(a, 50))));

  server.registerTool('get_study', {
    title: 'Get one study', annotations: { ...RO, title: 'Get one study' },
    description: 'Full record for one study by Atlas ID (e.g. "SAB1994"), PMID, DOI or PMCID: abstract excerpt, extracted findings, linked entities, the relations it supports or contradicts, related open questions.',
    inputSchema: {
      sid: z.string().optional().describe('Atlas study ID ("SAB1994"), PMID ("23716719"), DOI or PMCID'),
      study_id: z.string().optional().describe('Alias of sid.'),
      id: z.string().optional().describe('Alias of sid.'),
    },
  }, async (a) => {
    const sid = a.sid || a.study_id || a.id;
    if (!sid) return missing('Study (pass sid, e.g. "SAB1994")');
    const hit = await findStudy(atlas, sid);
    const s = hit && await atlas.one('studies', hit.sid);
    return s ? ok(s) : missing(`Study ${sid} (looked up as Atlas ID, PMID, DOI and PMCID)`);
  });

  server.registerTool('search_entities', {
    title: 'Search entities', annotations: { ...RO, title: 'Search entities' },
    description: 'Find genes/proteins, complexes, drugs, diseases, processes, nutrients and outcomes by name or synonym. Each result says where it matched (match_field: name, synonym or description); use match="name" to leave out description-only hits.',
    inputSchema: {
      query: z.string().describe('Name or synonym, e.g. "raptor", "sirolimus"'),
      type: z.string().optional().describe('Optional type filter, e.g. "Drug", "Gene/Protein", "Disease"'),
      match: z.enum(['any', 'name']).default('any').describe('"any" also searches descriptions; "name" searches names and synonyms only.'),
      limit: Int(1, 20).describe('Maximum 100; a larger value is capped at 100.'),
      offset: Int(0, 0).describe('For the next page: pass next_offset from the previous answer.'),
    },
  }, async (a) => ok(await searchEntities(atlas, cap(a, 100))));

  server.registerTool('get_entity', {
    title: 'Get one entity', annotations: { ...RO, title: 'Get one entity' },
    description: 'One entity (gene/protein, complex, drug, disease, process...) with its linked studies as short cards (first studies_limit) and every pathway relation it takes part in as a one-line claim. Accepts an id, a name or a synonym.',
    inputSchema: {
      entity: z.string().optional().describe('e.g. "mTORC1", "Rheb", "rapamycin"'),
      id: z.string().optional().describe('Alias of entity.'),
      studies_limit: Int(0, 25).describe('Maximum 50; a larger value is capped at 50.'),
    },
  }, async (a) => {
    const entity = a.entity || a.id;
    if (!entity) return missing('Entity (pass entity, e.g. "Rheb")');
    const e = await getEntity(atlas, entity, { studies_limit: Math.min(a.studies_limit, 50) });
    return e ? ok(e) : missing(`Entity "${entity}"`);
  });

  server.registerTool('find_relations', {
    title: 'Find pathway relations', annotations: { ...RO, title: 'Find pathway relations' },
    description: 'Signed, evidence-linked pathway relations (claims such as "Rheb activates mTORC1"). Filter by an entity on either end, by source/target, effect, contested status or minimum strength of the best supporting evidence.',
    inputSchema: {
      entity: z.string().optional().describe('Entity on either end of the relation'),
      source: z.string().optional(), target: z.string().optional(),
      effect: z.enum(['activates', 'inhibits', 'binds', 'recruits', 'required-for', 'context-dependent', 'no-effect']).optional(),
      contested_only: z.boolean().optional().describe('Only relations marked contested or with conflicting studies'),
      strongest_at_least: Code.optional().describe('Keep relations whose best supporting study is at least this code in the order S > H > A > M'),
      limit: Int(1, 20).describe('Maximum 50; a larger value is capped at 50.'),
      offset: Int(0, 0).describe('For the next page: pass next_offset from the previous answer.'),
    },
  }, async (a) => ok(await findRelations(atlas, cap(a, 50))));

  server.registerTool('get_relation', {
    title: 'Get one relation', annotations: { ...RO, title: 'Get one relation' },
    description: 'One pathway relation by ID (e.g. "RHEB-MTORC1"): mechanism, boundary conditions, confidence, supporting and conflicting studies.',
    inputSchema: { id: z.string() },
  }, async ({ id }) => { const r = await atlas.one('relations', id.toUpperCase()); return r ? ok(r) : missing(`Relation ${id}`); });

  server.registerTool('evidence_between', {
    title: 'Evidence between two entities', annotations: { ...RO, title: 'Evidence between two entities' },
    description: 'Direct curated relations between two entities (either direction) with full cards for the supporting and conflicting studies. Answers questions such as "what is the evidence that A acts on B?". A study that repeats within the answer is sent in full once and afterwards as a short card with full_card_in.',
    inputSchema: {
      a: z.string(), b: z.string(),
      dedupe: z.boolean().default(true).describe('Send a repeated study in full only once. Pass false for a full card every time.'),
    },
  }, async (a) => ok(await evidenceBetween(atlas, a)));

  server.registerTool('find_contradictions', {
    title: 'Find contested claims', annotations: { ...RO, title: 'Find contested claims' },
    description: 'Relations the Atlas marks as contested or that carry conflicting studies, with both sides of the evidence. status says which; breakdown splits the total. A contested relation with no conflicting study listed is flagged conflicting_studies_missing; relations named in its note or boundary are shown in named_in_text (a mention is not evidence). Paged: pass next_offset as offset for the rest. Optionally limited to one entity.',
    inputSchema: {
      entity: z.string().optional(),
      only_contested: z.boolean().default(false).describe('Keep only relations the Atlas flags contested, not those that merely carry conflicting studies.'),
      brief: z.boolean().default(false).describe('Shorten the long boundary and note text (text_truncated is set); get_relation has the full text.'),
      dedupe: z.boolean().default(true).describe('Send a repeated study in full only once. Pass false for a full card every time.'),
      limit: Int(1, 20).describe('Maximum 50; a larger value is capped at 50.'),
      offset: Int(0, 0).describe('For the next page: pass next_offset from the previous answer.'),
    },
  }, async (a) => ok(await findContradictions(atlas, cap(a, 50))));

  server.registerTool('list_questions', {
    title: 'List open questions', annotations: { ...RO, title: 'List open questions' },
    description: 'The Atlas\'s open questions (evidence gaps with testable hypotheses) and frontier questions. Paged. By default still_open is shortened at a sentence boundary (still_open_truncated); get_question has the full text, or pass brief=false.',
    inputSchema: {
      kind: z.enum(['open-question', 'frontier']).optional(),
      query: z.string().optional().describe('Keywords to find questions by their title, gap, hypothesis or what is still open, e.g. "rapamycin immune".'),
      brief: z.boolean().default(true).describe('Shorten still_open; false returns the full text.'),
      limit: Int(1, 20).describe('Maximum 50; a larger value is capped at 50.'),
      offset: Int(0, 0).describe('For the next page: pass next_offset from the previous answer.'),
    },
  }, async (a) => ok(await listQuestions(atlas, cap(a, 50))));

  server.registerTool('get_question', {
    title: 'Get one question', annotations: { ...RO, title: 'Get one question' },
    description: 'One open or frontier question by ID (e.g. "H1", "F2"): the gap, what changed, what is still open, how it could be tested, linked studies.',
    inputSchema: { id: z.string() },
  }, async ({ id }) => { const q = await atlas.one('questions', id.toUpperCase()); return q ? ok(q) : missing(`Question ${id}`); });

  server.registerTool('search_authors', {
    title: 'Search authors', annotations: { ...RO, title: 'Search authors' },
    description: 'People in the Atlas by full name ("Claudio De Virgilio"), author-list form ("De Virgilio C"), ORCID or lab. results are authors with a profile page (full name, ORCID, lab, their study IDs); in_author_lists are matching names in study author lists without a profile.',
    inputSchema: {
      query: z.string().describe('A name, ORCID or lab, e.g. "Sabatini", "Claudio De Virgilio", "Fribourg"'),
      limit: Int(1, 20).describe('Maximum 50; a larger value is capped at 50.'),
      offset: Int(0, 0).describe('For the next page: pass next_offset from the previous answer.'),
    },
  }, async (a) => ok(await searchAuthors(atlas, cap(a, 50))));

  server.registerTool('get_author', {
    title: 'Get one author', annotations: { ...RO, title: 'Get one author' },
    description: 'One profiled author by profile id ("claudio-de-virgilio"), full name, author-list form or ORCID: lab, role, profile URL and short cards of their studies in the Atlas.',
    inputSchema: {
      author: z.string().optional().describe('e.g. "Claudio De Virgilio", "De Virgilio C", "claudio-de-virgilio"'),
      id: z.string().optional().describe('Alias of author.'),
    },
  }, async (a) => {
    const q = a.author || a.id;
    if (!q) return missing('Author (pass author, e.g. "Claudio De Virgilio")');
    const r = await getAuthor(atlas, q);
    return r ? ok(r) : missing(`Author "${q}" with a profile page (search_authors also lists names in author lists without a profile)`);
  });

  return server;
}
