// Remote MCP server for Oliver's mTOR Atlas, for Cloudflare Workers.
//
// Same tools as the npm package (../../tools.js), served over the MCP
// Streamable HTTP transport at /mcp, so web assistants (ChatGPT, Grok,
// Claude.ai) can connect by URL. Stateless: every POST gets a fresh server
// object; the Atlas data cache lives at module level and is reused while the
// Worker instance stays warm. Read-only, no secrets, no auth.
import { WebStandardStreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js';
import { Atlas } from '../../lib.js';
import { createServer, VERSION, TOOL_NAMES } from '../../tools.js';
import { usageReport } from './usage-sql.js';

const CORS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, POST, DELETE, OPTIONS',
  'access-control-allow-headers': 'content-type, accept, authorization, mcp-session-id, mcp-protocol-version, last-event-id',
  'access-control-expose-headers': 'mcp-session-id, mcp-protocol-version',
  'access-control-max-age': '86400',
};

let atlas = null;
const getAtlas = (env) => (atlas ??= new Atlas(env?.ATLAS_API_BASE || undefined));

function withCors(res) {
  const h = new Headers(res.headers);
  for (const [k, v] of Object.entries(CORS)) h.set(k, v);
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h });
}

const json = (obj, status = 200) => new Response(JSON.stringify(obj, null, 2), {
  status, headers: { 'content-type': 'application/json; charset=utf-8', ...CORS },
});

const INFO = {
  name: "Oliver's mTOR Atlas MCP server",
  version: VERSION,
  mcp_endpoint: '/mcp',
  transport: 'streamable-http (stateless)',
  auth: 'none (public, read-only)',
  docs: 'https://mtor-atlas.org/api/#mcp',
  usage_stats: '/stats?days=30 (anonymous aggregate counts)',
  source: 'https://github.com/open-mtor-atlas/atlas/tree/main/mcp',
  data: 'https://mtor-atlas.org/api/v1/ (CC BY 4.0, doi:10.5281/zenodo.22059963)',
};


// ---- Anonymous usage counts (Cloudflare Workers Analytics Engine) ----------
// One data point per JSON-RPC message: day-level counts of which method/tool
// was used, by which kind of client, and whether it succeeded. Since 2026-10-10
// the tool arguments (search term, study ID; max 200 characters, e-mail-like
// strings removed) are stored too, in blob6, and are NOT part of the public
// /stats output: they are read only with usage.mjs --queries and an account token.
// Never stored: IP address, raw User-Agent, results, or anything that
// identifies a person. Skipped silently when the USAGE binding is absent
// (local tests, or Analytics Engine not enabled on the account).
const clean = (v, max = 48) => String(v ?? '').toLowerCase().replace(/[^a-z0-9 ./_-]/g, '').trim().slice(0, max) || '-';

// Coarse client family from the User-Agent; the raw header is never stored.
function uaFamily(ua) {
  const u = (ua || '').toLowerCase();
  const known = [
    ['claude', 'claude'], ['anthropic', 'claude'], ['openai', 'openai'], ['chatgpt', 'openai'],
    ['grok', 'xai'], ['xai', 'xai'], ['perplexity', 'perplexity'], ['cursor', 'cursor'],
    ['windsurf', 'windsurf'], ['vscode', 'vscode'], ['mcp-inspector', 'inspector'],
    ['python', 'python'], ['node', 'node'], ['undici', 'node'], ['curl', 'curl'], ['mozilla', 'browser'],
  ];
  for (const [needle, fam] of known) if (u.includes(needle)) return fam;
  return u ? 'other' : '-';
}

// Tool arguments as short text for the private query log. Strips e-mail-like strings
// and control characters, caps the length. Probe calls with invented tool names get none.
function argText(a) {
  if (a == null || typeof a !== 'object') return '';
  let t;
  try { t = JSON.stringify(a); } catch { return ''; }
  return t.replace(/[\u0000-\u001f]/g, ' ').replace(/[^\s"']+@[^\s"']+/g, '[email]').slice(0, 200);
}

const KNOWN_TOOLS = new Set(TOOL_NAMES);

// Anonymous per-user ids that some hosts send in a tool call's params._meta, used only to count
// distinct users. The value is never stored: only a salted SHA-256 prefix (secret USAGE_SALT), so
// the stored key cannot be traced back to the host's id or to a person.
// [_meta key, short label]. ChatGPT / Codex plugins send "openai/subject" ("v1/<uuid>").
// When another host (e.g. the Claude connector directory) turns out to send such an id, add its
// key here; blob8 below records which _meta keys each host sends, to find it.
const USER_META_KEYS = [
  ['openai/subject', 'oa'],
];

async function userKey(meta, salt) {
  if (!salt || !meta || typeof meta !== 'object') return '';
  for (const [key, label] of USER_META_KEYS) {
    const v = meta[key];
    if (typeof v !== 'string' || !v) continue;
    try {
      const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${salt}|${label}|${v}`));
      return `${label}:` + [...new Uint8Array(buf)].slice(0, 8).map((b) => b.toString(16).padStart(2, '0')).join('');
    } catch { return ''; }
  }
  return '';
}

// Names (never values) of the _meta keys a host sends, e.g. "openai/locale,openai/subject".
function metaKeys(meta) {
  if (!meta || typeof meta !== 'object') return '';
  return Object.keys(meta).map((k) => clean(k, 40)).sort().join(',').slice(0, 160);
}

async function recordUsage(env, messages, replies, ua, ms) {
  const ds = env?.USAGE;
  if (!ds?.writeDataPoint) return;
  const byId = new Map((replies || []).map((r) => [r?.id, r]));
  const fam = uaFamily(ua);
  for (const m of messages) {
    if (!m || typeof m.method !== 'string') continue;
    // A call to a tool the server does not have is a probe (catalog check): count it under one
    // label, so it neither adds rows to the per-tool table nor inflates the error counts.
    const unknown = m.method === 'tools/call' && !KNOWN_TOOLS.has(m.params?.name);
    const tool = m.method === 'tools/call' ? (unknown ? 'unknown-tool' : clean(m.params?.name)) : '-';
    const args = m.method === 'tools/call' && !unknown ? argText(m.params?.arguments) : '';
    const client = m.method === 'initialize' ? clean(m.params?.clientInfo?.name) : '-';
    const r = byId.get(m.id);
    const outcome = m.id === undefined ? 'notification'
      : unknown ? 'unknown-tool'
      : !r ? 'no-reply'
      : r.error ? 'error'
      : r.result?.isError ? (args === '' || args === '{}' ? 'no-args' : 'tool-error') : 'ok';   // a scanner calling a tool with no arguments is not a tool failure
    const meta = m.params?._meta;
    const user = m.method === 'tools/call' && !unknown ? await userKey(meta, env?.USAGE_SALT) : '';
    try {
      ds.writeDataPoint({
        indexes: [clean(m.method)],
        // blob7 = anonymous user key (salted hash, or empty), blob8 = names of the _meta keys sent
        blobs: [clean(m.method), tool, client, fam, outcome, args, user, metaKeys(meta)],
        doubles: [1, ms],
      });
    } catch { /* counting must never break a request */ }
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });

    if (url.pathname === '/' || url.pathname === '') {
      return request.method === 'GET' ? json(INFO) : json({ error: 'Use POST /mcp' }, 405);
    }
    if (url.pathname === '/health') return json({ ok: true, version: VERSION });

    // Public aggregate usage counts (no per-request rows, nothing about people).
    // Needs the secret ANALYTICS_TOKEN (Account Analytics: Read); cached for 10 minutes.
    if (url.pathname === '/stats') {
      if (!env?.ANALYTICS_TOKEN) return json({ error: 'Usage stats not configured' }, 404);
      const days = Math.max(1, Math.min(90, Number(url.searchParams.get('days')) || 30));
      const cacheKey = new Request(`https://stats.cache/${days}`);
      const cache = globalThis.caches?.default;
      const hit = cache && await cache.match(cacheKey);
      if (hit) return withCors(hit);
      try {
        const report = await usageReport(env.CF_ACCOUNT_ID, env.ANALYTICS_TOKEN, days);
        const res = new Response(JSON.stringify(report, null, 2), {
          headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=600' },
        });
        if (cache) await cache.put(cacheKey, res.clone());
        return withCors(res);
      } catch (e) {
        return json({ error: 'Stats query failed', detail: String(e.message || e).slice(0, 200) }, 502);
      }
    }

    // Domain verification for the OpenAI Plugins Directory (ChatGPT, Codex).
    // The token comes from the OpenAI dashboard and is set as a Worker
    // variable/secret OPENAI_APPS_CHALLENGE; it must be returned verbatim.
    if (url.pathname === '/.well-known/openai-apps-challenge') {
      const token = env?.OPENAI_APPS_CHALLENGE;
      return token
        ? new Response(token, { headers: { 'content-type': 'text/plain; charset=utf-8', ...CORS } })
        : json({ error: 'Not configured' }, 404);
    }

    if (url.pathname === '/mcp' || url.pathname === '/mcp/') {
      if (request.method !== 'POST') {
        // Stateless server: no standalone SSE stream (GET) and no sessions to end (DELETE).
        return json({ jsonrpc: '2.0', error: { code: -32000, message: 'Method not allowed. Use POST.' }, id: null }, 405);
      }
      const server = createServer(getAtlas(env));
      const transport = new WebStandardStreamableHTTPServerTransport({
        sessionIdGenerator: undefined,
        enableJsonResponse: true,
      });
      await server.connect(transport);
      const t0 = Date.now();
      // Read the JSON-RPC message(s) for the usage counter before the transport consumes the body.
      let messages = [];
      try {
        const body = await request.clone().json();
        messages = Array.isArray(body) ? body : [body];
      } catch { /* malformed body: the transport answers with a JSON-RPC error */ }
      try {
        const res = await transport.handleRequest(request);
        if (env?.USAGE && messages.length) {
          let replies = [];
          try {
            const out = await res.clone().json();
            replies = Array.isArray(out) ? out : [out];
          } catch { /* 202 Accepted for notifications has no body */ }
          const done = recordUsage(env, messages, replies, request.headers.get('user-agent'), Date.now() - t0).catch(() => {});
          if (ctx?.waitUntil) ctx.waitUntil(done); else await done;
        }
        return withCors(res);
      } finally {
        // The response body is already complete (enableJsonResponse), so closing is safe.
        transport.close?.();
        server.close?.();
      }
    }
    return json({ error: 'Not found', see: '/' }, 404);
  },
};
