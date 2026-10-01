// Remote MCP server for Oliver's mTOR Atlas, for Cloudflare Workers.
//
// Same tools as the npm package (../../tools.js), served over the MCP
// Streamable HTTP transport at /mcp, so web assistants (ChatGPT, Grok,
// Claude.ai) can connect by URL. Stateless: every POST gets a fresh server
// object; the Atlas data cache lives at module level and is reused while the
// Worker instance stays warm. Read-only, no secrets, no auth.
import { WebStandardStreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js';
import { Atlas } from '../../lib.js';
import { createServer, VERSION } from '../../tools.js';

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
  source: 'https://github.com/open-mtor-atlas/atlas/tree/main/mcp',
  data: 'https://mtor-atlas.org/api/v1/ (CC BY 4.0, doi:10.5281/zenodo.22059963)',
};


// ---- Anonymous usage counts (Cloudflare Workers Analytics Engine) ----------
// One data point per JSON-RPC message: day-level counts of which method/tool
// was used, by which kind of client, and whether it succeeded. Never stored:
// IP address, raw User-Agent, tool arguments, results, or anything that
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

function recordUsage(env, messages, replies, ua, ms) {
  const ds = env?.USAGE;
  if (!ds?.writeDataPoint) return;
  const byId = new Map((replies || []).map((r) => [r?.id, r]));
  const fam = uaFamily(ua);
  for (const m of messages) {
    if (!m || typeof m.method !== 'string') continue;
    const tool = m.method === 'tools/call' ? clean(m.params?.name) : '-';
    const client = m.method === 'initialize' ? clean(m.params?.clientInfo?.name) : '-';
    const r = byId.get(m.id);
    const outcome = m.id === undefined ? 'notification'
      : !r ? 'no-reply'
      : r.error ? 'error'
      : r.result?.isError ? 'tool-error' : 'ok';
    try {
      ds.writeDataPoint({
        indexes: [clean(m.method)],
        blobs: [clean(m.method), tool, client, fam, outcome],
        doubles: [1, ms],
      });
    } catch { /* counting must never break a request */ }
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });

    if (url.pathname === '/' || url.pathname === '') {
      return request.method === 'GET' ? json(INFO) : json({ error: 'Use POST /mcp' }, 405);
    }
    if (url.pathname === '/health') return json({ ok: true, version: VERSION });

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
          recordUsage(env, messages, replies, request.headers.get('user-agent'), Date.now() - t0);
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
