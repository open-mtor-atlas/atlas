// Smoke test: connects to the server and calls every tool once.
//   node test.js                          stdio server (index.js), live data
//   node test.js --worker                 the Cloudflare Worker code, run in-process
//   node test.js --url https://…/mcp      a deployed remote server
//   ATLAS_API_BASE=/path/to/dist/api/v1   read a local build instead of the live site
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { VERSION } from './tools.js';

const here = (f) => new URL(f, import.meta.url);
const pkg = JSON.parse(readFileSync(here('./package.json'), 'utf-8'));
const sj = JSON.parse(readFileSync(here('./server.json'), 'utf-8'));
const versions = [VERSION, pkg.version, sj.version, ...(sj.packages ?? []).map((p) => p.version)];
if (new Set(versions).size !== 1) { console.error('VERSION MISMATCH tools.js/package.json/server.json:', versions); process.exit(1); }

const argv = process.argv.slice(2);
let t;
if (argv[0] === '--worker') {
  const worker = (await import('./worker/src/index.js')).default;
  // Fake Analytics Engine binding: collects the anonymous usage data points.
  globalThis.__usage = [];
  const env = { ATLAS_API_BASE: process.env.ATLAS_API_BASE, USAGE: { writeDataPoint: (p) => globalThis.__usage.push(p) } };
  t = new StreamableHTTPClientTransport(new URL('https://worker.test/mcp'),
    { fetch: (u, init) => worker.fetch(new Request(u, init), env) });
} else if (argv[0] === '--url') {
  t = new StreamableHTTPClientTransport(new URL(argv[1]));
} else {
  t = new StdioClientTransport({ command: process.execPath, args: [fileURLToPath(here('./index.js'))], env: { ...process.env } });
}
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
if (globalThis.__usage) {
  const pts = globalThis.__usage;
  const toolCalls = pts.filter((p) => p.blobs[0] === 'tools/call');
  const init = pts.find((p) => p.blobs[0] === 'initialize');
  const bad = toolCalls.length !== calls.length
    || init?.blobs[2] !== 'atlas-test'
    || toolCalls.find((p) => p.blobs[1] === 'get_study' && p.blobs[4] === 'tool-error') === undefined
    || JSON.stringify(pts).includes('rapamycin');   // tool arguments must never be recorded
  console.log(`usage points: ${pts.length} (tools/call ${toolCalls.length}), e.g. ${JSON.stringify(toolCalls[1]?.blobs)}` + (bad ? '  <-- USAGE CHECK FAILED' : ''));
  if (bad) fail++;
}
console.log(fail ? `FAILED ${fail}` : 'ALL OK');
process.exit(fail ? 1 : 0);
