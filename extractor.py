import json
import logging
import re
import sys
import warnings
from pathlib import Path
from typing import Optional, Dict, List

warnings.filterwarnings("ignore")

try:
    import fitz  # PyMuPDF
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyMuPDF"])
    import fitz

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDFStructureExtractor:
    def __init__(self):
        self.h1_patterns = [r"^([A-Z][A-Z\s]{4,}|[IVXLCDM]+\s|[1-9]\s)", r"^Chapter\s+\d+", r"^Appendix\s+[A-Z0-9]+"]
        self.h2_patterns = [r"^\d+\.\d+", r"^\([a-z]\)", r"^[a-z]\)"]
        self.h3_patterns = [r"^\d+\.\d+\.\d+", r"^\([0-9]+\)"]

        self.heading_keywords = {
            "introduction", "summary", "conclusion", "overview", "abstract", "references",
            "appendix", "contents", "table of contents", "acknowledgements"
        }

    def extract_title(self, doc) -> str:
        candidates = []
        for page_num in range(min(2, doc.page_count)):
            page = doc[page_num]
            for b in page.get_text("dict")["blocks"]:
                if "lines" not in b: continue
                for l in b["lines"]:
                    for s in l["spans"]:
                        txt = s["text"].strip()
                        if 10 < len(txt) < 150 and not txt.islower():
                            candidates.append((txt, s["size"], page_num))
        if not candidates:
            return ""
        candidates.sort(key=lambda x: (-x[1], x[2]))
        return candidates[0][0]

    def is_heading(self, text: str) -> Optional[str]:
        text = text.strip()
        if len(text.split()) > 20 or len(text) > 150:
            return None

        for pat in self.h3_patterns:
            if re.match(pat, text): return "H3"
        for pat in self.h2_patterns:
            if re.match(pat, text): return "H2"
        for pat in self.h1_patterns:
            if re.match(pat, text): return "H1"

        if text.lower() in self.heading_keywords or text.isupper():
            return "H1"
        return None

    def extract_outline(self, doc) -> List[Dict]:
        outline = []
        seen = set()
        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    full_line = " ".join([span["text"].strip() for span in line.get("spans", [])])
                    full_line = full_line.strip()
                    if not full_line:
                        continue
                    level = self.is_heading(full_line)
                    key = (full_line.lower(), page_num)
                    if level and key not in seen:
                        seen.add(key)
                        outline.append({
                            "level": level,
                            "text": full_line,
                            "page": page_num + 1  # Convert to 1-based indexing
                        })
        return outline

    def extract_structure(self, pdf_path: Path) -> Dict:
        try:
            doc = fitz.open(pdf_path)
            title = self.extract_title(doc)
            outline = self.extract_outline(doc)
            return {
                "title": title,
                "outline": outline
            }
        except Exception as e:
            logger.error(f"Failed to process {pdf_path.name}: {e}")
            return {
                "title": pdf_path.stem,
                "outline": []
            }

def process_pdfs():
    input_dir = Path("/app/input")  # IMPORTANT: use this in Docker
    output_dir = Path("/app/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    extractor = PDFStructureExtractor()
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in input directory.")
        return

    for pdf_file in pdf_files:
        logger.info(f"Processing {pdf_file.name}")
        result = extractor.extract_structure(pdf_file)
        output_file = output_dir / f"{pdf_file.stem}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved output to {output_file.name}")

if __name__ == "__main__":
    process_pdfs()
