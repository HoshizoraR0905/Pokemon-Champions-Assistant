"""Explicit offline generation of new Speed fixtures; no Python Speed implementation imported."""
import json,subprocess,hashlib
from copy import deepcopy
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
example=json.load(open('examples/speed_order/compare.json'))['input']['context'];p=example['own'];field=example['field']
mods=[('neutral',{}),('Tailwind',{'tailwind':True}),('Scarf',{'item':'Choice Scarf'}),('paralysis',{'status':'paralysis'}),('Iron Ball',{'item':'Iron Ball'}),('combined',{'tailwind':True,'item':'Choice Scarf','status':'paralysis'})]
groups=[]
for name,changes in mods:
 actor=dict(p,**changes);groups.append(dict(id=name,participant=actor,field=deepcopy(field)))
for ability,weather in [('Swift Swim','rain'),('Chlorophyll','sun'),('Sand Rush','sand'),('Slush Rush','snow')]:
 for active in [False,True]:
  actor=dict(p,ability=ability);f=dict(field,weather=weather if active else 'none')
  groups.append(dict(id=ability+str(active),participant=actor,field=f))
for ability,changes in [('Unburden',dict(unburden_active=True,activation_evidence='Item loss before ordering decision.')),('Unburden',dict(unburden_active=False,activation_evidence='No activation before decision.')),('Quick Feet',dict(status='paralysis')),('Surge Surfer',{})]:
 actor=dict(p,ability=ability,**changes);f=dict(field,terrain='electric' if ability=='Surge Surfer' else 'none');groups.append(dict(id=ability+str(len(groups)),participant=actor,field=f))
for g in groups:g.update(candidates=[1,3,99,100,101,333,4095],stages=list(range(-6,7)))
cache=Path('.cache/m32');(cache/'oracle-inputs.json').write_text(json.dumps(dict(groups=groups)))
r=subprocess.run(['node','scripts/speed_oracle.cjs',str(cache/'oracle-inputs.json')],capture_output=True,text=True,check=True)
target=Path('tests/fixtures/speed_order/reference.json');target.write_text(r.stdout)
files=[str(target),'scripts/speed_oracle.cjs','speed_order/data/sources-v1.json','damage/data/manifest.json','knowledge/data/manifest.json']
Path('tests/fixtures/speed_order/manifest.json').write_text(json.dumps(dict(files={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files}),indent=2)+'\n')
print(len(groups),'groups',sum(len(g['rows']) for g in json.loads(r.stdout)['groups']),'rows')
