"""Audited source-specific readers; no hidden API or generic team crawler."""
import re
from metagame.parser import POINT_COLUMNS
from .html import DOM, Node

SOURCES={
 'pokedaily':dict(url='https://pokedaily.net/champions/rentals/',population='community_published',
   attribution='Team designs credited to their named creators; curated by Daily Pokemon',
   terms='https://pokedaily.net/terms/',rights='non-commercial reproduction with attribution/link; creator rights retained',
   max_records=6,format='Unknown',regulation='M-C'),
 'vgcmulticalc':dict(url='https://vgcmulticalc.com/teams/',population='tournament_published',
   attribution='VGC Multicalc / VGCPastes and named creators',terms=None,
   rights='public factual cards; broad redistribution license unknown; private pilot only',
   max_records=10,format='Doubles',regulation='M-C')}
STAT_KEYS={'HP':0,'Atk':1,'Def':2,'SpA':3,'SpD':4,'Spe':5}


def points(text):
    values=[None]*6
    seen=set()
    for part in text.split('/'):
        match=re.fullmatch(r'\s*(\d+)\s+(HP|Atk|Def|SpA|SpD|Spe)\s*',part)
        if not match or match[2] in seen:raise ValueError('Unrecognized/duplicate allocation component')
        seen.add(match[2]);values[STAT_KEYS[match[2]]]=int(match[1])
    deductions=[]
    # No arbitrary zero filling. This deduction requires the verified global
    # budget and source's explicit SP classification, checked by the caller.
    if sum(v for v in values if v is not None)==66 and all(v is None or 0<=v<=32 for v in values):
        deductions=[i for i,v in enumerate(values) if v is None]
        values=[0 if v is None else v for v in values]
    return values,deductions


def parse_export(text, *, source_sp_lines=None):
    members=[]
    blocks=re.split(r'\n\s*\n',text.strip().replace('\r\n','\n'))
    for index,block in enumerate(blocks):
        lines=[l.strip() for l in block.splitlines() if l.strip()]
        if not lines:continue
        header=lines.pop(0)
        name,sep,item=header.rpartition(' @ ')
        if not sep:name,item=header,None
        gender=None
        match=re.search(r'\s+\(([MF])\)$',name)
        if match:gender=match[1];name=name[:match.start()]
        # Nickname (Species) is the conventional paste syntax; the nickname
        # never enters either fingerprint.
        match=re.search(r'\(([^()]+)\)$',name)
        if match:name=match[1]
        mon=dict(species=name,item=item,ability=None,nature=None,moves=[],
            sp=dict(kind='unknown',values=[None]*6),configuration={},unsupported_fields=[],conflicts=[],evidence={})
        if gender:mon['configuration']['gender']=gender
        point_line=None
        for line in lines:
            if line.startswith('Ability: '):
                value=line[9:]
                if mon['ability'] is not None:mon['conflicts'].append('duplicate_ability')
                mon['ability']=value
            elif line.endswith(' Nature'):
                if mon['nature'] is not None:mon['conflicts'].append('duplicate_nature')
                mon['nature']=line[:-7]
            elif line.startswith('- '):mon['moves'].append(line[2:])
            elif line.startswith(('EVs: ','SPs: ','SP: ')):
                if point_line is not None:mon['conflicts'].append('duplicate_spread')
                point_line=line.split(': ',1)[1]
            elif line.startswith(('Shiny: ','Happiness: ')):
                # Shiny is cosmetic. Happiness is retained as configuration:
                # it can affect moves; it is not silently discarded.
                if line.startswith('Happiness: '):mon['configuration']['happiness']=line[11:]
            elif line.startswith('Level: '):
                mon['evidence']['published_level']=line[7:]
                # Champions' pinned stat profile does not depend on level.
            elif line.startswith('IVs: '):
                mon['evidence']['published_ivs']=line[5:]
                # Champions has no IV stat input under the maintained profile.
            else:mon['unsupported_fields'].append(line)
        if point_line:
            if source_sp_lines is not None and index < len(source_sp_lines):
                visible=source_sp_lines[index]
                if point_line!=visible:mon['conflicts'].append('visible_sp_export_disagreement')
                else:
                    values,deduced=points(point_line)
                    mon['sp']=dict(kind='champions_sp',values=values)
                    mon['evidence']['sp_semantics']='Visible SP label corroborates export allocation; not generic EV inference'
                    mon['evidence']['zero_components_deduced_from_66_budget']=deduced
            else:
                mon['evidence']['untyped_allocation']=point_line
        members.append(mon)
    return members


def pokedaily(raw):
    root=DOM(raw).root
    if 'Regulation M-C' not in root.text():raise ValueError('PokeDaily regulation heading changed')
    result=[]
    for section in root.find('section'):
        if section.attrs.get('class')!='rt-team':continue
        exports=list(section.find('textarea'));sheets=[n for n in section.find('li') if n.attrs.get('class')=='sh-mon']
        if len(exports)!=1 or len(sheets)!=6:raise ValueError('PokeDaily team sheet layout changed')
        fields=[]
        primary=[]
        for sheet in sheets:
            keys=[n.text().strip() for n in sheet.find('dt')]
            vals=[n.text().strip() for n in sheet.find('dd')]
            if len(keys)!=len(vals):raise ValueError('Incomplete team sheet definitions')
            fields.append(dict(zip(keys,vals)))
            primary.append(dict(zip(keys,[''.join(c for c in n.children if isinstance(c,str)).strip()
                for n in sheet.find('dd')])))
        if any('SP' not in f for f in fields):raise ValueError('No corroborating SP label')
        text=exports[0].text();members=parse_export(text,source_sp_lines=[f['SP'] for f in fields])
        if len(members)!=6:raise ValueError('Not a six-Pokémon export')
        for mon,visible,first in zip(members,fields,primary):
            if visible.get('Item')!=mon['item'] or visible.get('Nature')!=mon['nature']:
                mon['conflicts'].append('visible_build_export_disagreement')
            if first.get('Ability')!=mon['ability']:
                mon['conflicts'].append('visible_ability_export_disagreement')
            mon['evidence']['visible_sheet']=visible
        title=next(section.find('h2')).text().strip()
        top=next(n for n in section.find('div') if n.attrs.get('class')=='rt-top')
        from datetime import datetime
        posted=re.search(r'posted ([A-Za-z]+ \d{1,2}, \d{4})',top.text())
        seen=re.search(r'code seen ([A-Za-z]+ \d{1,2}, \d{4})',top.text())
        result.append(dict(source_key=section.attrs['id'],title=title,source_url=SOURCES['pokedaily']['url']+'#'+section.attrs['id'],
            population='community_published',regulation='M-C',format='Unknown',pokemon=members,
            metadata=dict(attribution=top.text().strip(),original_export=text,visible_fields=fields,
                rental_code=section.attrs['id'].upper(),
                published_date=datetime.strptime(posted[1],'%B %d, %Y').date().isoformat() if posted else None,
                code_seen_date=datetime.strptime(seen[1],'%B %d, %Y').date().isoformat() if seen else None,
                format_evidence='The page names M-C but does not state Singles/Doubles; retained as Unknown',
                declaration='Creator-published rental design as curated; code not independently verified')))
    if not result:raise ValueError('No expected PokeDaily team records')
    return result


def vgcmulticalc(raw):
    root=DOM(raw).root
    if 'Regulation M-C' not in root.text():raise ValueError('VGC Multicalc regulation changed')
    result=[]
    for article in root.find('article'):
        if article.attrs.get('data-cy')!='community-team-mobile':continue
        text=article.text().strip()
        if 'Louisville Regional 2027' not in text:
            raise ValueError('Pilot card population/event changed; review classification')
        pokemon=[]
        for img in article.find('img'):
            src=img.attrs.get('src','')
            if '/pokemon-champions/' in src:
                pokemon.append(dict(species=img.attrs.get('alt'),item=None,moves=[],
                    sp=dict(kind='unknown',values=[None]*6)))
            elif '/items/' in src and pokemon:pokemon[-1]['item']=img.attrs.get('alt')
        if len(pokemon)!=6:raise ValueError('Tournament card does not expose six members')
        title=next(article.find('button')).text().replace('chevron_right','').strip()
        from metagame.common import sha
        source_key=sha(title.encode())[:24]
        result.append(dict(source_key=source_key,title=title,source_url=SOURCES['vgcmulticalc']['url'],
            population='tournament_published',regulation='M-C',format='Doubles',pokemon=pokemon,
            metadata=dict(attribution=text,locator=dict(title=title,attribute='data-cy=community-team-mobile'),
                event='Louisville Regional 2027',links=[n.attrs.get('href') for n in article.find('a')],
                missing='Only the displayed six species and item image labels; SP badges do not supply allocations')))
    if not result:raise ValueError('No expected tournament cards')
    return result


def extract(source, raw, limit=None):
    policy=SOURCES[source]
    rows={'pokedaily':pokedaily,'vgcmulticalc':vgcmulticalc}[source](raw)
    maximum=policy['max_records'] if limit is None else limit
    if type(maximum) is not int or not 1<=maximum<=policy['max_records']:
        raise ValueError('Collection exceeds the audited bounded pilot')
    return rows[:maximum]
