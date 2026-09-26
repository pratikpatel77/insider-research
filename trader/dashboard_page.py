PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Insider Trader</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--mute:#697080;--line:#e3e6ec;--good:#0a7d47;--bad:#c22b2b;--warn:#a86400;--accent:#1f5fd6;--chip:#eef1f6}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a20;--ink:#e8eaee;--mute:#8b93a3;--line:#262b34;--good:#3ec786;--bad:#ff6b6b;--warn:#e0a13a;--accent:#6b9bff;--chip:#20252e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;padding:12px 20px;background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
h1{font-size:16px;margin:0 8px 0 0}h2{font-size:14px;margin:0 0 10px}
main{padding:16px 20px;max-width:1300px;margin:auto;display:grid;gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow-x:auto}
.badge{padding:3px 10px;border-radius:99px;font-weight:700;font-size:12px;letter-spacing:.04em}
.paper{background:#dff5e8;color:#0a7d47}.live{background:#ffdcdc;color:#c22b2b}
@media(prefers-color-scheme:dark){.paper{background:#12362a}.live{background:#4a1f1f}}
table{border-collapse:collapse;width:100%;min-width:760px}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{font-size:12px;color:var(--mute);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.good{color:var(--good)}.bad{color:var(--bad)}.mute{color:var(--mute)}.warn{color:var(--warn)}
button{font:inherit;padding:5px 12px;border-radius:7px;border:1px solid var(--line);background:var(--chip);color:var(--ink);cursor:pointer}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}button.danger{background:var(--bad);border-color:var(--bad);color:#fff}
button:disabled{opacity:.45;cursor:default}
input,select{font:inherit;padding:5px 8px;border-radius:7px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
input[type=number]{width:96px}input.sym{width:120px;text-transform:uppercase}
.row{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center}.grow{flex:1}
.chip{background:var(--chip);border-radius:6px;padding:2px 7px;font-size:12px}
.stats{display:flex;flex-wrap:wrap;gap:8px 28px}.stats div b{display:block;font-size:18px}
.log{font:12px/1.5 ui-monospace,Consolas,monospace;max-height:230px;overflow:auto}.log div{padding:1px 0}
.settings{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px 16px}
.settings label{display:flex;flex-direction:column;font-size:12px;color:var(--mute);gap:2px}
#toast{position:fixed;right:16px;bottom:16px;max-width:420px;padding:10px 14px;border-radius:8px;background:var(--ink);color:var(--bg);display:none;z-index:9}
.sw{display:inline-flex;align-items:center;gap:6px;cursor:pointer}
</style></head><body>
<header>
 <h1>Insider Trader</h1><span id="mode" class="badge"></span>
 <span id="brk" class="mute"></span><span id="login"></span>
 <span class="grow"></span>
 <label class="sw"><input type="checkbox" id="auto"> Auto-buy at <span id="buytime"></span></label>
 <button id="kill"></button><button id="scan">Scan now</button>
 <span class="mute" id="clock"></span>
</header>
<main>
 <div class="card"><div class="stats" id="stats"></div><div id="scaninfo" class="mute" style="margin-top:8px"></div></div>

 <div class="card"><h2>New signals <span class="mute" id="candnote"></span></h2>
  <table><thead><tr><th>Stock</th><th class="n">Insider avg</th><th class="n">Entry limit</th><th class="n">Price now</th><th class="n">vs avg</th><th>Status</th><th>Quantity</th><th></th></tr></thead><tbody id="cands"></tbody></table>
  <div class="mute" style="margin-top:8px">Only Clean signals still inside the entry limit can be bought. A signal rejected for lack of margin shows "Needs funds": add funds, then press Buy while it is still in range.</div>
 </div>

 <div class="card"><h2>Open positions <span class="mute">- stops are set and moved automatically</span></h2>
  <table><thead><tr><th>Stock</th><th class="n">Qty</th><th class="n">Entry</th><th class="n">Price now</th><th class="n">P&amp;L</th><th class="n">Stop</th><th>Stop type</th><th class="n">Highest close</th><th>Protection</th><th></th></tr></thead><tbody id="pos"></tbody></table></div>

 <div class="card"><h2>Record a trade you did outside this app</h2>
  <div class="row"><input class="sym" id="asym" placeholder="SYMBOL"><input type="number" id="apx" step="0.05" placeholder="Actual fill price"><input type="number" id="aqty" placeholder="Actual quantity">
   <button class="primary" id="adopt">Manage this trade</button><span class="mute">Uses your actual fill price and quantity to set the stop-loss and the trailing stop.</span></div></div>

 <div class="card"><h2>Closed trades</h2>
  <table><thead><tr><th>Stock</th><th class="n">Qty</th><th class="n">Entry</th><th class="n">Exit</th><th class="n">P&amp;L Rs</th><th class="n">P&amp;L %</th><th>Reason</th><th>Bought</th><th>Sold</th></tr></thead><tbody id="closed"></tbody></table></div>

 <div class="card"><h2>Settings</h2><div class="settings" id="settings"></div>
  <div class="row" style="margin-top:12px"><button class="primary" id="save">Save settings</button>
  <span class="mute">Broker:</span><select id="bsel"><option>paper</option><option>definedge</option><option>kotak</option><option>fyers</option></select>
  <button id="golive"></button></div></div>

 <div class="card"><h2>Log</h2><div class="log" id="log"></div></div>
</main><div id="toast"></div>
<script>
const $=s=>document.querySelector(s);let S=null,busy=false;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const f2=v=>v==null?'-':Number(v).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
const rs=v=>v==null?'-':(v<0?'-':'')+'Rs '+Math.abs(Math.round(v)).toLocaleString('en-IN');
const cls=v=>v>0?'good':v<0?'bad':'';
function toast(m,bad){const t=$('#toast');t.textContent=m;t.style.background=bad?'#c22b2b':'';t.style.color=bad?'#fff':'';t.style.display='block';clearTimeout(toast.h);toast.h=setTimeout(()=>t.style.display='none',bad?9000:4000)}
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Trader':'1'},body:JSON.stringify(body||{})});
 const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||('Error '+r.status));return j}
async function run(path,body,ok){try{await post(path,body);if(ok)toast(ok);load()}catch(e){toast(e.message,true)}}
async function load(){if(busy)return;try{const r=await fetch('/api/state');S=await r.json();render()}catch(e){$('#clock').textContent='disconnected'}}

function render(){const s=S,st=s.settings,live=s.mode==='live';
 $('#mode').textContent=live?'LIVE - REAL MONEY':'PAPER';$('#mode').className='badge '+(live?'live':'paper');
 $('#brk').innerHTML=live?`Broker: <b>${esc(s.broker)}</b>`:'Simulated fills on real NSE prices'+(s.broker!=='paper'?` - <b>${esc(s.broker)}</b> selected`:'');
 $('#login').innerHTML=s.broker==='paper'?'':s.broker_error?`<span class="bad">${esc(s.broker_error)}</span>`:(s.broker_ready?'<span class="good">connected</span>':loginBox(s));
 $('#auto').checked=st.auto_buy;$('#buytime').textContent=st.buy_time;$('#clock').textContent=s.now+(s.market_open?' - market open':' - market closed');
 $('#kill').textContent=st.kill_switch?'Kill switch ON (click to resume buying)':'Kill switch';$('#kill').className=st.kill_switch?'danger':'';
 $('#scan').disabled=s.scan.running;$('#scan').textContent=s.scan.running?'Scanning...':'Scan now';
 const T=s.totals,wr=T.closed_n?Math.round(T.wins/T.closed_n*100):0;
 $('#stats').innerHTML=`<div>Open positions<b>${s.slots_used}${st.max_positions?' / '+st.max_positions:''}</b></div><div>Available margin<b>${s.funds==null?'-':rs(s.funds)}</b></div><div>Open P&L<b class="${cls(T.open_pnl)}">${rs(T.open_pnl)}</b></div>
  <div>Closed P&L<b class="${cls(T.closed_pnl)}">${rs(T.closed_pnl)}</b></div><div>Closed trades<b>${T.closed_n}${T.closed_n?` <span class="mute" style="font-size:13px">${wr}% won</span>`:''}</b></div>
  <div>Per position<b>${rs(st.position_amount)}</b></div>`;
 const sc=s.scan;$('#scaninfo').innerHTML=sc.running?esc(sc.msg||'Scanning...'):sc.at?`Last scan ${esc(sc.at)} (prices as of ${esc(sc.as_of)}).`+(sc.error?` <span class="bad">Last error: ${esc(sc.error)}</span>`:''):'No scan yet. It runs by itself at 08:40, or press Scan now.';
 // candidates
 $('#candnote').textContent=`- entry limit = insiders' average + ${st.entry_band_pct}%`;
 $('#cands').innerHTML=s.candidates.map((c,i)=>{const vs=c.ltp&&c.avg_now?(c.ltp/c.avg_now-1)*100:null;
  const stx={buyable:'<span class="good">Buyable</span>','above zone':'<span class="warn">Above entry limit</span>',held:'<span class="chip">Held</span>','needs funds':`<span class="warn" title="${esc(c.reject_note||'')}">Rejected: needs funds</span>`,used:'<span class="chip">Already traded</span>','no price':'<span class="mute">no price yet</span>','not clean':`<span class="bad" title="${esc(c.notes.join('; '))}">Not clean</span> <span class="mute">${esc(c.notes.join('; ').slice(0,60))}</span>`}[c.status];
  const can=c.status==='buyable'||c.status==='needs funds';const est=c.ltp?Math.floor(st.position_amount/(c.ltp*1.003)):null;
  return `<tr><td><b>${esc(c.sym)}</b> <span class="mute">${esc(c.company)}</span></td><td class="n">${f2(c.avg_now)}</td><td class="n">${f2(c.cap)}</td><td class="n">${f2(c.ltp)}</td>
  <td class="n ${vs>st.entry_band_pct?'warn':''}">${vs==null?'-':(vs>0?'+':'')+vs.toFixed(1)+'%'}</td><td>${stx}</td>
  <td><input type="number" min="1" id="q${i}" placeholder="auto${est?' ('+est+')':''}"></td>
  <td><button class="primary" ${can?'':'disabled'} onclick="buy('${esc(c.sym)}',${i})">Buy</button></td></tr>`}).join('')||'<tr><td colspan="8" class="mute">No signals yet.</td></tr>';
 // positions
 $('#pos').innerHTML=s.positions.map(p=>{const prot=p.status==='entering'?'<span class="warn">order placed, waiting for fill</span>':p.sl_state==='broker'?'<span class="good">stop order at broker</span>':p.sl_state==='software'?'<span class="warn">app is watching the price</span>':p.sl_state==='exit'?'<span class="warn">exit order in progress</span>':'<span class="bad">no stop order yet</span>';
  return `<tr><td><b>${esc(p.sym)}</b> <span class="chip">${esc(p.source)}</span></td><td class="n">${p.qty}</td><td class="n">${f2(p.entry_price)}</td><td class="n">${f2(p.ltp)}</td>
  <td class="n ${cls(p.pnl_now)}">${p.pnl_now==null?'-':rs(p.pnl_now)+' ('+p.pnl_pct.toFixed(1)+'%)'}</td><td class="n">${f2(p.stop)}</td><td>${esc(p.stop_kind||'')}${p.stop>p.initial_stop+0.01?' <span class="chip">trailing</span>':''}</td>
  <td class="n">${f2(p.high_close)}</td><td>${prot}</td><td>${p.status==='open'?`<button class="danger" onclick="sell(${p.id},'${esc(p.sym)}')">Exit now</button>`:''}</td></tr>`}).join('')||'<tr><td colspan="10" class="mute">No open positions.</td></tr>';
 $('#closed').innerHTML=s.closed.map(p=>`<tr><td><b>${esc(p.sym)}</b></td><td class="n">${p.qty}</td><td class="n">${f2(p.entry_price)}</td><td class="n">${f2(p.exit_price)}</td><td class="n ${cls(p.pnl)}">${rs(p.pnl)}</td>
  <td class="n ${cls(p.pnl)}">${((p.exit_price/p.entry_price-1)*100).toFixed(1)}%</td><td>${esc(p.exit_reason)}</td><td class="mute">${esc((p.entry_time||'').slice(0,10))}</td><td class="mute">${esc((p.exit_time||'').slice(0,10))}</td></tr>`).join('')||'<tr><td colspan="9" class="mute">Nothing closed yet.</td></tr>';
 $('#log').innerHTML=s.events.map(e=>`<div class="${e.level==='error'?'bad':e.level==='warn'?'warn':''}">${esc(e.ts.slice(5))}  ${esc(e.msg)}</div>`).join('');
 // settings form (rebuild only when not being edited)
 if(!document.activeElement||!document.activeElement.closest('#settings')){
  const lab={position_amount:'Rs per position',max_positions:'Max open positions (0 = no limit)',paper_capital:'Paper account balance Rs',entry_band_pct:'Entry band % over insider avg',buy_time:'Auto-buy time',buy_window_min:'Auto-buy window (min)',limit_buffer_pct:'Limit above price %',fill_wait_min:'Cancel unfilled after (min)',trail_pct:'Trailing stop %',max_sl_pct:'Max initial stop %',min_sl_pct:'Min pivot distance %',pivot_bars:'Pivot bars each side',pivot_lookback:'Pivot look-back (sessions)',sl_limit_gap_pct:'Stop-limit gap %',max_order_value:'Max single order Rs',max_orders_per_day:'Max orders per day'};
  $('#settings').innerHTML=Object.keys(lab).map(k=>`<label>${lab[k]}<input data-k="${k}" value="${esc(st[k])}"></label>`).join('')}
 $('#bsel').value=s.broker;$('#golive').textContent=live?'Switch to PAPER':'Go live...';$('#golive').className=live?'':'danger'}

function loginBox(s){if(s.broker==='fyers')return `<button onclick="fyersLogin()">Login to Fyers</button> <input id="lg" placeholder="paste the address you land on" size="26"> <button onclick="doLogin()">Connect</button>`;
 if(!s.broker_auto_login)return `<input id="lg" placeholder="6-digit code" size="9"> <button onclick="doLogin()">Login</button>`;
 return `<span class="warn">not connected</span> <button onclick="doLogin()">Login</button>`}
async function fyersLogin(){try{const r=await fetch('/api/fyers_url');const j=await r.json();if(j.url)window.open(j.url,'_blank');else toast('No login link',true)}catch(e){toast(e.message,true)}}
function doLogin(){const v=($('#lg')||{}).value||'';run('/api/login',{totp:v,redirected_url:v},'Login attempted')}
function buy(sym,i){const q=+($('#q'+i).value)||null;const live=S.mode==='live';
 if(live&&!confirm(`LIVE order: buy ${q?q+' shares of':'about '+rs(S.settings.position_amount)+' of'} ${sym}?`))return;
 run('/api/buy',{sym,qty:q},'Buy order placed for '+sym)}
$('#adopt').onclick=()=>{const sym=$('#asym').value.trim().toUpperCase(),price=+$('#apx').value,qty=+$('#aqty').value;if(!sym||!price||!qty)return toast('Enter symbol, fill price and quantity',true);
 run('/api/adopt',{sym,price,qty},'Now managing '+sym)};
function sell(id,sym){if(confirm(`Sell all of ${sym} at market now?`))run('/api/sell',{id},'Exit order sent for '+sym)}
$('#auto').onchange=e=>{if(e.target.checked&&S.mode==='live'&&!confirm('Turn on AUTOMATIC buying with real money? New Clean signals will be bought at '+S.settings.buy_time+'.')){e.target.checked=false;return}run('/api/settings',{changes:{auto_buy:e.target.checked}},e.target.checked?'Auto-buy ON':'Auto-buy OFF')};
$('#kill').onclick=()=>run('/api/settings',{changes:{kill_switch:!S.settings.kill_switch}},'Kill switch toggled');
$('#scan').onclick=()=>run('/api/scan',{},'Scan started');
$('#save').onclick=()=>{const c={};document.querySelectorAll('#settings input').forEach(i=>c[i.dataset.k]=i.value);run('/api/settings',{changes:c},'Settings saved')};
$('#bsel').onchange=e=>run('/api/broker',{name:e.target.value},'Broker set to '+e.target.value);
$('#golive').onclick=()=>{if(S.mode==='live')return run('/api/mode',{mode:'paper'},'Paper mode');
 if(S.broker==='paper')return toast('Pick a broker first',true);if(!S.live_unlocked)return toast('Live trading is locked: add TRADER_ALLOW_LIVE=1 to trader/.env and restart',true);
 const c=prompt('This will trade REAL MONEY through '+S.broker+'.\nType GO LIVE to confirm:');if(c!==null)run('/api/mode',{mode:'live',confirm:c},'LIVE mode on')};
load();setInterval(load,10000);
</script></body></html>
"""
