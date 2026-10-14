// Offline DOM smoke/initialization benchmark; not a real browser layout benchmark.
const fs = require('node:fs');
const vm = require('node:vm');
const {performance} = require('node:perf_hooks');
class Element {
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.value='all';this.attrs={};this._text='';this.open=false;}
 set textContent(v){this._text=String(v);this.children=[];}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 get lastChild(){return this.children.at(-1);}
 append(...nodes){for(const n of nodes)n.parentElement=this;this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
 setAttribute(k,v){this.attrs[k]=v;}
}
const mockElements={},mockListeners={};
global.document={baseURI:require('node:url').pathToFileURL(require('node:path').resolve(process.argv[2])).href,getElementById:id=>mockElements[id]??(mockElements[id]=new Element()),createElement:tag=>new Element(tag),addEventListener:(key,fn)=>mockListeners[key]=fn};
for(const id of ['before-json','after-json','event-json','raw-json'])document.getElementById(id).parentElement=new Element('details');
const benchmarkHtml=fs.readFileSync(process.argv[2],'utf8');
const benchmarkMarker='<script type="application/json" id="timeline-data">';
const benchmarkStart=benchmarkHtml.indexOf(benchmarkMarker)+benchmarkMarker.length;
mockElements['timeline-data']=new Element();mockElements['timeline-data'].textContent=benchmarkHtml.slice(benchmarkStart,benchmarkHtml.indexOf('</script>',benchmarkStart));
const benchmarkScript=benchmarkHtml.match(/<script>([\s\S]*?)<\/script>/)[1];
const benchmarkBegin=performance.now();
vm.runInThisContext(benchmarkScript);
const benchmarkReady=performance.now();
vm.runInThisContext(`
for(let i=0;i<entries.length;i++){
 $('events').children[i].onclick();
 if($('after-json').textContent!=='')throw Error('Collapsed debug panel rendered eagerly');
 if(selected!==i)throw Error('Navigation did not select requested state');
 const state=entries[i].after;
 if(state.knowledge?.pokemon_projection){
  const walk=node=>[node,...node.children.flatMap(walk)];
  const summaries=walk($('sides')).filter(n=>n.tagName==='DIV'&&n._text.startsWith('已确认／揭示招式：'));
  for(const [pid,view]of Object.entries(state.knowledge.pokemon_projection)){
   if(state.pokemon[pid].side_id!=='opponent')continue;
   for(const move of view.revealed_moves){
    const label=state.knowledge.hidden_configuration.labels[move.canonical_id]||move.name;
    if(!summaries.some(n=>n._text.includes(label)))throw Error('Revealed move missing from main summary: '+label);
   }
  }
 }

}
$('after-json').parentElement.open=true;$('after-json').parentElement.ontoggle();
if(JSON.stringify(JSON.parse($('after-json').textContent))!==JSON.stringify(entries.at(-1).after))throw Error('Lazy debug state mismatch');
$('events').children[0].onclick();
if(JSON.stringify(JSON.parse($('after-json').textContent))!==JSON.stringify(entries[0].after))throw Error('Open debug panel not refreshed');
`);
console.log(JSON.stringify({html_bytes:Buffer.byteLength(benchmarkHtml),states:mockElements.events.children.length,startup_ms:+(benchmarkReady-benchmarkBegin).toFixed(2),all_states_navigation_and_lazy_debug_ms:+(performance.now()-benchmarkReady).toFixed(2),rss_mb:+(process.memoryUsage().rss/1024/1024).toFixed(2),smoke_passed:true,environment:'Node minimal DOM; no browser layout timing'}));
