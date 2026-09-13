/* Smoke-test a served page's JavaScript the way a browser would run it.

   WHY THIS EXISTS
   /circa shipped broken and my own harness passed it. The harness returned a
   fake element for every getElementById, so a missing element never threw. A
   real browser returns null, and the shared core's last line --
   renderEntries();load(); -- walked straight into it. Because the core and the
   page script share one <script> block, that single TypeError killed
   everything after it, and the page sat on "Loading..." with its own code
   never reached.

   So the rule here: getElementById returns null unless the id is really in the
   HTML, exactly like the browser. Anything thrown while the script body runs
   is a failure.

   Network is stubbed with a promise that never settles. The bug being guarded
   against is synchronous, and stubbing this way keeps the test offline and
   deterministic.

   Usage: node tests/check_pages.js page1.html [page2.html ...]
*/
const fs = require('fs');

function idsIn(html) {
  const out = new Set();
  for (const m of html.matchAll(/\bid="([^"]+)"/g)) out.add(m[1]);
  return out;
}

function scriptsIn(html) {
  return [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
}

function runPage(file) {
  const html = fs.readFileSync(file, 'utf8');
  const ids = idsIn(html);
  const made = {};

  const el = id => ({
    id, innerHTML: '', textContent: '', className: '', value: '', hidden: false,
    style: {}, onclick: null, onchange: null, oninput: null,
    classList: { add() {}, remove() {}, toggle() {} },
    setAttribute() {}, removeAttribute() {}, getAttribute: () => null,
    addEventListener() {}, appendChild() {}, querySelectorAll: () => [],
  });

  global.document = {
    // null for anything not actually in the markup — the whole point
    getElementById: id => (ids.has(id) ? (made[id] || (made[id] = el(id))) : null),
    querySelectorAll: () => [],
    querySelector: () => null,
    addEventListener() {},
    createElement: () => el('made'),
    documentElement: {
      setAttribute() {}, removeAttribute() {}, getAttribute: () => null,
    },
  };
  global.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
  global.window = { matchMedia: () => ({ matches: false }),
                    performance: { now: () => 0 }, addEventListener() {} };
  global.matchMedia = global.window.matchMedia;
  global.performance = global.window.performance;
  global.setInterval = () => 0;
  global.setTimeout = () => 0;
  global.fetch = () => new Promise(() => {});   // never settles, stays offline

  const name = file.split('/').pop();
  try {
    for (const src of scriptsIn(html)) eval(src);
  } catch (e) {
    console.log(`FAIL ${name}: ${e.constructor.name}: ${e.message}`);
    return false;
  }
  console.log(`ok   ${name}`);
  return true;
}

let bad = 0;
for (const f of process.argv.slice(2)) if (!runPage(f)) bad++;
console.log(bad ? `${bad} page(s) threw` : 'all pages ran clean');
process.exit(bad ? 1 : 0);
