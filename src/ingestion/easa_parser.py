#!/usr/bin/env python3
"""
EASA CS-25 Document Parser
Parse EASA CS-25 Certification Specifications for Large Aeroplanes
"""

import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


@dataclass
class Section:
    """Single regulation section"""
    number: str
    title: str
    page: int
    content_parts: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class Subpart:
    """A subpart (like Subpart A, B, etc.)"""
    id: str
    title: str
    page: int
    sections: List[Section] = field(default_factory=list)


class EASAParser:
    """Parse EASA aviation regulations"""

    # Standard CS-25 subparts with actual page numbers (determined from document)
    STANDARD_SUBPARTS = {
        "A": ("GENERAL", 8),
        "B": ("FLIGHT", 9),
        "C": ("STRUCTURE", 30),
        "D": ("DESIGN AND CONSTRUCTION", 54),
        "E": ("POWERPLANT", 91),
        "F": ("EQUIPMENT", 112),
        "G": ("OPERATING LIMITATIONS AND INFORMATION", 134),
        "J": ("AUXILIARY POWER UNIT INSTALLATION", 150),  # Will be located dynamically
    }

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.doc = None
        self.subparts: List[Subpart] = []
        self.total_sections = 0

    def parse(self) -> Dict:
        """Parse the PDF document"""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

        if fitz is None:
            raise ImportError("PyMuPDF (fitz) is required. Install: pip install PyMuPDF")

        print(f"Opening: {self.pdf_path}")
        self.doc = fitz.open(self.pdf_path)
        total_pages = len(self.doc)

        print(f"Total pages: {total_pages}")

        # Initialize standard subparts
        self._init_standard_subparts()

        # Find actual page numbers for subparts
        self._locate_subpart_pages()

        # Extract sections for each subpart
        for subpart in self.subparts:
            self._extract_sections(subpart)

        # Build structure
        structure = self._build_structure()

        return {
            "doc_name": "CS-25",
            "doc_title": "EASA CS-25 - Certification Specifications for Large Aeroplanes",
            "ccar_number": "CS-25",
            "agency": "EASA",
            "total_pages": total_pages,
            "total_sections": self.total_sections,
            "total_subparts": len(self.subparts),
            "parse_quality": "good",
            "document_type": "text_based",
            "structure": structure
        }

    def _init_standard_subparts(self):
        """Initialize standard CS-25 subparts"""
        for sp_id, (title, page) in self.STANDARD_SUBPARTS.items():
            self.subparts.append(Subpart(id=sp_id, title=title, page=page))
        print(f"Initialized {len(self.subparts)} standard subparts")

    def _locate_subpart_pages(self):
        """Find actual page numbers for each subpart"""
        for i, subpart in enumerate(self.subparts):
            # Search range for this subpart
            start_search = max(0, subpart.page - 5)
            end_search = min(len(self.doc), subpart.page + 50)

            for page_num in range(start_search, end_search):
                page = self.doc[page_num]
                text = page.get_text()

                # Look for "SUBPART X - TITLE" pattern or "1-X-1" page marker
                if f'SUBPART {subpart.id}' in text.upper() or f'1-{subpart.id}-1' in text:
                    subpart.page = page_num + 1
                    break

        # Sort subparts by page number
        self.subparts.sort(key=lambda sp: sp.page)

        print("Subpart locations:")
        for sp in self.subparts:
            print(f"  Subpart {sp.id} (page {sp.page}): {sp.title}")

    def _extract_sections(self, subpart: Subpart):
        """Extract all sections within a subpart"""
        # Determine page range
        start_page = subpart.page - 1
        subpart_index = self.subparts.index(subpart)
        if subpart_index < len(self.subparts) - 1:
            end_page = self.subparts[subpart_index + 1].page - 1
        else:
            end_page = len(self.doc)

        # Pattern for CS 25.xxx - can be followed by title on same or next line
        section_pattern = re.compile(r'^\s*CS\s*25\.(\d+[a-z]*(?:\.\d+[a-z]*)*)\s*$', re.MULTILINE)

        current_sections = {}

        for page_num in range(start_page, min(end_page, len(self.doc))):
            page = self.doc[page_num]
            text = page.get_text()

            # Find all section markers
            for match in section_pattern.finditer(text):
                section_num = "25." + match.group(1)

                # Get title from next lines
                start_pos = match.end()
                next_newline = text.find('\n', start_pos)
                if next_newline != -1:
                    # Get text until next section marker or end
                    remaining = text[next_newline + 1:]

                    # Find the title (usually the next non-empty line)
                    lines = remaining.split('\n')
                    title = ""
                    for line in lines[:5]:
                        line = line.strip()
                        # Skip empty lines, page numbers, and section markers
                        if line and not re.match(r'^\d+$', line) and not re.match(r'^CS\s*25\.', line):
                            # Skip common non-title patterns
                            if not re.match(r'^\([a-z]\)', line) and \
                               not re.match(r'^\d+–\d+–\d+', line) and \
                               line not in ['BOOK', 'AMC', 'CS-25', 'CS–25']:
                                title = line
                                break

                    if title:
                        # Clean up title
                        title = self._clean_title(title)
                        if title and len(title) > 2:
                            if section_num not in current_sections:
                                current_sections[section_num] = Section(
                                    number=section_num,
                                    title=f"§ {section_num} {title}",
                                    page=page_num + 1,
                                    summary=f"§ {section_num} {title}"
                                )

        # Sort and add sections
        def section_key(s):
            parts = s.number.split('.')
            return [int(p) if p.isdigit() else p for p in parts]

        sorted_sections = sorted(current_sections.values(), key=section_key)
        subpart.sections = sorted_sections
        self.total_sections += len(subpart.sections)

        print(f"  Subpart {subpart.id}: {len(subpart.sections)} sections")

    def _clean_title(self, title: str) -> str:
        """Clean up section title"""
        # Remove trailing partial words and common artifacts
        title = re.sub(r'\s*-\s*$', '', title)
        title = re.sub(r'\.{3,}$', '', title)
        title = re.sub(r'\([a-z]\)\s*$', '', title)
        title = re.sub(r'\s+', ' ', title)

        # Limit title length
        if len(title) > 150:
            title = title[:150].rsplit(' ', 1)[0] + '...'

        return title.strip()

    def _build_structure(self) -> Dict:
        """Build the structure dictionary"""
        chapters = []

        for subpart in self.subparts:
            chapter_data = {
                "id": subpart.id,
                "title": f"{subpart.id} - {subpart.title}",
                "page": subpart.page,
                "sections": []
            }

            for section in subpart.sections:
                section_data = {
                    "number": section.number,
                    "title": section.title,
                    "page": section.page,
                    "content_parts": section.content_parts,
                    "summary": section.summary
                }
                chapter_data["sections"].append(section_data)

            chapters.append(chapter_data)

        return {"chapters": chapters}

    def save(self, output_path: str):
        """Parse and save to JSON"""
        data = self.parse()

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\nSaved: {output_file}")
        print(f"Total sections: {data['total_sections']}")
        print(f"Total subparts: {data['total_subparts']}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python easa_parser.py <pdf_path> [output_path]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "data/processed/CS-25_structure.json"

    parser = EASAParser(pdf_path)
    parser.save(output_path)


if __name__ == "__main__":
    main()
