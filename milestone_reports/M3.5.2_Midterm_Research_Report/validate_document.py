"""Validate the packaged document and render representative pages for review."""
from pathlib import Path
import hashlib
import json
import re
import pymupdf

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CACHE=ROOT/'.cache/document-build/m352'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    tex=(HERE/'report.tex').read_text()
    summary=json.loads((HERE/'evidence-summary.json').read_text())
    used=set(re.findall(r'\\figone\{([^}]+)\}',tex))
    used.update(re.findall(r'\\includegraphics\[[^]]*\]\{figures/([^}]+)\}',tex))
    used={filename for filename in used if not filename.startswith('#')}
    expected={f['file']:f for f in summary['figure_provenance']}
    assert used==set(expected),(used,set(expected))
    assert len(used)==14
    for filename,receipt in expected.items():
        assert sha(HERE/'figures'/filename)==receipt['sha256'],filename
        if receipt['kind'].startswith('existing') and (ROOT/receipt['source']).exists():
            assert sha(ROOT/receipt['source'])==receipt['sha256'],filename
    optional_source_check=False
    study=ROOT/'.cache/research/m351'/summary['study_fingerprint']
    if study.exists():
        for filename,digest in summary['source_sha256'].items():
            assert sha(study/filename)==digest,filename
        optional_source_check=True
    assert summary['incineroar_k3_membership_cross_tab']==[[31,0,0],[3,7,14],[0,0,142]]
    assert summary['species']['Incineroar']['models']['sp']['candidates'][2]['sizes']==[31,24,142]
    assert summary['species']['Incineroar']['models']['learned']['candidates'][2]['sizes']==[34,7,156]
    assert summary['species']['Incineroar']['selected_k']['learned']==1
    log=CACHE/'report.log'
    if log.exists():
        content=log.read_text(errors='replace')
        assert not re.search(r'Overfull \\[hv]box|undefined references|undefined citations|LaTeX Warning:|^!',content,re.M), 'Inspect LaTeX log'
    document=pymupdf.open(HERE/'report.pdf')
    assert 12<=len(document)<=24,len(document)
    text='\n'.join(page.get_text() for page in document)
    for term in ('Introduction and motivation','Nonlinear training-allocation dissimilarity',
                 'Incineroar: primary comparison','Grouped, target-masked','Future research questions','Conclusion'):
        assert term in text,term
    assert not re.search(r'[\u4e00-\u9fff]',text),'Report must be English'
    image_count=sum(len(page.get_images()) for page in document)
    assert image_count==14,image_count
    for n,page in enumerate(document):
        assert len(page.get_text().split())>30,('Blank/sparse page',n+1)
        for word in page.get_text('words'):
            rect=pymupdf.Rect(word[:4])*page.rotation_matrix
            assert rect.x0>=-1 and rect.y0>=-1 and rect.x1<=page.rect.width+1 and rect.y1<=page.rect.height+1,('Page overflow',n+1,word)
    preview=CACHE/'review-pages';preview.mkdir(parents=True,exist_ok=True)
    selected=[]
    for i,page in enumerate(document):
        # Render all pages; inspect representative ones explicitly before delivery.
        page.get_pixmap(matrix=pymupdf.Matrix(1.4,1.4)).save(str(preview/f'page-{i+1:02}.png'))
        if any(t in page.get_text() for t in ('Nonlinear training-allocation','Incineroar: primary','Grouped, target-masked','Conclusion')):
            selected.append(i+1)
    archive=json.loads((ROOT/'milestone_reports/Previous_Milestones/archive-provenance.json').read_text())
    for entry in archive:
        assert sha(ROOT/'milestone_reports'/entry['archive'])==entry['archive_sha256']
        if (ROOT/entry['source']).exists():assert sha(ROOT/entry['source'])==entry['source_sha256']
        for img in entry['images']:assert sha(ROOT/'milestone_reports'/img['file'])==img['sha256']
    result=dict(pages=len(document),figure_appearances=image_count,original_figures=11,new_presentation_figures=3,
                optional_local_study_hash_check=optional_source_check,archives=len(archive),
                pdf_sha256=sha(HERE/'report.pdf'),representative_text_pages=selected,
                preview_directory=str(preview.relative_to(ROOT)),status='passed',
                interpretation='Document integrity/layout checks; visual review and scientific acceptance are separate.')
    (CACHE/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
