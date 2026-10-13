"""Tesseract adapter with explicit unavailable-language reporting."""
import cv2
import numpy as np
import re
import pytesseract
from models import Observation, RawOCR


class OCR:
    def __init__(self, language: str = "chi_sim+eng", threshold: float = 0.75):
        if not 0 <= threshold <= 1:
            raise ValueError('OCR threshold must be between 0 and 1')
        self.threshold = threshold
        self.warnings: list[str] = []
        try:
            available = set(pytesseract.get_languages(config=""))
            selected = [x for x in language.split("+") if x in available]
            missing = set(language.split("+")) - available
            if missing:
                self.warnings.append(f"Missing OCR languages: {', '.join(sorted(missing))}")
            self.language = "+".join(selected)
            if not selected:
                self.warnings.append("No requested OCR language available")
        except pytesseract.TesseractNotFoundError:
            self.language = ""
            self.warnings.append("Tesseract unavailable; text fields remain unknown")

    def read(self, image: np.ndarray, box: tuple[int,int,int,int], numeric: bool = False,
             multiline: bool = False, italic: bool = False) -> Observation:
        x1, y1, x2, y2 = box
        if not self.language:
            return Observation(region=box)
        crop = image[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if not numeric and not italic:
            scale = max(1.0,64/max(1,gray.shape[0]))
            gray = cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
        # Bright UI text on colored panels; retain grayscale for menu detail pages.
        if numeric and italic:
            hsv = cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
            gray = ((hsv[:,:,1] < 65) & (hsv[:,:,2] > 200)).astype('uint8')*255
        elif numeric or italic:
            gray = cv2.threshold(gray, 190, 255, cv2.THRESH_BINARY)[1]
        if italic or numeric:
            height, width = gray.shape
            shear = .35 if italic else .2
            gray = cv2.warpAffine(gray,np.float32([[1,shear,0],[0,1,0]]),
                                 (width+round(height*shear),height))
        if numeric or italic:
            gray = cv2.copyMakeBorder(gray,10,10,10,10,cv2.BORDER_CONSTANT,value=0)
            gray = 255-gray
        config = f"--psm {6 if multiline else 7}"
        if numeric:
            config += " -c tessedit_char_whitelist=0123456789/%"
        try:
            language = 'eng' if numeric else self.language
            if italic and not numeric and 'chi_sim' in self.language:
                language = 'chi_sim'
            data = pytesseract.image_to_data(gray, lang=language,
                                            config=config, output_type=pytesseract.Output.DICT,
                                            timeout=10)
        except (RuntimeError, pytesseract.TesseractError) as exc:
            warning = f"OCR failed: {exc}"
            if warning not in self.warnings:
                self.warnings.append(warning)
            return Observation(region=box)
        tokens = [(t.strip(), float(c) / 100) for t, c in zip(data['text'], data['conf'])
                  if t.strip() and float(c) >= 0]
        original = " ".join(t for t, _ in tokens)
        raw = original
        raw = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])','',raw)
        confidence = sum(c * len(t) for t, c in tokens) / max(1, sum(len(t) for t, _ in tokens))
        return Observation(raw if confidence >= self.threshold and raw else None,
                           round(confidence, 3), box, raw,
                           raw_ocr=RawOCR(original,round(confidence,3),box,language,
                               tokens=[{'text':t,'confidence':c} for t,c in tokens]))
