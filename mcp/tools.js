// Tool definitions shared by the stdio server (index.js, npm package) and the
// remote Streamable HTTP server (worker/, Cloudflare Workers). One definition,
// so the two can never offer different tools or descriptions.
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import {
  CODE_ORDER, searchStudies, searchEntities, getEntity, findRelations,
  evidenceBetween, findContradictions, listQuestions,
} from './lib.js';

// Keep equal to "version" in package.json and server.json (test.js checks it).
export const VERSION = '1.2.0';

export const INSTRUCTIONS = `Oliver's mTOR Atlas is a curated, evidence-labelled corpus of mTOR research (studies, entities, signed pathway relations, open questions).
How to use it well:
- Every study has an evidence code: S synthesis of human data, H human study, A animal model, M molecular/in vitro, R review, PP preprint, RT registered trial. The code describes the KIND of study, not its quality. Do not present an M finding as if it were shown in people.
- A relation is a claim (source -> effect -> target) with supporting and conflicting studies, boundary conditions, a consensus flag and a human-relevance grade. Quote the boundary when you use a relation.
- "Not in the Atlas" means not in this curated corpus, not "not known". Say so.
- Cite the study or relation 'url' fields, and the dataset (doi:10.5281/zenodo.22059963) with the dataset_version and corpus_snapshot from atlas_about.`;


/** A fresh MCP server with all Atlas tools, reading through `atlas`. */
export function createServer(atlas) {
  const server = new McpServer({ name: 'mtor-atlas', version: VERSION }, { instructions: INSTRUCTIONS });
  const RO = { readOnlyHint: true, openWorldHint: false, idempotentHint: true };
  const ok = (obj) => ({ content: [{ type: 'text', text: JSON.stringify(obj, null, 1) }] });
  const missing = (what) => ({ content: [{ type: 'text', text: `${what} not found in the Atlas.` }], isError: true });
  const Code = z.enum(CODE_ORDER);

  server.registerTool('atlas_about', {
    title: 'About the Atlas', annotations: RO,
    description: 'Dataset version, corpus snapshot date, counts, evidence-code legend and how to cite. Call first when citing.',
  }, async () => ok(await atlas.meta()));

  server.registerTool('search_studies', {
    title: 'Search studies', annotations: RO,
    description: 'Search the curated studies by keywords (title, finding, authors, journal, model system), optionally filtered by evidence code, a linked entity (gene, drug, disease...) and year range. Returns summary records with evidence codes and URLs.',
    inputSchema: {
      query: z.string().optional().describe('Keywords, e.g. "rapamycin lifespan mice". Omit to list by filters only.'),
      evidence_code: z.array(Code).optional().describe('Keep only these evidence codes, e.g. ["H","S"] for human evidence.'),
      entity: z.string().optional().describe('Only studies linked to this entity (name, synonym or id), e.g. "Rheb".'),
      year_from: z.number().int().optional(), year_to: z.number().int().optional(),
      limit: z.number().int().min(1).max(50).default(20),
      offset: z.number().int().min(0).default(0).describe('For the next page: pass next_offset from the previous answer.'),
    },
  }, async (a) => ok(await searchStudies(atlas, a)));

  server.registerTool('get_study', {
    title: 'Get one study', annotations: RO,
    description: 'Full record for one study by Atlas ID (e.g. "SAB1994"): abstract excerpt, extracted findings, linked entities, the relations it supports or contradicts, related open questions.',
    inputSchema: { sid: z.string().describe('Atlas study ID, e.g. "SAB1994"') },
  }, async ({ sid }) => { const s = await atlas.one('studies', sid.toUpperCase()); return s ? ok(s) : missing(`Study ${sid}`); });

  server.registerTool('search_entities', {
    title: 'Search entities', annotations: RO,
    description: 'Find genes/proteins, complexes, drugs, diseases, processes, nutrients and outcomes by name or synonym.',
    inputSchema: {
      query: z.string().describe('Name or synonym, e.g. "raptor", "sirolimus"'),
      type: z.string().optional().describe('Optional type filter, e.g. "Drug", "Gene/Protein", "Disease"'),
      limit: z.number().int().min(1).max(100).default(20),
    },
  }, async (a) => ok(await searchEntities(atlas, a)));

  server.registerTool('get_entity', {
    title: 'Get one entity', annotations: RO,
    description: 'One entity (gene/protein, complex, drug, disease, process...) with its linked studies as short cards (first studies_limit) and every pathway relation it takes part in as a one-line claim. Accepts an id, a name or a synonym. For more studies use search_studies with entity=...',
    inputSchema: {
      entity: z.string().describe('e.g. "mTORC1", "Rheb", "rapamycin"'),
      studies_limit: z.number().int().min(0).max(50).default(25),
    },
  }, async ({ entity, studies_limit }) => {
    const e = await getEntity(atlas, entity, { studies_limit });
    return e ? ok(e) : missing(`Entity "${entity}"`);
  });

  server.registerTool('find_relations', {
    title: 'Find pathway relations', annotations: RO,
    description: 'Signed, evidence-linked pathway relations (claims such as "Rheb activates mTORC1"). Filter by an entity on either end, by source/target, effect, contested status or minimum strength of the best supporting evidence.',
    inputSchema: {
      entity: z.string().optional().describe('Entity on either end of the relation'),
      source: z.string().optional(), target: z.string().optional(),
      effect: z.enum(['activates', 'inhibits', 'binds', 'recruits', 'required-for', 'context-dependent', 'no-effect']).optional(),
      contested_only: z.boolean().optional().describe('Only relations marked contested or with conflicting studies'),
      strongest_at_least: Code.optional().describe('Keep relations whose best supporting study is at least this code in the order S > H > A > M'),
      limit: z.number().int().min(1).max(50).default(20),
      offset: z.number().int().min(0).default(0).describe('For the next page: pass next_offset from the previous answer.'),
    },
  }, async (a) => ok(await findRelations(atlas, a)));

  server.registerTool('get_relation', {
    title: 'Get one relation', annotations: RO,
    description: 'One pathway relation by ID (e.g. "RHEB-MTORC1"): mechanism, boundary conditions, confidence, supporting and conflicting studies.',
    inputSchema: { id: z.string() },
  }, async ({ id }) => { const r = await atlas.one('relations', id.toUpperCase()); return r ? ok(r) : missing(`Relation ${id}`); });

  server.registerTool('evidence_between', {
    title: 'Evidence between two entities', annotations: RO,
    description: 'Direct curated relations between two entities (either direction) with full cards for the supporting and conflicting studies. Use to answer "what is the evidence that A acts on B?".',
    inputSchema: { a: z.string(), b: z.string() },
  }, async (a) => ok(await evidenceBetween(atlas, a)));

  server.registerTool('find_contradictions', {
    title: 'Find contested claims', annotations: RO,
    description: 'Relations the Atlas marks as contested or that carry conflicting studies, with both sides of the evidence. Optionally limited to one entity.',
    inputSchema: { entity: z.string().optional(), limit: z.number().int().min(1).max(50).default(20) },
  }, async (a) => ok(await findContradictions(atlas, a)));

  server.registerTool('list_questions', {
    title: 'List open questions', annotations: RO,
    description: 'The Atlas\'s open questions (evidence gaps with testable hypotheses) and frontier questions.',
    inputSchema: { kind: z.enum(['open-question', 'frontier']).optional() },
  }, async (a) => ok(await listQuestions(atlas, a)));

  server.registerTool('get_question', {
    title: 'Get one question', annotations: RO,
    description: 'One open or frontier question by ID (e.g. "H1", "F2"): the gap, what changed, what is still open, how it could be tested, linked studies.',
    inputSchema: { id: z.string() },
  }, async ({ id }) => { const q = await atlas.one('questions', id.toUpperCase()); return q ? ok(q) : missing(`Question ${id}`); });

  return server;
}
