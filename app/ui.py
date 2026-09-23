PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Insider Buy Screener</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap">
<style>
:root{
 --paper:#f3f4f8;--sheet:#ffffff;--sheet-2:#f8f9fc;--ink:#1b1d33;--ink-2:#474b66;--muted:#747894;--rule:#e2e4ed;--rule-2:#eef0f5;
 --indigo:#2f3c9e;--indigo-ink:#ffffff;--indigo-soft:#e9ecfa;--marigold:#e8a317;--marigold-text:#8a5b00;--marigold-soft:#fdf1d6;
 --pos:#12775a;--pos-soft:#e5f3ed;--neg:#b42318;--neg-soft:#fcebe9;--track:#e6e8f0;
 --serif:"Newsreader",Georgia,"Times New Roman",serif;--sans:"Hanken Grotesk",system-ui,-apple-system,"Segoe UI",sans-serif;
 --shadow:0 1px 2px rgba(27,29,51,.06),0 8px 24px -12px rgba(27,29,51,.18)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --paper:#12142a;--sheet:#1a1d36;--sheet-2:#161931;--ink:#eceef8;--ink-2:#c0c3da;--muted:#8e92ad;--rule:#2b2f50;--rule-2:#23274459;
 --indigo:#a3afff;--indigo-ink:#12142a;--indigo-soft:#262c5c;--marigold:#f2b640;--marigold-text:#f5c86a;--marigold-soft:#3b2f12;
 --pos:#52c99d;--pos-soft:#17332b;--neg:#ff8b7d;--neg-soft:#3d2025;--track:#2a2e4d;--shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px -14px rgba(0,0,0,.6)}}
:root[data-theme="dark"]{color-scheme:dark;
 --paper:#12142a;--sheet:#1a1d36;--sheet-2:#161931;--ink:#eceef8;--ink-2:#c0c3da;--muted:#8e92ad;--rule:#2b2f50;--rule-2:#23274459;
 --indigo:#a3afff;--indigo-ink:#12142a;--indigo-soft:#262c5c;--marigold:#f2b640;--marigold-text:#f5c86a;--marigold-soft:#3b2f12;
 --pos:#52c99d;--pos-soft:#17332b;--neg:#ff8b7d;--neg-soft:#3d2025;--track:#2a2e4d;--shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px -14px rgba(0,0,0,.6)}

*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 var(--sans);font-variant-numeric:tabular-nums;padding-inline:20px;padding-block:0 64px}
.wrap{max-width:1200px;margin:0 auto}
button,input,select{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--indigo);outline-offset:2px;border-radius:6px}
a{color:var(--indigo)}

/* top bar */
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;padding-block:22px 0}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:15px;letter-spacing:-.005em}
.brand svg{flex:none}
.actions{display:flex;gap:8px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:8px;font-weight:600;font-size:14px;padding:9px 16px;border-radius:999px;border:1px solid var(--rule);
 background:var(--sheet);color:var(--ink);text-decoration:none;cursor:pointer;transition:background .15s,border-color .15s,transform .1s}
.btn:hover{border-color:var(--muted)}
.btn:active{transform:translateY(1px)}
.btn.primary{background:var(--indigo);border-color:var(--indigo);color:var(--indigo-ink)}
.btn.primary:hover{filter:brightness(1.08)}
.btn[disabled],.btn[aria-disabled="true"]{opacity:.45;pointer-events:none}
.btn svg{width:16px;height:16px}
.spin{animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* briefing */
.brief{padding-block:44px 30px;max-width:900px}
.brief h1{font:500 clamp(34px,5.4vw,56px)/1.05 var(--serif);letter-spacing:-.02em;margin:0;text-wrap:balance}
.brief h1 .n{font-variant-numeric:lining-nums tabular-nums}
.clauses{font:400 clamp(19px,2.3vw,24px)/1.5 var(--serif);color:var(--ink-2);margin:14px 0 0;text-wrap:pretty}
.clause{all:unset;cursor:pointer;color:var(--ink);border-radius:3px;padding:0 2px;margin:0 -2px;
 background:linear-gradient(transparent 62%,var(--hl,var(--indigo-soft)) 62%);background-size:100% 100%;transition:background-size .25s ease}
.clause:hover{--hl:var(--marigold-soft)}
.clause[aria-pressed="true"]{--hl:var(--marigold);background:linear-gradient(transparent 55%,color-mix(in srgb,var(--marigold) 55%,transparent) 55%)}
.clause:focus-visible{outline:2px solid var(--indigo);outline-offset:2px}
.clause.bad{--hl:var(--neg-soft)}
.clause.quiet{background:none;color:var(--ink-2);cursor:default}
.stamp{margin-top:18px;font-size:13.5px;color:var(--muted)}
.stamp b{color:var(--ink-2);font-weight:600}

/* scanning */
.scan{max-width:640px;padding-block:44px 30px}
.scan h1{font:500 clamp(30px,4.6vw,46px)/1.1 var(--serif);letter-spacing:-.02em;margin:0 0 20px}
.steps{list-style:none;margin:0;padding:0;display:grid;gap:12px}
.steps li{display:grid;grid-template-columns:28px 1fr;gap:12px;align-items:start;color:var(--muted)}
.steps .dot{width:28px;height:28px;border-radius:50%;border:1.5px solid var(--rule);display:grid;place-items:center;font-size:13px;font-weight:600;background:var(--sheet)}
.steps li.on{color:var(--ink)} .steps li.on .dot{border-color:var(--indigo);color:var(--indigo)}
.steps li.done{color:var(--ink-2)} .steps li.done .dot{background:var(--indigo);border-color:var(--indigo);color:var(--indigo-ink)}
.steps .t{font-weight:600;padding-top:3px} .steps .d{font-size:13.5px;color:var(--muted);margin-top:2px;min-height:1.4em}
.track{height:4px;background:var(--track);border-radius:4px;overflow:hidden;margin:22px 0 10px}
.track i{display:block;height:100%;width:0;background:var(--indigo);border-radius:4px;transition:width .5s ease}
.hint{font-size:13.5px;color:var(--muted)}
.error{margin:28px 0 0;max-width:720px;background:var(--neg-soft);border-radius:14px;padding:16px 18px;color:var(--ink)}
.error b{color:var(--neg)}

/* toolbar */
.bar{display:flex;align-items:flex-end;justify-content:space-between;gap:12px 20px;flex-wrap:wrap;border-bottom:1px solid var(--rule)}
.tabs{display:flex;gap:22px}
.tab{all:unset;cursor:pointer;padding:10px 0 12px;font-weight:600;font-size:14.5px;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-1px}
.tab:hover{color:var(--ink-2)}
.tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--ink)}
.tab .c{font-weight:500;color:var(--muted);margin-left:4px}
.tab:focus-visible{outline:2px solid var(--indigo);outline-offset:4px}
.tools{display:flex;gap:8px;align-items:center;padding-bottom:8px;flex-wrap:wrap}
.field{display:flex;align-items:center;gap:6px;background:var(--sheet);border:1px solid var(--rule);border-radius:999px;padding:6px 12px;font-size:13.5px;color:var(--muted)}
.field select,.field input{border:0;background:transparent;outline:0;font-size:13.5px;color:var(--ink)}
.field input{width:170px}
.field:focus-within{border-color:var(--indigo)}
.toggle{display:inline-flex;align-items:center;gap:8px;font-size:13.5px;color:var(--ink-2);cursor:pointer;padding:6px 4px;user-select:none}
.toggle input{accent-color:var(--indigo);width:15px;height:15px}

/* watchlist */
.sheet{background:var(--sheet);border-radius:18px;box-shadow:var(--shadow);margin-top:18px;overflow:hidden}
.cols,.row{display:grid;grid-template-columns:minmax(150px,1.05fr) minmax(240px,2.1fr) minmax(140px,1fr) minmax(150px,1fr) minmax(120px,.9fr);gap:20px;padding:16px 22px}
.cols{font-size:12.5px;color:var(--muted);font-weight:500;padding-block:12px;border-bottom:1px solid var(--rule)}
.item{border-bottom:1px solid var(--rule-2)}
.item:last-child{border-bottom:0}
.row{cursor:pointer;align-items:start;transition:background .12s}
.row:hover{background:var(--sheet-2)}
.item.open>.row{background:var(--sheet-2)}
.sym{font-weight:700;font-size:15.5px;letter-spacing:.01em;display:flex;align-items:center;gap:8px}
.newdot{width:8px;height:8px;border-radius:50%;background:var(--marigold);box-shadow:0 0 0 3px var(--marigold-soft)}
.co{font:italic 400 15px/1.3 var(--serif);color:var(--ink-2);margin-top:2px}
.sub{font-size:13px;color:var(--muted);margin-top:4px}
.who{font-size:14.5px;color:var(--ink);line-height:1.45}
.who .role{color:var(--muted)}
.who .stake{white-space:nowrap}
.who .more{color:var(--muted)}
.buy{font-size:13.5px;color:var(--ink-2);margin-top:4px}
.px{font-weight:600;font-size:17px}
.chg{font-size:13.5px;margin-top:2px}
.pos{color:var(--pos)} .neg{color:var(--neg)} .mut{color:var(--muted)}
.win{font-size:13.5px;color:var(--ink-2)}
.win b{font-weight:600;color:var(--ink);font-size:15px}
.wbar{position:relative;height:6px;border-radius:6px;background:var(--track);margin-top:8px;overflow:hidden}
.wbar i{position:absolute;inset:0 auto 0 0;background:var(--indigo);border-radius:6px}
.wbar.new i{background:var(--marigold)}
.wbar.end i{background:var(--muted)}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.tag{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;padding:3px 10px 3px 8px;border-radius:999px;background:var(--marigold-soft);color:var(--marigold-text);white-space:nowrap}
.tag::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.tag.good{background:var(--pos-soft);color:var(--pos)}
.tag.bad{background:var(--neg-soft);color:var(--neg)}
.tag.info{background:var(--indigo-soft);color:var(--indigo)}
.chev{justify-self:end;color:var(--muted);transition:transform .2s}

/* detail */
.detail{display:grid;grid-template-rows:0fr;transition:grid-template-rows .28s ease}
.item.open .detail{grid-template-rows:1fr}
.detail>div{overflow:hidden}
.dpad{padding:6px 22px 24px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.25fr);gap:28px}
.dpad h3{font:500 19px/1.3 var(--serif);margin:12px 0 10px}
.people{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.people li{display:grid;grid-template-columns:1fr auto;gap:4px 12px;font-size:14px}
.people .nm{font-weight:600}
.people .cat{grid-column:1;color:var(--muted);font-size:13px}
.people .st{grid-row:1 / span 2;grid-column:2;text-align:right;font-size:13.5px}
.people .st small{display:block;color:var(--pos);font-weight:600}
.facts{display:grid;grid-template-columns:auto 1fr;gap:6px 18px;font-size:14px;margin:0}
.facts dt{color:var(--muted)} .facts dd{margin:0}
.flags{margin:14px 0 0;padding:0;list-style:none;display:grid;gap:6px;font-size:13.5px;color:var(--ink-2)}
.flags li{display:flex;gap:8px} .flags li::before{content:"";flex:none;width:6px;height:6px;border-radius:50%;background:var(--marigold);margin-top:8px}
.flags li.bad::before{background:var(--neg)}
.mini{width:100%;border-collapse:collapse;font-size:13px}
.mini th{font-weight:500;color:var(--muted);text-align:left;padding:6px 8px;border-bottom:1px solid var(--rule)}
.mini td{padding:7px 8px;border-bottom:1px solid var(--rule-2);vertical-align:top}
.mini td.r,.mini th.r{text-align:right;white-space:nowrap}
.mini tr:last-child td{border-bottom:0}
.tscroll{overflow-x:auto;border:1px solid var(--rule);border-radius:12px;background:var(--sheet)}
.links{display:flex;gap:16px;margin-top:16px;font-size:14px;font-weight:600}
.links a{text-decoration:none} .links a:hover{text-decoration:underline}

.empty{padding:44px 22px;text-align:center;color:var(--muted)}
.empty b{display:block;font:500 22px/1.3 var(--serif);color:var(--ink);margin-bottom:6px}
.empty button{margin-top:14px}

/* other tabs */
.plain{background:var(--sheet);border-radius:18px;box-shadow:var(--shadow);margin-top:18px;overflow:hidden}
.plain .lede{padding:18px 22px 4px;margin:0;color:var(--ink-2);font-size:14.5px;max-width:78ch}
.near{width:100%;border-collapse:collapse;font-size:14px}
.near th{font-weight:500;font-size:12.5px;color:var(--muted);text-align:left;padding:14px 22px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
.near td{padding:14px 22px;border-bottom:1px solid var(--rule-2);vertical-align:top}
.near td.r,.near th.r{text-align:right;white-space:nowrap}
.near tr:last-child td{border-bottom:0}
.near .why{color:var(--ink-2);font-size:13.5px;max-width:34ch}
.rules{padding:10px 22px 22px;display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:4px 36px}
.rules div{display:grid;grid-template-columns:22px 1fr;gap:10px;padding:14px 0;border-bottom:1px solid var(--rule-2)}
.rules svg{color:var(--pos);margin-top:3px}
.rules b{display:block;font-weight:600;margin-bottom:2px}
.rules span{color:var(--ink-2);font-size:14px}
.note{padding:18px 22px;background:var(--sheet-2);color:var(--ink-2);font-size:14px;border-top:1px solid var(--rule)}
.foot{font-size:13px;color:var(--muted);margin-top:22px;max-width:90ch}

@media (max-width:900px){
 .cols{display:none}
 .row{grid-template-columns:1fr auto;gap:10px 16px;padding:16px 18px}
 .row>.c-who{grid-column:1 / -1}
 .row>.c-px{grid-column:1} .row>.c-win{grid-column:2;min-width:140px}
 .row>.c-tag{grid-column:1 / -1}
 .chev{display:none}
 .dpad{grid-template-columns:1fr;padding:4px 18px 22px;gap:8px}
 .near thead{display:none}
 .near tr{display:grid;grid-template-columns:1fr auto;gap:4px 12px;padding:14px 18px;border-bottom:1px solid var(--rule-2)}
 .near td{padding:0;border:0}
 .near td.why,.near td.buyers{grid-column:1 / -1}
}
@media (max-width:520px){body{padding-inline:14px}.field input{width:120px}.brief{padding-block:32px 22px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
</head>
<body>
<div class="wrap">
<header class="top">
 <div class="brand">
  <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><rect width="26" height="26" rx="8" fill="var(--indigo)"/><path d="M7 17.5l4-4.5 3 3 5-6.5" fill="none" stroke="var(--indigo-ink)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="19" cy="9.5" r="2.2" fill="var(--marigold)"/></svg>
  Insider Buy Screener
 </div>
 <div class="actions">
  <a class="btn" id="xl" href="/api/excel" aria-disabled="true">
   <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2v8M4.5 6.5 8 10l3.5-3.5M3 13h10"/></svg>Download Excel</a>
  <button class="btn primary" id="run" type="button">
   <svg id="runic" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M13.5 8A5.5 5.5 0 1 1 11.9 4.1M13.5 2.5v3h-3"/></svg><span id="runtx">Scan again</span></button>
 </div>
</header>

<section class="scan" id="scan" hidden aria-live="polite">
 <h1>Checking NSE for insider buys</h1>
 <ol class="steps">
  <li data-s="0"><span class="dot">1</span><div><div class="t">Daily prices</div><div class="d"></div></div></li>
  <li data-s="1"><span class="dot">2</span><div><div class="t">Insider filings</div><div class="d"></div></div></li>
  <li data-s="2"><span class="dot">3</span><div><div class="t">Applying the rules</div><div class="d"></div></div></li>
 </ol>
 <div class="track"><i id="pbar"></i></div>
 <p class="hint">The first scan of the day takes 3–6 minutes. After that, opening the app today shows this scan straight away.</p>
</section>

<div class="error" id="err" hidden role="alert"></div>

<main id="main" hidden>
 <section class="brief" aria-live="polite">
  <h1 id="headline"></h1>
  <p class="clauses" id="clauses"></p>
  <p class="stamp" id="stamp"></p>
 </section>

 <div class="bar">
  <div class="tabs" role="tablist">
   <button class="tab" role="tab" id="tab-w" aria-selected="true" aria-controls="p-w" type="button">Watchlist<span class="c" id="c-w"></span></button>
   <button class="tab" role="tab" id="tab-n" aria-selected="false" aria-controls="p-n" type="button">Didn't qualify<span class="c" id="c-n"></span></button>
   <button class="tab" role="tab" id="tab-r" aria-selected="false" aria-controls="p-r" type="button">Rules</button>
  </div>
  <div class="tools" id="tools">
   <label class="toggle"><input type="checkbox" id="clean"> Hide stocks with cautions</label>
   <label class="field">Sort <select id="sort" aria-label="Sort by">
    <option value="new">Newest disclosure</option><option value="win">Most time left</option>
    <option value="near">Closest to insider price</option><option value="val">Largest purchase</option></select></label>
   <label class="field"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3" stroke-linecap="round"/></svg>
    <input type="search" id="q" placeholder="Find a stock" aria-label="Find a stock"></label>
  </div>
 </div>

 <section id="p-w" role="tabpanel" aria-labelledby="tab-w">
  <div class="sheet">
   <div class="cols" aria-hidden="true"><span>Stock</span><span>Who bought</span><span>Price</span><span>Watch window</span><span>Status</span></div>
   <div id="list" role="list"></div>
  </div>
  <p class="foot">Click a stock to see everyone who bought, the other insider filings, and why it's flagged. These are candidates for your own entry setup, not recommendations.</p>
 </section>

 <section id="p-n" role="tabpanel" aria-labelledby="tab-n" hidden>
  <div class="plain">
   <p class="lede">The largest insider buys (₹1 crore and above) in the last 120 sessions that failed a rule. In the 2016–26 study, buys like these did not beat comparable stocks.</p>
   <table class="near"><thead><tr><th>Stock</th><th>Buyer</th><th class="r">Value</th><th class="r">Market cap</th><th>Why it's left out</th></tr></thead><tbody id="near"></tbody></table>
  </div>
 </section>

 <section id="p-r" role="tabpanel" aria-labelledby="tab-r" hidden>
  <div class="plain">
   <div class="rules" id="rules"></div>
   <div class="note">In the 2016–26 backtest these rules beat comparable stocks by about 15% a year after costs. Around 6% of that also showed up on random dates in the same stocks, so plan on roughly 9%. The worst fall was 66% in the 2018–20 small-cap crash, so hold 10–15 positions. This is research, not investment advice. Don't trade stocks where you are an insider or hold unpublished price-sensitive information.</div>
  </div>
 </section>
</main>
</div>

<script>
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
let DATA=null,FILTER='all',poll=null,OPEN=new Set();
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,d=1)=>v==null?'–':v.toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=(v,d=1)=>v==null?'–':(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),d)+'%';
const cls=v=>v==null?'mut':v>0?'pos':v<0?'neg':'mut';
const cr=v=>v==null?'–':'₹'+(v>=100?fmt(v,0):v>=10?fmt(v,1):fmt(v,2))+' cr';
const rs=v=>v==null?'–':'₹'+fmt(v,2);
const plural=(n,one,many)=>n===1?one:many;
const WORDS=['No','One','Two','Three','Four','Five','Six','Seven','Eight','Nine','Ten'];
const word=(n,cap)=>{const w=n<=10?WORDS[n]:String(n);return cap?w:w.toLowerCase()};
const ROLE={'Promoters':'promoter','Promoter':'promoter','Promoter and Director':'promoter & director','Promoter Group':'promoter group',
 'Immediate relative':'relative','Immediate Relative':'relative','Promoter Immediate Relative':"promoter's relative",'Director':'director',
 'Directors Immediate Relative':"director's relative",'KMP':'key manager','Key Managerial Personnel':'key manager'};
const role=c=>ROLE[c]||String(c||'insider').toLowerCase();
const isNew=s=>s.sessions_left>=116, ending=s=>s.sessions_left<=10;
const FLAGS=[[/exit/i,'Exit check','bad'],[/small ticket/i,'Small buy',''],[/5.10k/i,'₹5–10k cr size',''],[/far above/i,'Already ran up',''],
 [/nearly over/i,'Window ending',''],[/sold before/i,'Earlier insider sales',''],[/first personal/i,'New holder','']];
const flag=n=>{for(const[re,l,c]of FLAGS)if(re.test(n))return{l,c};return{l:n,c:''}};

async function status(){return (await fetch('/api/status')).json()}
async function start(){$('#err').hidden=true;await fetch('/api/scan',{method:'POST'});watch()}
function stage(p){return p<56?0:p<88?1:2}
function watch(){
 $('#run').disabled=true;$('#runic').classList.add('spin');$('#runtx').textContent='Scanning…';
 if(!DATA){$('#scan').hidden=false;$('#main').hidden=true}
 clearInterval(poll);
 const tick=async()=>{const s=await status();const st=stage(s.pct);
  $$('.steps li').forEach(li=>{const i=+li.dataset.s;li.className=i<st?'done':i===st?'on':'';li.querySelector('.d').textContent=i===st?s.msg:(i<st?'Done':'');
   li.querySelector('.dot').innerHTML=i<st?'<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m3.5 8.5 3 3 6-7"/></svg>':i+1});
  $('#pbar').style.width=s.pct+'%';
  if(DATA)$('#stamp').innerHTML=`<b>Scanning NSE again…</b> ${esc(s.msg)} (${s.pct}%)`;
  if(!s.running){clearInterval(poll);$('#run').disabled=false;$('#runic').classList.remove('spin');$('#runtx').textContent='Scan again';$('#scan').hidden=true;
   if(s.error){$('#err').hidden=false;$('#err').innerHTML=`<b>The scan stopped.</b> ${esc(s.error)} Check your internet connection, then choose Scan again.`;if(DATA){$('#main').hidden=false;stampLine()}}
   else if(s.has_result)load()}};
 tick();poll=setInterval(tick,1000)}
async function load(){const r=await fetch('/api/result');if(!r.ok)return;DATA=await r.json();render(true)}

function stampLine(){const m=DATA.meta;
 $('#stamp').innerHTML=`Prices up to <b>${esc(m.as_of)}</b>. Filings up to <b>${esc(m.latest_filing)}</b>. Last scanned <b>${esc(m.run_at)}</b>.`}
function countUp(el,n){if(matchMedia('(prefers-reduced-motion: reduce)').matches||n<2){el.textContent=n;return}
 const t0=performance.now(),d=650;const f=t=>{const k=Math.min(1,(t-t0)/d);el.textContent=Math.round(n*(1-Math.pow(1-k,3)));if(k<1)requestAnimationFrame(f)};requestAnimationFrame(f)}
function render(first){
 const S=DATA.signals;$('#main').hidden=false;$('#xl').setAttribute('aria-disabled','false');
 const nNew=S.filter(isNew).length,nPend=S.filter(s=>s.pending).length,nExit=S.filter(s=>s.exit_warning).length,nEnd=S.filter(ending).length;
 const h=$('#headline');
 if(!S.length)h.innerHTML='No stocks on watch right now.';
 else{h.innerHTML=`<span class="n" id="hn">${S.length}</span> ${plural(S.length,'stock','stocks')} on watch.`;if(first)countUp($('#hn'),S.length)}
 const c=[];
 const cl=(f,txt,extra='')=>`<button type="button" class="clause ${extra}" data-f="${f}" aria-pressed="${FILTER===f}">${txt}</button>`;
 if(S.length){
  c.push(nNew?cl('new',`${word(nNew,true)} ${plural(nNew,'is','are')} new this week`):'<span class="clause quiet">Nothing new this week</span>');
  if(nPend)c.push(cl('pend',`${word(nPend)} can be entered from the next session`));
  c.push(nExit?cl('exit',`${word(nExit)} ${plural(nExit,'needs','need')} an exit check`,'bad'):'<span class="clause quiet">none need an exit check</span>');
  if(nEnd)c.push(cl('end',`${word(nEnd)} ${plural(nEnd,'window closes','windows close')} soon`));
  $('#clauses').innerHTML=c.slice(0,-1).join(', ')+(c.length>1?', and ':'')+c[c.length-1]+'.'+(FILTER!=='all'?` ${cl('all','Show all')}`:'');
 }else $('#clauses').innerHTML='When an individual insider buys with conviction in a stock that passes the rules, it will appear here. Filings mostly arrive between 4 and 9 pm.';
 $$('#clauses .clause[data-f]').forEach(b=>b.addEventListener('click',()=>{FILTER=FILTER===b.dataset.f?'all':b.dataset.f;render(false)}));
 stampLine();
 $('#c-w').textContent=S.length;$('#c-n').textContent=DATA.near.length;
 list();near()}

function lead(s){const ind=s.people.filter(p=>!p.entity);const pool=ind.length?ind:s.people;
 return pool.slice().sort((a,b)=>(b.after-b.before)-(a.after-a.before))[0]}
function sorted(){const S=DATA.signals.map((s,i)=>({s,i}));const k=$('#sort').value;
 if(k==='win')S.sort((a,b)=>b.s.sessions_left-a.s.sessions_left);
 if(k==='near')S.sort((a,b)=>Math.abs(a.s.vs_insider??1e9)-Math.abs(b.s.vs_insider??1e9));
 if(k==='val')S.sort((a,b)=>b.s.value_cr-a.s.value_cr);
 return S}
function list(){
 const q=$('#q').value.trim().toLowerCase(),clean=$('#clean').checked;
 const rows=sorted().filter(({s})=>(FILTER==='all'||(FILTER==='new'&&isNew(s))||(FILTER==='pend'&&s.pending)||(FILTER==='exit'&&s.exit_warning)||(FILTER==='end'&&ending(s)))
  &&(!clean||!s.notes.length)&&(!q||s.sym.toLowerCase().includes(q)||s.company.toLowerCase().includes(q)));
 if(!rows.length){$('#list').innerHTML=`<div class="empty"><b>No stocks match.</b>${q?'Try a different name or symbol.':'Change the filter to see the rest of the watchlist.'}<br><button class="btn" type="button" id="reset">Show the whole watchlist</button></div>`;
  $('#reset').onclick=()=>{FILTER='all';$('#q').value='';$('#clean').checked=false;render(false)};return}
 $('#list').innerHTML=rows.map(({s,i})=>{
  const L=lead(s),others=s.people.length-1;
  const fl=s.notes.map(flag);const tags=[];
  if(s.pending)tags.push('<span class="tag info">Enter next session</span>');
  if(isNew(s)&&!s.pending)tags.push('<span class="tag info">New</span>');
  fl.filter(f=>f.c==='bad').concat(fl.filter(f=>f.c!=='bad')).slice(0,2).forEach(f=>tags.push(`<span class="tag ${f.c}">${esc(f.l)}</span>`));
  if(fl.length>2)tags.push(`<span class="tag">+${fl.length-2} more</span>`);
  if(!fl.length)tags.push('<span class="tag good">Clean</span>');
  const w=Math.max(0,Math.min(120,s.sessions_left)),wc=isNew(s)?'new':ending(s)?'end':'';
  return `<div class="item${OPEN.has(s.sym)?' open':''}" role="listitem" data-i="${i}">
  <div class="row" role="button" tabindex="0" aria-expanded="${OPEN.has(s.sym)}">
   <div class="c-stock"><div class="sym">${isNew(s)?'<span class="newdot" title="New this week"></span>':''}${esc(s.sym)}</div><div class="co">${esc(s.company)}</div><div class="sub">${cr(s.mcap_cr)} market cap</div></div>
   <div class="c-who"><div class="who">${esc(L.name)} <span class="role">(${esc(role(L.cat))})</span> <span class="stake">${fmt(L.before,2)}% → ${fmt(L.after,2)}%</span>${others>0?` <span class="more">and ${others} ${plural(others,'other','others')}</span>`:''}</div>
    <div class="buy">Bought ${cr(s.value_cr)} at an average ${rs(s.avg_price)}, raising their own holding ${s.own_incr>1000?'more than tenfold':'by '+fmt(s.own_incr,0)+'%'}. Disclosed ${esc(s.last_disclosed)}.</div></div>
   <div class="c-px"><div class="px">${rs(s.close)}</div><div class="chg ${cls(s.vs_insider)}">${pct(s.vs_insider)} vs insiders</div><div class="sub">${pct(s.from_high,0)} from 52-week high</div></div>
   <div class="c-win"><div class="win">${s.pending?'<b>Starts</b> next session':`<b>${w}</b> of 120 sessions left`}</div><div class="wbar ${wc}" aria-hidden="true"><i style="width:${(w/120*100).toFixed(1)}%"></i></div></div>
   <div class="c-tag"><div class="tags">${tags.join('')}</div></div>
  </div>
  <div class="detail"><div>${OPEN.has(s.sym)?detail(s):''}</div></div></div>`}).join('');
 $$('#list .row').forEach(r=>{const go=()=>toggle(r.parentElement);r.addEventListener('click',go);r.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}})})}
function toggle(it){const s=DATA.signals[+it.dataset.i];const inner=it.querySelector('.detail>div');const open=!it.classList.contains('open');
 if(open){inner.innerHTML=detail(s);OPEN.add(s.sym)}else OPEN.delete(s.sym);
 requestAnimationFrame(()=>it.classList.toggle('open',open));it.querySelector('.row').setAttribute('aria-expanded',String(open))}
function detail(s){
 const ppl=s.people.slice().sort((a,b)=>(b.after-b.before)-(a.after-a.before)).map(p=>`<li><span class="nm">${esc(p.name)}</span>
  <span class="st">${fmt(p.before,2)}% → ${fmt(p.after,2)}%<small>+${fmt(p.after-p.before,2)} pts</small></span>
  <span class="cat">${esc(role(p.cat))}${p.entity?' · a company, not counted as a signal':''}</span></li>`).join('');
 const flags=s.notes.length?`<ul class="flags">${s.notes.map(n=>`<li class="${/exit/i.test(n)?'bad':''}">${esc(n.replace(/: .*$/,''))}${/weaker history/.test(n)?' (weaker in the backtest)':''}</li>`).join('')}</ul>`:'';
 const oth=s.other.length?`<div class="tscroll"><table class="mini"><thead><tr><th>Disclosed</th><th>Who</th><th>What</th><th class="r">Value</th></tr></thead><tbody>${
  s.other.map(x=>`<tr><td style="white-space:nowrap">${esc(x.date)}</td><td>${esc(x.person)}<div class="mut">${esc(role(x.cat))}</div></td><td>${esc(x.type.replace(' / ',', '))}</td><td class="r">${cr(x.value_cr)}</td></tr>`).join('')}</tbody></table></div>`
  :'<p class="mut" style="margin:0">No other insider filings from 90 days before the signal to today.</p>';
 return `<div class="dpad">
  <div><h3>Who bought</h3><ul class="people">${ppl}</ul>
   <h3>The purchase</h3><dl class="facts">
    <dt>Trades</dt><dd>${esc(s.first_trade)} to ${esc(s.last_trade)}, ${s.filings} ${plural(s.filings,'filing','filings')}</dd>
    <dt>First disclosed</dt><dd>${esc(s.first_disclosed)}</dd>
    <dt>Shares</dt><dd>${s.shares.toLocaleString('en-IN')}${s.pct_company!=null?`, ${fmt(s.pct_company,3)}% of the company`:''}</dd>
    <dt>Daily trading</dt><dd>${cr(s.liq_cr)} a day (60-day median)</dd></dl>
   ${s.exit_warning?`<p class="error" style="margin:14px 0 0"><b>Exit check:</b> ${esc(s.exit_detail)}</p>`:''}${flags}
   <div class="links"><a href="https://www.nseindia.com/get-quotes/equity?symbol=${encodeURIComponent(s.sym)}" target="_blank" rel="noopener">Open on NSE</a>
    <a href="https://www.nseindia.com/companies-listing/corporate-filings-insider-trading" target="_blank" rel="noopener">NSE insider filings</a></div></div>
  <div><h3>Other insider filings</h3>${oth}</div></div>`}
function near(){const N=DATA.near;
 $('#near').innerHTML=N.length?N.map(n=>`<tr><td><div class="sym" style="font-size:14.5px">${esc(n.sym)}</div><div class="co" style="font-size:14px">${esc(n.company)}</div></td>
  <td class="buyers">${esc(n.buyers)}<div class="mut" style="font-size:13px">${esc(n.group)}</div></td><td class="r">${cr(n.value_cr)}</td><td class="r">${cr(n.mcap_cr)}</td>
  <td class="why">${esc(n.why.charAt(0).toUpperCase()+n.why.slice(1))}</td></tr>`).join('')
  :'<tr><td colspan="5" class="empty">No large buys were left out in the last 120 sessions.</td></tr>'}
const RULES=[['A genuine market purchase','Filing type "Buy", mode "Market Purchase", equity shares. Transfers, gifts, ESOPs, preferential allotments and pledges are ignored.'],
 ['Bought by an individual','A promoter, promoter-group member, relative, director or key manager who is a person, not a company, LLP, trust or fund.'],
 ['With conviction','The shares bought add at least 5% to what the buyer already owned.'],
 ['In a smaller company','Market cap ₹10,000 crore or less. ₹1,000–5,000 crore was the strongest band.'],
 ['That you can trade','EQ series, at least ₹1 crore traded a day, few circuit hits, price ₹10 or more.'],
 ['With no insider selling','No promoter-side sale in the prior 180 days (90 days for director and key-manager buys).'],
 ['Watched for 120 sessions','Enter only with your own setup. A new qualifying buy restarts the clock; an insider sale afterwards is an exit check.']];
$('#rules').innerHTML=RULES.map(([t,d])=>`<div><svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3.5 8.5 3 3 6-7"/></svg><p style="margin:0"><b>${t}</b><span>${d}</span></p></div>`).join('');

$('#q').addEventListener('input',list);$('#clean').addEventListener('change',list);$('#sort').addEventListener('change',list);
$$('.tab').forEach(t=>t.addEventListener('click',()=>{$$('.tab').forEach(x=>x.setAttribute('aria-selected',String(x===t)));
 ['p-w','p-n','p-r'].forEach(id=>$('#'+id).hidden=id!==t.getAttribute('aria-controls'));$('#tools').style.visibility=t.id==='tab-w'?'visible':'hidden'}));
$('#run').addEventListener('click',start);
(async()=>{const s=await status();if(s.running)watch();else if(s.has_result)load();else start()})();
</script>
</body>
</html>
"""
