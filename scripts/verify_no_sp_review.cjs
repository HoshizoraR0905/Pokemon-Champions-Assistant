/* Browser checks use an isolated server annotation database, never human reviews.
 * Usage: node scripts/verify_no_sp_review.cjs http://127.0.0.1:8354 OUTPUT_DIR
 * Requires local Google Chrome and Node with built-in WebSocket (22+).
 */
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert');
const url=process.argv[2],out=path.resolve(process.argv[3]||'');
if(!url||!process.argv[3]||fs.existsSync(out))throw Error('Supply URL and a new output directory');
fs.mkdirSync(out,{recursive:true});
const profile=path.join(out,'chrome-profile');
const browser=cp.spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
 ['--headless','--disable-gpu','--no-first-run','--window-size=1440,1050','--user-data-dir='+profile,'--remote-debugging-port=0',url],{stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));let ws,next=0;const pending=new Map(),errors=[];
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function wait(expression){for(let i=0;i<100;i++){if(await ev(expression))return;await pause(100);}throw Error('Timeout '+expression);}
(async()=>{try{
 let port;for(let i=0;i<100;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0].trim();if(/^\d+$/.test(port))break;}catch{}await pause(100);}
 const pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}};
 await send('Runtime.enable');await send('Page.enable');
 await wait("typeof DATA!=='undefined' && DATA && $('run-info').textContent.includes('eligible')");
 await ev("$('population').value='curated';$('status').value='all';$('cluster').value='all';$('sort').value='queue';rebuild(DATA.queue[0])");
 await wait("document.querySelectorAll('.teammate').length===5");
 // Refuse to touch the actual human store even if the caller supplies its URL.
 assert(await ev("DATA.annotation_location.includes('test-reviews')"),'Use a test-reviews annotation database');
 assert.equal(await ev("DATA.records.length"),202);
 assert.equal(await ev("DATA.independent_count"),191);
 assert.equal(await ev("document.querySelectorAll('.cluster-card').length"),3);
 assert.equal(await ev("document.querySelectorAll('.weight-row').length"),6);
 assert(await ev("[...document.querySelectorAll('.teammate')].every(e=>e.querySelectorAll('li').length===4&&e.textContent.includes('Item:')&&e.querySelector('a'))"));
 assert(await ev("[...document.querySelectorAll('.fill')].every(e=>e.getBoundingClientRect().width>0)"),'Weight bars render');
 const first=await ev('current');
 await ev("$('next').click()");await wait('current!=='+JSON.stringify(first));
 await ev("$('previous').click()");await wait('current==='+JSON.stringify(first));
 await ev("$('assessment').value='ambiguous';$('assessment').dispatchEvent(new Event('input'));$('notes').value='AUTOMATED UI CHECK — not a human assessment';$('notes').dispatchEvent(new Event('input'));$('review-form').dispatchEvent(new Event('submit',{cancelable:true}))");
 await wait("!dirty && $('save-status').textContent.includes('Saved durably')");
 assert(await ev("Boolean(reviews[current])"));
 await ev("$('population').value='independent';$('population').dispatchEvent(new Event('change'));$('sort').value='uncertain';$('sort').dispatchEvent(new Event('change'))");
 await wait("ids.length===191");
 await ev("$('jump').value='3';$('jump-go').click()");const jumped=await ev('current');
 await wait("fetch('/api/session').then(r=>r.json()).then(s=>s.last_record==="+JSON.stringify(jumped)+")");
 await send('Page.reload');await wait("typeof DATA!=='undefined'&&DATA&&current==="+JSON.stringify(jumped));
 assert.equal(await ev("$('sort').value"),'uncertain');assert.equal(await ev("$('population').value"),'independent');
 assert(await ev('Boolean(reviews['+JSON.stringify(first)+'])'));
 const reviewedCount=await ev('Object.keys(reviews).length');
 assert(await ev("fetch('/api/export.json').then(r=>r.json()).then(x=>x.reviews.some(r=>r.notes.includes('AUTOMATED UI CHECK')))") );
 assert(await ev("fetch('/api/export.csv').then(r=>r.text()).then(x=>x.includes('suggested_weights')&&x.includes('AUTOMATED UI CHECK'))"));
 await ev("$('population').value='all';$('population').dispatchEvent(new Event('change'))");assert.equal(await ev('ids.length'),202);
 await ev("$('status').value='reviewed';$('status').dispatchEvent(new Event('change'))");assert.equal(await ev('ids.length'),reviewedCount);
 await ev("$('status').value='unreviewed';$('status').dispatchEvent(new Event('change'))");assert.equal(await ev('ids.length'),202-reviewedCount);
 await ev("$('status').value='all';$('status').dispatchEvent(new Event('change'));$('cluster').value='1';$('cluster').dispatchEvent(new Event('change'))");
 assert(await ev("ids.length>0&&ids.every(id=>record(id).prediction.moves_only.top===1)"));
 await ev("$('cluster').value='all';$('cluster').dispatchEvent(new Event('change'));$('population').value='curated';$('population').dispatchEvent(new Event('change'))");
 assert.equal(await ev('ids.length'),20);
 await ev("document.querySelector('#candidate').scrollIntoView()");
 const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'review.png'),Buffer.from(shot.data,'base64'));
 assert.equal(errors.length,0,JSON.stringify(errors));
 const result={status:'passed',eligible:202,independent:191,curated:20,checks:['cluster references','five full teammates','both weight displays','bars render','next/previous','durable save','sorting and jump','resume on reload','JSON/CSV export','population/status/cluster filters'],human_review:'not performed; test annotation store only'};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{if(ws)ws.close();browser.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
