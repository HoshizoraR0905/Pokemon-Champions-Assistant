"""Parse a supplied 52Poke Chinese title article snapshot, without network access.

Only the table with verified headings is read. Champions overrides are selected;
dynamic trainer-name templates remain unsupported. No species IDs are invented.
"""
import argparse
import hashlib
from html import unescape
import json
from pathlib import Path
import re


def text(value):
    return unescape(re.sub('<[^>]+>', '', value)).strip()


def parse_titles(html):
    heading = re.search(r'<th[^>]*>\s*序号\s*</th>\s*<th[^>]*>\s*称号\s*</th>\s*<th[^>]*>\s*对应奖章／证章\s*</th>\s*</tr>', html)
    if heading is None:
        raise ValueError('Expected title table headings are missing')
    body = html[heading.end():].split('</table>', 1)[0]
    rows = {}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', body, re.S):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(cells) != 3 or not text(cells[0]).isdigit():
            raise ValueError('Unexpected title table row')
        number = int(text(cells[0]))
        variants = re.split(r'<br\s*/?>', cells[1])
        champions = [v for v in variants if 'Champions' in v]
        chosen = champions[-1] if champions else variants[0]
        title = text(re.sub(r'<sup\b.*?</sup>', '', chosen, flags=re.S))
        record = dict(number=number, title=title, award=text(cells[2]),
                      game='Pokémon Champions', language='zh-Hans',
                      applicability='Champions override' if champions else 'article documents HOME-carried titles in Champions',
                      supported='<' not in title and '>' not in title)
        if number in rows and rows[number] != record:
            raise ValueError('Conflicting duplicate title rows')
        rows[number] = record
    if set(rows) != set(range(1, 113)):
        raise ValueError('Unexpected article row coverage; review changes before updating snapshot')
    assert rows[56]['title'] == '开始犯困的'
    return list(rows.values())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--html', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); html = a.html.read_text()
    revisions = set(re.findall(r'oldid=(\d+)', html))
    if len(revisions) != 1:
        raise ValueError('Missing or ambiguous article revision')
    data = dict(schema_version=1, version='52poke-titles-2026-10-19-v1',
                source=dict(url='https://wiki.52poke.com/zh-hans/称号', revision_id=int(next(iter(revisions))),
                            retrieved_date='2026-10-19', game='Pokémon Champions',
                            html_sha256=hashlib.sha256(a.html.read_bytes()).hexdigest(),
                            attribution='神奇宝贝百科 / 52Poké contributors',
                            license='CC BY-NC-SA 3.0', license_url='https://creativecommons.org/licenses/by-nc-sa/3.0/'),
                limitation='Chinese static Pokemon title strings only. This is not the Champions trainer achievements table. Unknown titles and variable trainer-name titles abstain.',
                titles=parse_titles(html))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    print(len(data['titles']), 'title rows; revision', data['source']['revision_id'])


if __name__ == '__main__':
    main()
