/* Test-only pinned Champions reference adapter; Python implementation not imported. */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),pkg=path.join(root,'.cache/m31/oracle/node_modules/@smogon/calc');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'damage/data/manifest.json')));
for(const [name,digest] of Object.entries(manifest.oracle.files)) {
 if(crypto.createHash('sha256').update(fs.readFileSync(path.join(pkg,name))).digest('hex')!==digest)throw Error('Oracle checksum '+name);
}
const c=require(pkg),u=require(path.join(pkg,'dist/mechanics/util')),gen=c.Generations.get(0);
const source=fs.readFileSync(path.join(root,'.cache/m32/sources/champions-scripts.ts'),'utf8');
const body=source.match(/getActionSpeed\(\) \{([\s\S]*?)\n\t\t\},/)[1];const actionSpeed=new Function(body);
function speed(input,actual,stage){
 const p=input.participant,f=input.field;let mon=new c.Pokemon(gen,'Charizard');
 mon.rawStats.spe=actual;mon.boosts.spe=stage;mon.ability=p.ability_active&&p.ability!=='none'?p.ability:'';mon.item=p.item==='none'?'':p.item;
 mon.abilityOn=p.ability==='Unburden'&&p.unburden_active;mon.status={none:'',paralysis:'par',burn:'brn',poison:'psn',toxic:'tox',sleep:'slp',freeze:'frz'}[p.status];
 const field=new c.Field({weather:{none:undefined,sun:'Sun',rain:'Rain',sand:'Sand',snow:'Snow'}[f.weather],terrain:{none:undefined,electric:'Electric',grassy:'Grassy',psychic:'Psychic',misty:'Misty'}[f.terrain],attackerSide:{isTailwind:p.tailwind}});
 return {effective_speed:u.getFinalSpeed(gen,mon,field,field.attackerSide),modern_cap_probe:u.getFinalSpeed(c.Generations.get(9),mon,field,field.attackerSide)};
}
const request=JSON.parse(fs.readFileSync(process.argv[2]));
for(const g of request.groups){g.rows=g.candidates.flatMap(actual=>g.stages.map(stage=>({actual_speed:actual,stage,...speed(g,actual,stage)})));delete g.candidates;delete g.stages;}
request.order_cases=[false,true].flatMap(trick=>[[99,100],[100,100],[101,100],[10000,9999]].map(([own,opponent])=>{
 const mock=n=>({getStat:()=>n,battle:{ruleTable:{has:()=>false},field:{getPseudoWeather:()=>trick}}});
 const a=actionSpeed.call(mock(own)),b=actionSpeed.call(mock(opponent));
 return {own_effective:own,opponent_effective:opponent,trick_room:trick,orders:a===b?['own','opponent']:[a>b?'own':'opponent']};
}));
request.oracle={package:'@smogon/calc',version:'0.12.0',generation:0,ordering_commit:'3a766f2cfb5e51c1e428cfe87d0dba91a8f01640',ordering:'Executed pinned Champions getActionSpeed method with oracle effective Speed'};
process.stdout.write(JSON.stringify(request)+'\n');
