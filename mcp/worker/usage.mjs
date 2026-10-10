// Anonymous usage report for the remote MCP server (Workers Analytics Engine).
//
// Easiest: open https://mtor-atlas-mcp.mtor-atlas.workers.dev/stats (same data, JSON).
// Local alternative, without the Worker:
//   $env:ANALYTICS_TOKEN="..."        (PowerShell; token "mtor-atlas-mcp-usage-read", Account Analytics: Read)
//   node usage.mjs [days]          default 30
import { usageReport, queriesSql, runSql } from './src/usage-sql.js';
import { writeFileSync } from 'node:fs';

const acct = process.env.ANALYTICS_ACCOUNT_ID || '28737ccd742e4db6af4ea76764219a6f';
const token = process.env.ANALYTICS_TOKEN;
if (!token) { console.error('Set ANALYTICS_TOKEN first. In PowerShell: $env:ANALYTICS_TOKEN="..."'); process.exit(1); }
const days = Math.max(1, Math.min(90, Number(process.argv.find((a) => /^\d+$/.test(a))) || 30));

// node usage.mjs 7 --queries   writes dotazy.json with the arguments of the real tool calls (private).
if (process.argv.includes('--queries')) {
  const rows = await runSql(acct, token, queriesSql(days));
  writeFileSync('dotazy.json', JSON.stringify(rows, null, 2));
  console.log(`dotazy.json: ${rows.length} calls with arguments, last ${days} days`);
  process.exit(0);
}
const r = await usageReport(acct, token, days);

const table = (title, rows) => {
  console.log(`\n${title}`);
  if (!rows.length) return console.log('  (no data yet)');
  for (const row of rows) console.log('  ' + Object.values(row).map((v, i) => String(v).padEnd(i ? 10 : 28)).join(''));
};
console.log(`mTOR Atlas MCP usage, last ${days} days: ${r.totals.tool_calls} tool calls, ${r.totals.connections} connections`);
table('Tool calls by tool (calls, errors, tool_errors, avg ms)', r.by_tool);
table('Connections (initialize) by client name', r.by_client_name);
table('Tool calls by client family (User-Agent)', r.by_client_family);
table('Per day (connections, tool calls)', r.by_day);
