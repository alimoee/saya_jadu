// تست موتور سایت سایا — persistent (بدون وابستگی به /tmp)
// اجرا: node /home/user/saya/test-site.js
const fs = require('fs');
const vm = require('vm');
const path = '/home/user/ecommerce-shots/site/index.html';
const html = fs.readFileSync(path, 'utf8');

let pass = 0, fail = 0;
function check(name, cond) {
  console.log((cond ? '  PASS ' : '  FAIL ') + name);
  cond ? pass++ : fail++;
}

// ── 1) ساختار HTML / perf / SEO ─────────────────────────
check('no inlined videos', !html.includes('data:video'));
check('no inlined poster', !html.includes('data:image/jpeg;base64,'));
check('hero ref x2', (html.match(/assets\/hero\.mp4/g) || []).length === 2);
check('hero video (manager) ref', /id="tradeHeroVid"[\s\S]{0,160}?<source src="assets\/hero\.mp4"/.test(html));
check('trade image map', (html.match(/assets\/trades\/\w+\.jpg/g) || []).length >= 8);
check('poster ref', html.includes('poster="assets/poster.jpg"'));
check('og:image intact (placeholder or live url)', html.includes('content="__OG_BASE__/og-image.jpg"') || html.includes('og-image.jpg'));
check('price/faq/cta sections', ['id="price"','id="faq"','id="cta"'].every(s => html.includes(s)));

const ldMatch = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
check('json-ld present', !!ldMatch);
let ld = null;
try { ld = JSON.parse(ldMatch[1]); } catch (e) {}
check('json-ld valid', !!ld);
if (ld) {
  const types = ld['@graph'].map(x => x['@type']);
  check('json-ld types', types.includes('WebSite') && types.includes('SoftwareApplication') && types.includes('FAQPage'));
  const faq = ld['@graph'].find(x => x['@type'] === 'FAQPage');
  check('faq 8 items', faq.mainEntity.length === 8);
  const app = ld['@graph'].find(x => x['@type'] === 'SoftwareApplication');
  check('offers 3', app.offers.offerCount === '3' || app.offers.offers.length === 3);
  check('price range 2.1M-15M (v3)', app.offers.lowPrice === '2100000' && app.offers.highPrice === '15000000');
}

// ── 2) موتور JS ─────────────────────────────────────────
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
check('one engine script', scripts.length === 1);
const code = scripts[0][1];

function makeEl(id) {
  return {
    id, innerHTML: '', textContent: '', value: '', style: {}, dataset: {},
    children: [], classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    setAttribute(){}, getAttribute(){ return null; }, removeAttribute(){},
    appendChild(c){ this.children.push(c); return c; }, append(c){ this.children.push(c); return c; },
    remove(){}, insertAdjacentHTML(){},
    querySelector(){ return makeEl('q'); }, querySelectorAll(){ return []; },
    addEventListener(){}, removeEventListener(){}, focus(){}, blur(){}, click(){},
    scrollIntoView(){}, play(){ return Promise.resolve(); }, pause(){},
    getContext(){ return { fillRect(){}, clearRect(){}, beginPath(){}, arc(){}, fill(){}, stroke(){} }; },
  };
}
const els = {};
const sandbox = {
  console,
  setTimeout: () => 0, setInterval: () => 0, clearTimeout(){}, clearInterval(){},
  document: {
    getElementById(id){ return els[id] || (els[id] = makeEl(id)); },
    querySelector(){ return makeEl('qs'); }, querySelectorAll(){ return []; },
    createElement(t){ return makeEl(t); }, addEventListener(){},
    body: makeEl('body'), head: makeEl('head'),
  },
  navigator: { userAgent: 'node-test' },
  localStorage: { getItem(){ return null; }, setItem(){}, removeItem(){} },
  speechSynthesis: { speak(){}, cancel(){}, getVoices(){ return []; } },
  URL, Blob: class {},
  fetch: () => Promise.reject(new Error('offline')),
};
sandbox.window = sandbox;
vm.createContext(sandbox);
let threw = null;
try { vm.runInContext(code, sandbox, { timeout: 10000 }); } catch (e) { threw = e; }
check('engine executes clean', threw === null);
if (threw) { console.log('  error:', threw.message); }

const S = sandbox;
check('TRADES 12', S.TRADES && Object.keys(S.TRADES).length === 12);
if (S.TRADES) {
  const rest = S.TRADES.restoran;
  check('restoran faktura 68,265,000', rest && rest.inv && (rest.inv.total === 68265000 ||
    rest.inv.lines.reduce((s, l) => s + l[1] * l[2], 0) === 68265000));
  check('restoran faktura no 10457', rest && rest.inv && String(rest.inv.no) === '10457');
  const abzar = S.TRADES.abzar;
  const abzarTotal = abzar && abzar.inv ? (abzar.inv.total ||
    abzar.inv.lines.reduce((s, l) => s + l[1] * l[2], 0)) : 0;
  check('abzar total 108,600,000', abzarTotal === 108600000);
}
if (typeof S.fmt === 'function') {
  const x = S.fmt('108600000');
  check('fmt adds sep', x.includes('٬'));
  check('fmt idempotent', S.fmt(x) === x);
  check('fmt persian digits', /[\u06F0-\u06F9]/.test(x));
}
if (typeof S.g2j === 'function') {
  const a = S.g2j(2026, 9, 14), b = S.g2j(2026, 10, 14);
  check('g2j 2026-09-14 = 1405/6/23', JSON.stringify(a) === '[1405,6,23]');
  check('g2j 2026-10-14 = 1405/7/22', JSON.stringify(b) === '[1405,7,22]');
}
check('flows exist', ['cardFlow','creditFlow','oldCustomerFlow','missedCallFlow'].every(f => typeof S[f] === 'function'));
check('greetText منشی دیجیتال', typeof S.greetText === 'function' ? S.greetText().includes('منشی دیجیتال') : (typeof S.greetText === 'string' && S.greetText.includes('منشی دیجیتال')));
check('lamp.open exists', S.lamp && typeof S.lamp.open === 'function');
check('RULES 13', Array.isArray(S.RULES) && S.RULES.length === 13);
check('CHIPS 13', Array.isArray(S.CHIPS) && S.CHIPS.length === 13);

console.log(`\nRESULT: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
