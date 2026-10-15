"""Record each sampled text mask independently of OCR scheduling decisions."""
import hashlib
from .message_selection import features,SelectionConfig


class RepeatEvidence:
    def __init__(self):
        self.anchor=None

    def observe(self,row,image):
        f=features(image,SelectionConfig());mask_sha=hashlib.sha256(f['mask'].tobytes()).hexdigest()
        result=dict(source_sha256=row['sha256'],timestamp=row['timestamp'],text_mask_sha256=mask_sha,
                    ocr_selected=bool(row['selection']['selected']),suppressed=False)
        if row['selection']['reason']=='unchanged_text_mask' and self.anchor:
            result.update(suppressed=True,anchor_sha256=self.anchor['source_sha256'],
                          anchor_timestamp=self.anchor['timestamp'],
                          exact_mask=mask_sha==self.anchor['text_mask_sha256'],
                          similarity=row['selection']['repeat_similarity'],
                          basis='masked scheduling equivalence; no new OCR or semantic/continuous-state assertion')
        if row['selection']['selected']:self.anchor=result.copy()
        elif row['selection']['reason'] in {'phase_or_log_excluded','insufficient_message_evidence'}:self.anchor=None
        return result
