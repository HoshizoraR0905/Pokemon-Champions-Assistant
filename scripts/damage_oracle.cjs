/* Test-only adapter. No Python implementation imported. Actual stats replace all constructor defaults. */
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const pkg=path.join(root,'.cache/m31/oracle/node_modules/@smogon/calc');
const c=require(pkg),mechanics=require(path.join(pkg,'dist/mechanics/champions'));
if(require(path.join(pkg,'package.json')).version!=='0.12.0')throw Error('Pinned oracle version required');
const data=JSON.parse(fs.readFileSync(path.join(root,'damage/data/reference-v1.json')));
const kb=JSON.parse(fs.readFileSync(path.join(root,'knowledge/data/entities.json'))).entities;
const norm=x=>x.toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');
function ref(value,kind){let e=kb.filter(e=>e.kind===kind&&(e.canonical_id===value||Object.values(e.names).concat(e.aliases).some(n=>norm(n)===norm(value))));if(e.length!==1)throw Error('Oracle input ambiguous '+value);return e[0];}
const stats={attack:'atk',defense:'def',special_attack:'spa',special_defense:'spd',speed:'spe'};
const statuses={none:'',burn:'brn',paralysis:'par',poison:'psn',toxic:'tox',sleep:'slp',freeze:'frz'};
const gen=c.Generations.get(0);
function mon(input){let e=ref(input.identity,'species');if(input.form&&input.form!=='base'&&input.form!=='as_named')e=ref(input.form,'species');const p=new c.Pokemon(gen,data.species[e.canonical_id].oracle_name);
 p.level=input.level;p.ability=input.ability==='none'?'':ref(input.ability,'ability').names.en;p.item=input.item==='none'?'':ref(input.item,'item').names.en;
 p.status=statuses[input.status];p.rawStats.hp=input.maximum_hp;p.stats.hp=input.maximum_hp;p.originalCurHP=input.current_hp;
 for(const [long,short] of Object.entries(stats)){p.rawStats[short]=input.stats[long];p.stats[short]=input.stats[long];p.boosts[short]=input.stages[long];}return p;}
function calc(input){const f=input.field;
 let a=mon(input.attacker),d=mon(input.defender);const move=new c.Move(gen,ref(input.move,'move').names.en,{isCrit:f.critical});
 const weather={none:undefined,sun:'Sun',rain:'Rain',sand:'Sand',snow:'Snow'},terrain={none:undefined,electric:'Electric',grassy:'Grassy',psychic:'Psychic',misty:'Misty'};
 const field=new c.Field({gameType:f.format==='doubles'?'Doubles':'Singles',weather:weather[f.weather],terrain:terrain[f.terrain],attackerSide:{isHelpingHand:f.helping_hand},defenderSide:{isReflect:f.reflect,isLightScreen:f.light_screen,isAuroraVeil:f.aurora_veil,isFriendGuard:f.friend_guard}});
 const result=mechanics.calculateChampions(gen,a,d,move,field);let rolls=result.damage;if(typeof rolls==='number')rolls=[rolls];if(rolls.some(Array.isArray))throw Error('Unexpected multihit fixture');return {rolls,oracle_description:result.rawDesc};}
const inputs=JSON.parse(fs.readFileSync(process.argv[2]));
const results=inputs.cases.map(row=>({id:row.id,input:row.input,...calc(row.input)}));
process.stdout.write(JSON.stringify({oracle:{package:'@smogon/calc',version:'0.12.0',generation:0,adapter:'actual raw stats; direct Champions mechanics; ability/level defaults overwritten'},cases:results},null,2)+'\n');
