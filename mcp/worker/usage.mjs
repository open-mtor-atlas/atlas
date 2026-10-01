// Anonymous usage report for the remote MCP server (Workers Analytics Engine).
//
//   CF_ACCOUNT_ID defaults to the Atlas account; override with set CF_ACCOUNT_ID=...
//   set CF_API_TOKEN=...             (token "mtor-atlas-mcp-usage-read", Account Analytics: Read)
//   node usage.mjs [days]            default 30
//
// Data points come from src/index.js recordUsage(): blob1 method, blob2 tool,
// blob3 client name (initialize only), blob4 client family, blob5 outcome,
// double2 duration in ms. Analytics Engine samples at high volume, so counts
// use SUM(_sample_interval). Data is kept by Cloudflare for 3 months.
const acct = process.env.CF_ACCOUNT_ID || '28737ccd742e4db6af4ea76764219a6f';
const token = process.env.CF_API_TOKEN;
if (!acct || !token) { console.error('Set CF_API_TOKEN first (see the header of this file).'); process.exit(1); }
const days = Math.max(1, Math.min(90, Number(process.argv[2]) || 30));
const DS = 'mtor_atlas_mcp_usage';
const since = `timestamp > NOW() - INTERVAL '${days}' DAY`;

async function q(sql) {
  const r = await fetch(`https://api.cloudflare.com/client/v4/accounts/${acct}/analytics_engine/sql`, {
    method: 'POST', headers: { authorization: `Bearer ${token}` }, body: sql,
  });
  const txt = await r.text();
  if (!r.ok) throw new Error(`${r.status}: ${txt.slice(0, 300)}`);
  return JSON.parse(txt).data;
}
const table = (title, rows) => {
  console.log(`\n${title}`);
  if (!rows.length) return console.log('  (no data yet)');
  for (const r of rows) console.log('  ' + Object.values(r).map((v, i) => String(v).padEnd(i ? 10 : 28)).join(''));
};

console.log(`mTOR Atlas MCP usage, last ${days} days`);
table('Tool calls by tool (calls, errors, avg ms)', await q(`
  SELECT blob2 AS tool, SUM(_sample_interval) AS calls,
         SUM(if(blob5 != 'ok', _sample_interval, 0)) AS errors, ROUND(AVG(double2)) AS avg_ms
  FROM ${DS} WHERE blob1 = 'tools/call' AND ${since} GROUP BY tool ORDER BY calls DESC`));
table('Connections (initialize) by client name', await q(`
  SELECT blob3 AS client, SUM(_sample_interval) AS sessions
  FROM ${DS} WHERE blob1 = 'initialize' AND ${since} GROUP BY client ORDER BY sessions DESC LIMIT 20`));
table('Tool calls by client family (User-Agent)', await q(`
  SELECT blob4 AS family, SUM(_sample_interval) AS calls
  FROM ${DS} WHERE blob1 = 'tools/call' AND ${since} GROUP BY family ORDER BY calls DESC`));
table('Per day (connections, tool calls)', await q(`
  SELECT toStartOfInterval(timestamp, INTERVAL '1' DAY) AS day,
         SUM(if(blob1 = 'initialize', _sample_interval, 0)) AS connections,
         SUM(if(blob1 = 'tools/call', _sample_interval, 0)) AS tool_calls
  FROM ${DS} WHERE ${since} GROUP BY day ORDER BY day DESC`));
