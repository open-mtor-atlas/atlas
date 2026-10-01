import { fileURLToPath } from 'node:url';
// Smoke test: starts the server over stdio and calls every tool once.
//   ATLAS_API_BASE=/path/to/dist/api/v1 node test.js   (local build)
//   node test.js                                       (live site)
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const t = new StdioClientTransport({ command: process.execPath, args: [fileURLToPath(new URL('./index.js', import.meta.url))], env: { ...process.env } });
const c = new Client({ name: 'atlas-test', version: '0' });
await c.connect(t);
const tools = (await c.listTools()).tools.map((x) => x.name);
console.log('tools:', tools.join(', '));
const calls = [
  ['atlas_about', {}],
  ['search_studies', { query: 'rapamycin lifespan', evidence_code: ['A'], limit: 3 }],
  ['search_studies', { entity: 'Rheb', limit: 3 }],
  ['get_study', { sid: 'sab1994' }],
  ['search_entities', { query: 'sirolimus' }],
  ['get_entity', { entity: 'Rheb' }],
  ['find_relations', { entity: 'Rheb' }],
  ['find_relations', { strongest_at_least: 'H', limit: 3 }],
  ['get_relation', { id: 'RHEB-MTORC1' }],
  ['evidence_between', { a: 'mTORC1', b: 'Rheb' }],
  ['evidence_between', { a: 'Golgi', b: 'mTORC1' }],
  ['find_contradictions', { limit: 3 }],
  ['list_questions', {}],
  ['get_question', { id: 'H1' }],
  ['get_study', { sid: 'NOPE0000' }],
];
let fail = 0;
for (const [name, args] of calls) {
  const r = await c.callTool({ name, arguments: args });
  const txt = r.content?.[0]?.text ?? '';
  let summary = txt.slice(0, 110).replace(/\s+/g, ' ');
  try {
    const j = JSON.parse(txt);
    summary = j.total_matches !== undefined ? `total_matches=${j.total_matches}, first=${j.results?.[0]?.sid ?? j.results?.[0]?.id ?? j.results?.[0]?.name}`
      : j.direct_relations ? `direct=${j.direct_relations.length} ${j.note ? '(note)' : ''}`
      : Array.isArray(j) ? `n=${j.length}` : j.total !== undefined ? `total=${j.total}` : Object.keys(j).slice(0, 6).join(',');
  } catch {}
  const expectErr = name === 'get_study' && args.sid === 'NOPE0000';
  if (!!r.isError !== expectErr) fail++;
  console.log((r.isError ? 'ERR ' : 'ok  ') + name.padEnd(20) + JSON.stringify(args).slice(0, 60).padEnd(62) + summary);
}
await c.close();
console.log(fail ? `FAILED ${fail}` : 'ALL OK');
process.exit(fail ? 1 : 0);
