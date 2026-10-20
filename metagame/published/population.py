"""Explicit negative source evidence excludes simulator designs from game analysis."""
import re


def exclusion(record):
    metadata=record.get('metadata',{})
    text=record.get('title','')+' '+str(metadata.get('event') or '')
    if re.search(r'\bshowdown\b',text,re.I):
        return 'Explicit Pokémon Showdown source context; excluded from Champions in-game design population'
    return None
