#!/usr/bin/env node
/*
 * prerender_tabs.js -- crawler musí vidět totéž co člověk.
 *
 * Problém, který tohle řeší: #questionsView a #eventsView se plnily až za běhu
 * (renderGaps() / renderEvents() přepsaly innerHTML na konci načtení stránky).
 * Pro GPTBot, ClaudeBot, PerplexityBot a Common Crawl -- které JS zpravidla
 * nespouštějí -- byly ty dva taby prázdné, nebo hůř: v Open Questions zůstal
 * ručně psaný fallback Q1-Q7, který se s živým obsahem H1-H10 vůbec neshodoval.
 * Crawler tedy viděl JINÝ obsah než člověk, což je horší než nevidět nic.
 *
 * Řešení bez duplikace renderovací logiky: tenhle skript spustí PŘESNĚ TY SAMÉ
 * funkce renderGaps() a renderEvents() z index.html v Node (s minimálním DOM
 * stubem) a výsledek zapíše staticky mezi PRERENDER značky. Za běhu se pak JS
 * pustí znovu a nahradí obsah týmž řetězcem -- žádný vizuální rozdíl, ale
 * v HTML zdroji už ten text je.
 *
 * Jediný zdroj pravdy zůstává ATLAS_GAPS / ATLAS_FINDINGS / ATLAS_EVENTS
 * a JS funkce v index.html. Tenhle skript nic vlastního nerenderuje.
 *
 *   node prerender_tabs.js            -- vygeneruje a zapíše
 *   node prerender_tabs.js --check    -- jen ověří čerstvost, nezapisuje
 *                                        (návratový kód 1 = zastaralé)
 *
 * POZOR: pouští se PO bake_from_mcp.py (ten přepisuje ATLAS_* pole),
 * jinak zapečeš starý obsah.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HERE = path.dirname(path.resolve(__filename));
const FILE = path.join(HERE, 'index.html');
const CHECK = process.argv.includes('--check');

/* Taby, které se plní až za běhu. Klíč = id divu, hodnota = jméno render funkce. */
const TABS = [
  { id: 'questionsView', fn: 'renderGaps' },
  { id: 'eventsView', fn: 'renderEvents' },
];

function fail(msg) {
  console.error('CHYBA: ' + msg);
  process.exit(1);
}

/* ---- 1. načíst index.html ---------------------------------------------- */
let html = fs.readFileSync(FILE, 'utf8');

/* ---- 2. posbírat data + render funkce ze samotné stránky ---------------- */
function grabConst(name) {
  const m = html.match(new RegExp('const ' + name + ' = \\[[\\s\\S]*?\\];'));
  if (!m) fail('nenalezeno ' + name + ' v index.html');
  return m[0];
}
function grabFn(name) {
  // funkce jsou na začátku řádku a končí "\n}" na začátku řádku
  const m = html.match(new RegExp('^function ' + name + '\\(\\)\\{[\\s\\S]*?\\n\\}', 'm'));
  if (!m) fail('nenalezena funkce ' + name + '() v index.html');
  return m[0];
}

/* ---- 3. spustit je v izolovaném kontextu s DOM stubem ------------------- */
function render(tab) {
  const el = { innerHTML: '' };
  const sandbox = {
    document: {
      getElementById: (id) => (id === tab.id ? el : null),
    },
    console,
    Date,
    encodeURIComponent,
    parseInt,
    parseFloat,
  };
  vm.createContext(sandbox);
  const src = [
    grabConst('ATLAS_GAPS'),
    grabConst('ATLAS_FINDINGS'),
    grabConst('ATLAS_EVENTS'),
    grabFn(tab.fn),
    tab.fn + '();',
  ].join('\n');
  try {
    vm.runInContext(src, sandbox, { timeout: 10000 });
  } catch (e) {
    fail(tab.fn + '() spadla při prerenderu: ' + e.message);
  }
  if (!el.innerHTML || el.innerHTML.length < 400) {
    fail(tab.fn + '() vrátila podezřele málo obsahu (' + el.innerHTML.length + ' znaků)');
  }
  return el.innerHTML;
}

/* ---- 4. vložit mezi značky --------------------------------------------- */
function inject(tabId, body) {
  const open = '<!--PRERENDER:' + tabId + '-->';
  const close = '<!--/PRERENDER:' + tabId + '-->';
  const i = html.indexOf(open);
  const j = html.indexOf(close);
  if (i === -1 || j === -1 || j < i) {
    fail('značky ' + open + ' / ' + close + ' nenalezeny v index.html — '
       + 'prerender nemá kam zapsat (obnov je uvnitř <div id="' + tabId + '">)');
  }
  const current = html.slice(i + open.length, j);
  const changed = current.trim() !== body.trim();
  if (!CHECK && changed) {
    html = html.slice(0, i + open.length) + body + html.slice(j);
  }
  return { changed, bytes: body.length };
}

/* ---- 5. atomický zápis s ověřením (index.html je ~1,5 MB) -------------- */
function writeVerified(target, content) {
  const tmp = target + '.tmp';
  const fd = fs.openSync(tmp, 'w');
  fs.writeSync(fd, content, 0, 'utf8');
  fs.fsyncSync(fd);
  fs.closeSync(fd);
  const back = fs.readFileSync(tmp, 'utf8');
  if (back.length !== content.length || !back.trimEnd().endsWith('</html>')) {
    fs.unlinkSync(tmp);
    fail('ověření zápisu selhalo (uříznutý konec souboru) — NEZAPSÁNO');
  }
  fs.renameSync(tmp, target);
}

/* ---- běh --------------------------------------------------------------- */
let stale = false;
for (const tab of TABS) {
  const body = render(tab);
  const r = inject(tab.id, body);
  if (r.changed) stale = true;
  console.log(
    '  ' + tab.id.padEnd(15) + ' ' + String(r.bytes).padStart(7) + ' B  '
    + (r.changed ? (CHECK ? 'ZASTARALÉ' : 'aktualizováno') : 'beze změny')
  );
}

if (CHECK) {
  if (stale) {
    console.error('\nCHYBA: prerenderovaný obsah neodpovídá tomu, co JS vykreslí za běhu.');
    console.error('Crawler by viděl jiný text než člověk. Spusť: node prerender_tabs.js');
    process.exit(1);
  }
  console.log('\nprerender je aktuální.');
} else {
  if (stale) {
    writeVerified(FILE, html);
    console.log('\nindex.html přepsán a ověřen (' + html.length + ' znaků).');
  } else {
    console.log('\nbeze změny, nezapisuji.');
  }
}
