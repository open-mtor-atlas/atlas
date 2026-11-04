// Aggregate usage queries over the Workers Analytics Engine dataset written by
// recordUsage() in index.js. Shared by the Worker's /stats endpoint and by
// ../usage.mjs. Only aggregates leave this module: counts per tool, per
// client name, per client family and per day.
// errors      = the server answered with a protocol-level error (invalid request or arguments).
// tool_errors = the tool ran and reported a failure, mostly "not found" for an unknown id.
// no_args     = the tool was called with no arguments at all (scanners); counted apart from tool_errors.
export const DATASET = 'mtor_atlas_mcp_usage';

export function usageQueries(days) {
  const since = `timestamp > NOW() - INTERVAL '${days}' DAY`;
  return {
    by_tool: `
      SELECT blob2 AS tool, SUM(_sample_interval) AS calls,
             SUM(if(blob5 = 'error', _sample_interval, 0)) AS errors,
             SUM(if(blob5 = 'tool-error', _sample_interval, 0)) AS tool_errors,
             SUM(if(blob5 = 'no-args', _sample_interval, 0)) AS no_args, ROUND(AVG(double2)) AS avg_ms
      FROM ${DATASET} WHERE blob1 = 'tools/call' AND ${since} GROUP BY tool ORDER BY calls DESC`,
    by_client_name: `
      SELECT blob3 AS client, SUM(_sample_interval) AS connections
      FROM ${DATASET} WHERE blob1 = 'initialize' AND ${since} GROUP BY client ORDER BY connections DESC LIMIT 20`,
    by_client_family: `
      SELECT blob4 AS family, SUM(_sample_interval) AS calls
      FROM ${DATASET} WHERE blob1 = 'tools/call' AND ${since} GROUP BY family ORDER BY calls DESC`,
    by_day: `
      SELECT toStartOfInterval(timestamp, INTERVAL '1' DAY) AS day,
             SUM(if(blob1 = 'initialize', _sample_interval, 0)) AS connections,
             SUM(if(blob1 = 'tools/call', _sample_interval, 0)) AS tool_calls
      FROM ${DATASET} WHERE ${since} GROUP BY day ORDER BY day DESC`,
  };
}

// Distinct anonymous users per day and client family. blob7 holds a salted hash of the host's own
// anonymous user id (only hosts that send one, today ChatGPT / Codex plugins). Only counts leave
// this module; the hashes themselves are never returned.
export function usersSql(days) {
  return `
    SELECT toStartOfInterval(timestamp, INTERVAL '1' DAY) AS day, blob4 AS family, blob7 AS user, SUM(_sample_interval) AS calls
    FROM ${DATASET} WHERE blob1 = 'tools/call' AND blob7 != '' AND blob7 != '-'
      AND timestamp > NOW() - INTERVAL '${days}' DAY GROUP BY day, family, user`;
}

function countUsers(rows) {
  const perDay = new Map();
  const total = new Map();
  for (const r of rows) {
    const k = `${r.day}|${r.family}`;
    if (!perDay.has(k)) perDay.set(k, { day: r.day, family: r.family, users: new Set(), calls: 0 });
    const d = perDay.get(k);
    d.users.add(r.user); d.calls += Number(r.calls) || 0;
    if (!total.has(r.family)) total.set(r.family, new Set());
    total.get(r.family).add(r.user);
  }
  return {
    note: 'Distinct anonymous users, only for hosts that send an anonymous user id (ChatGPT / Codex plugins). Counted since 4 Nov 2026.',
    by_day: [...perDay.values()].map((d) => ({ day: d.day, family: d.family, users: d.users.size, calls: d.calls }))
      .sort((a, b) => String(b.day).localeCompare(String(a.day))),
    in_period: Object.fromEntries([...total].map(([f, s]) => [f, s.size])),
  };
}

// Private query log: the arguments of real tool calls (not probes), newest first.
// Deliberately NOT part of usageReport(), so the public /stats never shows it.
export function queriesSql(days) {
  return `
    SELECT timestamp, blob2 AS tool, blob4 AS family, blob5 AS outcome, blob6 AS args
    FROM ${DATASET} WHERE blob1 = 'tools/call' AND NOT startsWith(blob2, '__') AND blob6 != ''
      AND timestamp > NOW() - INTERVAL '${days}' DAY ORDER BY timestamp DESC LIMIT 1000`;
}

export async function runSql(accountId, token, sql) {
  const r = await fetch(`https://api.cloudflare.com/client/v4/accounts/${accountId}/analytics_engine/sql`, {
    method: 'POST', headers: { authorization: `Bearer ${token}` }, body: sql,
  });
  const txt = await r.text();
  if (!r.ok) throw new Error(`Analytics Engine ${r.status}: ${txt.slice(0, 300)}`);
  // Analytics Engine returns numbers as strings; convert the numeric columns.
  return JSON.parse(txt).data.map((row) => Object.fromEntries(Object.entries(row).map(
    ([k, v]) => [k, typeof v === 'string' && v !== '' && !Number.isNaN(Number(v)) && k !== 'tool' && k !== 'client' && k !== 'family' ? Number(v) : v])));
}

export async function usageReport(accountId, token, days) {
  const out = { days, generated_at: new Date().toISOString() };
  for (const [name, sql] of Object.entries(usageQueries(days))) out[name] = await runSql(accountId, token, sql);
  try { out.unique_users = countUsers(await runSql(accountId, token, usersSql(days))); }
  catch { out.unique_users = null; /* older rows have no blob7; never fail the whole report */ }
  out.totals = {
    tool_calls: out.by_tool.reduce((a, r) => a + (r.calls || 0), 0),
    connections: out.by_client_name.reduce((a, r) => a + (r.connections || 0), 0),
  };
  return out;
}
