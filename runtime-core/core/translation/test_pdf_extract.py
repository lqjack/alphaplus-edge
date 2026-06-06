"""Manual legacy PDF extraction smoke script.

The original helper depended on an external `utils.parse_pdfs` package that is
not shipped in this repository and executed broken test code at import time.
Keep it available for direct/manual use, but skip it under pytest collection.
"""

import logging
import os
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.skip(
    reason="Manual legacy PDF extraction smoke script; external parser not bundled."
)


def extract_pdf_text(pdf_path: str | Path) -> str:
    from utils.parse_pdfs.extract_pdfs import extract_paper_info

    pdf_path = Path(pdf_path)
    extract_paper_info(str(pdf_path))
    extracted_path = pdf_path.with_name(f"{pdf_path.stem}_extracted.txt")
    return extracted_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    resources_dir = Path("resources/pdfs")
    for file_name in os.listdir(resources_dir):
        pdf_path = resources_dir / file_name
        logger.info("file name: %s", file_name)
        text = extract_pdf_text(pdf_path)
        logger.info("文件提取结果：%s", text)
