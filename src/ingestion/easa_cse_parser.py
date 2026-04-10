#!/usr/bin/env python3
"""
EASA CS-E Document Parser
Parse EASA CS-E Certification Specifications for Engines
"""

import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set

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


class CS_E_Parser:
    """Parse EASA CS-E engine regulations"""

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

        # Find Book 2 start (end of Book 1 content)
        book2_start = self._find_book2_start()
        print(f"Book 1 ends at page: {book2_start}")

        # Locate subparts
        self._locate_subparts(book2_start)

        # Extract sections for each subpart
        for subpart in self.subparts:
            self._extract_sections(subpart, book2_start)

        # Build structure
        structure = self._build_structure()

        return {
            "doc_name": "CS-E",
            "doc_title": "EASA CS-E - Certification Specifications for Engines",
            "ccar_number": "CS-E",
            "agency": "EASA",
            "total_pages": total_pages,
            "total_sections": self.total_sections,
            "total_subparts": len(self.subparts),
            "parse_quality": "good",
            "document_type": "text_based",
            "structure": structure
        }

    def _find_book2_start(self) -> int:
        """Find where Book 2 starts (skip TOC which is around page 2)"""
        # Start from page 20 to skip TOC and early pages
        for page_num in range(20, len(self.doc)):
            page = self.doc[page_num]
            text = page.get_text()
            if 'BOOK 2' in text:
                return page_num
        return len(self.doc)

    def _locate_subparts(self, book2_start: int):
        """Locate subparts within Book 1"""
        # Known subpart structure from TOC
        subpart_info = {
            "A": ("GENERAL", 2),
            "B": ("PISTON ENGINES; DESIGN AND CONSTRUCTION", 26),
            "C": ("PISTON ENGINES; TYPE SUBSTANTIATION", 28),
        }

        for sp_id, (title, default_page) in subpart_info.items():
            self.subparts.append(Subpart(id=sp_id, title=title, page=default_page))

        print(f"Initialized {len(self.subparts)} subparts")

    def _extract_sections(self, subpart: Subpart, book2_start: int):
        """Extract all sections within a subpart"""
        # Determine page range
        start_page = subpart.page - 1
        subpart_index = self.subparts.index(subpart)
        if subpart_index < len(self.subparts) - 1:
            end_page = self.subparts[subpart_index + 1].page - 1
        else:
            end_page = book2_start

        # Track unique sections
        seen_sections: Set[str] = set()
        sections_list: List[Section] = []

        for page_num in range(start_page, min(end_page, len(self.doc))):
            page = self.doc[page_num]
            text = page.get_text()

            # Find section headers with titles
            # Pattern: CS-E XXX followed by title on same or next line
            lines = text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Check if line contains CS-E section number
                match = re.match(r'^CS-E\s+(\d+[a-z]*)\s+(.+)$', line, re.IGNORECASE)
                if match:
                    section_num = match.group(1)
                    title = match.group(2).strip()

                    # Clean and validate title
                    title = self._clean_title(title)
                    if title and len(title) > 2:
                        full_num = f"E.{section_num}"
                        if full_num not in seen_sections:
                            seen_sections.add(full_num)
                            sections_list.append(Section(
                                number=full_num,
                                title=f"§ E.{section_num} {title}",
                                page=page_num + 1,
                                summary=f"§ E.{section_num} {title}"
                            ))
                else:
                    # Check if line is just a section number, title is on next line
                    match = re.match(r'^CS-E\s+(\d+[a-z]*)\s*$', line, re.IGNORECASE)
                    if match and i + 1 < len(lines):
                        section_num = match.group(1)
                        title = lines[i + 1].strip()

                        # Skip if next line looks like subsection (a), etc.
                        if not re.match(r'^\([a-z]\)', title) and len(title) > 2:
                            title = self._clean_title(title)
                            full_num = f"E.{section_num}"
                            if full_num not in seen_sections:
                                seen_sections.add(full_num)
                                sections_list.append(Section(
                                    number=full_num,
                                    title=f"§ E.{section_num} {title}",
                                    page=page_num + 1,
                                    summary=f"§ E.{section_num} {title}"
                                ))

                i += 1

        # Sort sections by number
        def section_key(s: Section) -> int:
            try:
                return int(s.number.split('.')[1])
            except (ValueError, IndexError):
                return 999999

        sections_list.sort(key=section_key)
        subpart.sections = sections_list
        self.total_sections += len(subpart.sections)

        print(f"  Subpart {subpart.id}: {len(subpart.sections)} sections")

    def _clean_title(self, title: str) -> str:
        """Clean up section title"""
        # Remove trailing artifacts
        title = re.sub(r'\s*-\s*$', '', title)
        title = re.sub(r'\.{3,}$', '', title)
        title = re.sub(r'\s+', ' ', title)

        # Remove common non-title patterns
        if re.match(r'^\([a-z]\)', title):
            return ""
        if re.match(r'^\d+$', title):
            return ""
        if title in ['CS-E', 'BOOK', 'AMC', 'Annex']:
            return ""

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
        print("Usage: python easa_cse_parser.py <pdf_path> [output_path]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "data/processed/CS-E_structure.json"

    parser = CS_E_Parser(pdf_path)
    parser.save(output_path)


if __name__ == "__main__":
    main()
