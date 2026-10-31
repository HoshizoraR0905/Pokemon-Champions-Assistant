"""Reproduce the scoped 166-item reference audit from already pinned sources.

Source-specific supplement to existing canonical KnowledgeBase IDs; no crawling.
52Poké corroboration receipts are reused when present. UI guarantees remain unknown.
"""
import json,re,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from speed_order.core import knowledge,name
from damage.engine import ITEMS,TYPE_ITEMS,BERRIES
k=knowledge();root=Path('.cache/m341-actions/sources')
def blocks(path):
 text=path.read_text();starts=list(re.finditer(r'^\t([a-z0-9]+): \{',text,re.M));out={}
 for n,m in enumerate(starts):
  end=starts[n+1].start() if n+1<len(starts) else len(text)
  out[m[1]]=(text[m.start():end],text.count('\n',0,m.start())+1,text.count('\n',0,end))
 return out
base=blocks(root/'ps-data-items.ts');mods=blocks(root/'ps-data-mods-champions-items.ts')
normalize=lambda s:re.sub('[^a-z0-9]','',s.lower())
effects={
'Air Balloon':'Airborne until damaged; pops on a damaging hit; entry announcement subject to Gravity/item suppression',
'Big Root':'Increases drain/recovery gained; does not increase connected-hit damage',
'Binding Band':'Increases partial-trapping residual damage, not initial hit',
'Bright Powder':'Lowers incoming accuracy; connected-hit equality does not test accuracy',
'Choice Scarf':'Speed ×1.5 and move lock; current Speed handled by existing engine; historical lock not simulated',
'Eject Button':'Consumed after damaging hit to switch holder',
'Electric Seed':'Consumed on electric terrain; Defense +1',
'Grassy Seed':'Consumed on grassy terrain; Defense +1',
'Misty Seed':'Consumed on misty terrain; Special Defense +1',
'Psychic Seed':'Consumed on psychic terrain; Special Defense +1',
'Focus Band':'Conditional survival at 1 HP; cannot treat lethal damage as exact ordinary equality',
'Focus Sash':'Consumed to survive lethal hit at 1 HP from full HP',
'Iron Ball':'Speed ×0.5; grounds holder and removes Flying Ground immunity under reference conditions',
'King’s Rock':'Adds conditional flinch; no multiplier on connected hit',
'Leek':'Raises critical stage for Farfetch’d family; explicit critical branch remains required',
'Leftovers':'End-turn HP recovery',
'Leppa Berry':'Consumed to restore depleted move PP',
'Life Orb':'Damage ×5324/4096; separate post-hit recoil evidence',
'Light Ball':'Attack and Special Attack ×2 for Pikachu only; Fling paralysis is outside this hit scope',
'Light Clay':'Extends Reflect/Light Screen/Aurora Veil duration; current screens supplied explicitly',
'Mental Herb':'Consumed to cure supported mental move restrictions',
'Metronome':'Consecutive successful same-move damage modifiers [4096,4915,5734,6553,7372,8192]/4096, capped; resets on interrupted sequence/switch',
'Muscle Band':'Physical move base-power modifier 4505/4096',
'Normal Gem':'Consumed for a Normal-move power boost; consumption/history handler unresolved',
'Oran Berry':'Consumed for flat 10 HP recovery at threshold',
'Quick Claw':'Conditional same-priority move order override; activation distinct from possession',
'Red Card':'Consumed after damaging hit to force attacker switch',
'Rocky Helmet':'Contact retaliation HP loss after hit; separate from move damage',
'Scope Lens':'Raises critical stage; explicit critical branch remains required',
'Shed Shell':'Allows escape from trapping',
'Shell Bell':'Post-hit recovery proportional to damage inflicted',
'Sitrus Berry':'Consumed for quarter maximum HP recovery at threshold',
'Terrain Extender':'Extends terrain duration; current terrain supplied explicitly',
'White Herb':'Consumed to restore negative stat stages',
'Wide Lens':'Raises accuracy; not connected-hit power',
'Wise Glasses':'Special move base-power modifier 4505/4096',
'Zoom Lens':'Conditional accuracy boost after target acts; order history required for accuracy',
'Expert Belt':'Super-effective final-damage modifier 4915/4096',
}
for n,status in [('Aspear','freeze'),('Cheri','paralysis'),('Chesto','sleep'),('Lum','status/confusion'),('Pecha','poison'),('Persim','confusion'),('Rawst','burn')]:effects[n+' Berry']='Consumed to cure '+status+'; current status supplied explicitly'
for n,w in [('Damp','rain'),('Heat','sun'),('Icy','snow'),('Smooth','sand')]:effects[n+' Rock']='Extends '+w+' duration; current weather supplied explicitly'
seed={'Electric Seed','Grassy Seed','Misty Seed','Psychic Seed'}
trigger=seed|{'Air Balloon','Quick Claw'}
rare={'Iron Ball','Metronome','Binding Band','Big Root','Focus Band','Oran Berry','Leppa Berry','Shell Bell','Zoom Lens'}
rows={}
for iid in k.facts['items']:
 n=name(iid,'item');key=normalize(n);b,lo,hi=base[key];override=mods.get(key)
 required=[f for f,v in k.facts['pokemon'].items() if v.get('required_item')==n]
 stones=bool(required or 'megaStone:' in b)
 species=sorted({'pokeapi:species:'+str(k.entities[f].species_id) for f in required})
 if n=='Meowsticite':species=['pokeapi:species:678']
 category='species_specific' if stones or n in {'Light Ball','Leek'} else 'evidence_triggered' if n in trigger else 'rare_specialized' if n in rare else 'standard'
 effect='Enables species-specific Mega transformation; new stats and ability; no direct multiplier with current form/stats supplied' if stones else 'Boosts '+TYPE_ITEMS[n]+' move base power 4915/4096' if n in TYPE_ITEMS else 'Consumed to reduce matching incoming '+BERRIES[n]+' damage under trigger conditions' if n in BERRIES else effects[n]
 handler='existing_modifier' if n in ITEMS else 'current_form_stone' if stones else 'unresolved' if n=='Metronome' else 'normal_gem' if n=='Normal Gem' else 'light_ball' if n=='Light Ball' else 'grounding' if n in {'Air Balloon','Iron Ball'} else 'contextual_connected_hit'
 callbacks=sorted(set(re.findall(r'\b(on[A-Z]\w*)\s*\(',b)))
 rows[n]=dict(id=iid,name=n,category=category,primary_effect=effect,legal_champions=True,
 applicable_species=species if stones else ['pokeapi:species:25'] if n=='Light Ball' else ['pokeapi:species:83','pokeapi:species:865'] if n=='Leek' else 'all',
 applicable_forms=required if stones else 'all within applicable species',holding_restriction='compatible_stone_generation_only' if stones else 'none; effect eligibility is not holding legality',
 direct_damage='transformation' if stones else 'conditional' if n in set(TYPE_ITEMS)|set(BERRIES)|{'Life Orb','Wise Glasses','Muscle Band','Expert Belt','Light Ball','Metronome','Normal Gem','Focus Sash','Focus Band'} else 'no direct multiplier; explicit state required',
 speed_order=n in {'Choice Scarf','Iron Ball','Quick Claw'},grounding_field_defense=n in seed|{'Air Balloon','Iron Ball','Light Clay','Terrain Extender','Damp Rock','Heat Rock','Icy Rock','Smooth Rock','White Herb'} or stones,
 observable_message=dict(reference_callbacks=callbacks,reference_protocol_messages=sorted(set(re.findall(r"this\.add\(['\"]([^'\"]+)",b))),shared_consumption_hook=('useItem(' in b or 'eatItem(' in b),champions_ui_guarantee='unverified; missing recognition is not negative evidence'),
 lifecycle='transformation_bound' if stones else 'consumable' if n.endswith('Berry') or n in seed|{'Air Balloon','Eject Button','Red Card','Normal Gem','White Herb','Mental Herb','Focus Sash'} else 'conditional_persistent',
 historical_state_required=n not in set(TYPE_ITEMS)|set(BERRIES)|{'Wise Glasses','Muscle Band','Expert Belt','Light Ball'},
 forward_coverage=handler,recommended_candidate_policy=('compatible species/forms only; preserve transformation identity' if stones else 'dormant until positive reviewed evidence; no missing-message exclusion' if category=='evidence_triggered' else 'dormant unless enabled/observed; Iron Ball rescue only if ordinary Speed parents fail' if category=='rare_specialized' else 'include when effect-applicable; ineffective holding remains legal diagnostic alternative' if category=='species_specific' else 'include by default; share connected-hit computations only after contextual audit'),policy_reason='Explicit modeling policy, not measured usage frequency; standard includes relevant utility/defense items',
 sources=[dict(source='showdown_items',key=key,lines=[lo,hi]),dict(source='champions_items',key=key,lines=list(override[1:]) if override else None,inherit=not override or 'inherit: true' in override[0]),dict(source='canonical',id=iid)],
 uncertainty=['Community-reference mechanics, not independent Champions certification','Champions UI message guarantee not established']+(['Historical consecutive-move state not implemented'] if n=='Metronome' else ['Mega form identity/stats absent from pinned canonical catalog; no invented transformation'] if n=='Meowsticite' else []))
source={}
for label,p in [('showdown_items',root/'ps-data-items.ts'),('champions_items',root/'ps-data-mods-champions-items.ts'),('canonical',Path('knowledge/data/champions_facts.json'))]:
 source[label]=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url=('https://github.com/smogon/pokemon-showdown/blob/3a766f2cfb5e51c1e428cfe87d0dba91a8f01640/data/'+('items.ts' if label=='showdown_items' else 'mods/champions/items.ts')) if label!='canonical' else k.facts['source']['repository'] if 'source' in k.facts else 'knowledge/data/champions_facts.json',license='MIT' if label!='canonical' else 'existing KnowledgeBase source manifest',retrieved='2026-10-22',audited='2026-10-23')
p=Path('damage/data/item-classification-v1.json');p.write_text(json.dumps(dict(version='champions-item-classification-v1',profile='showdown-champions-reference-v1',sources=source,items=rows),ensure_ascii=False,indent=2)+'\n')
print(len(rows),'items',__import__('collections').Counter(r['category'] for r in rows.values()))

receipt=Path('.cache/m343b/wiki-receipts.json')
if receipt.exists():
 data=json.loads(p.read_text());data['corroboration']=json.loads(receipt.read_text());p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
