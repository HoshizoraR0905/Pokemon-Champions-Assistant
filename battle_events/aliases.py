"""Display-name lookup is not canonical species-name normalization.

NFKC, casefold, and whitespace removal only. Punctuation is retained. A key is
a search key, never proof two raw labels belong to the same individual.
"""
import unicodedata


def alias_key(raw):
    return ''.join(unicodedata.normalize('NFKC',raw).casefold().split())


def substitutions(text,bindings,side='unknown'):
    normalized=alias_key(text);groups={};used=[];conflicts=[]
    for raw,binding in bindings.items():
        if not binding.get('evidence'):continue
        if side!='unknown' and binding.get('side',side)!=side:continue
        groups.setdefault(alias_key(raw),[]).append((raw,binding))
    for key,rows in sorted(groups.items(),key=lambda r:-len(r[0])):
        if not key or key not in normalized:continue
        claims={(r[1]['identity']['canonical_id'],r[1].get('instance_id')) for r in rows}
        if len(claims)!=1:
            # Mask a colliding alias even if it happens to spell a species name.
            normalized=normalized.replace(key,'未定昵称');conflicts.append(key);continue
        binding=rows[0][1]
        normalized=normalized.replace(key,binding['identity']['name']);used.append(binding)
    return normalized,used,conflicts
