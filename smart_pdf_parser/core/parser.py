"""
Core PDF parsing functionality.

This module handles the extraction of content from PDF files using PyMuPDF (fitz).
"""

import fitz  # PyMuPDF
import re
import os
from typing import List, Dict, Any, Tuple, Optional, Set, Union
from collections import defaultdict, Counter
import logging

from ..models.document import Document, Section, Table
from ..utils.exceptions import PDFInputError, PDFStructureError, TableExtractionError
from ..utils.logger import get_logger
from ..utils.validators import validate_pdf_file

logger = get_logger(__name__)

class PDFParser:
    """Main class for parsing PDF documents and extracting structured content."""
    
    def __init__(self, 
                 detect_tables: bool = True, 
                 use_toc: bool = True,
                 detect_headings: bool = True,
                 min_heading_size: float = 12.0,
                 heading_size_threshold: float = 1.2):
        """
        Initialize the PDF parser.
        
        Args:
            detect_tables: Whether to detect and extract tables
            use_toc: Whether to use the document's table of contents when available
            detect_headings: Whether to detect headings based on font size/style
            min_heading_size: Minimum font size to consider as a heading
            heading_size_threshold: Ratio above normal text size to consider as heading
        """
        self.detect_tables = detect_tables
        self.use_toc = use_toc
        self.detect_headings = detect_headings
        self.min_heading_size = min_heading_size
        self.heading_size_threshold = heading_size_threshold
        
        self.doc_title = ""
        self.page_count = 0
        self.toc_available = False
        self.text_blocks_by_page = {}
        self.font_stats = {}
        self.heading_candidates = {}
        
        # Table detection parameters
        self.min_table_rows = 2
        self.min_table_cols = 2
        self.table_line_threshold = 3  # Minimum number of horizontal lines to detect a table
    
    def parse(self, 
              file_path: Union[str, os.PathLike], 
              extract_title: bool = True) -> Document:
        """
        Parse a PDF file and extract its structure.
        
        Args:
            file_path: Path to the PDF file
            extract_title: Whether to attempt to extract the document title
            
        Returns:
            Document: Structured representation of the PDF
            
        Raises:
            PDFInputError: If the PDF file is invalid
            PDFStructureError: If the structure cannot be properly parsed
        """
        logger.info(f"Parsing PDF: {file_path}")
        
        # Validate and open the PDF file
        pdf_doc = validate_pdf_file(file_path)
        self.page_count = pdf_doc.page_count
        
        # Extract document title if requested
        if extract_title:
            self.doc_title = self._extract_document_title(pdf_doc, os.path.basename(file_path))
        else:
            self.doc_title = os.path.basename(file_path)
        
        logger.info(f"Document title: {self.doc_title}, Pages: {self.page_count}")
        
        # Extract and analyze text blocks
        self._extract_text_blocks(pdf_doc)
        
        # Analyze font statistics to help with heading detection
        if self.detect_headings:
            self._analyze_font_statistics()
        
        # Create the document structure
        document = self._create_document_structure(pdf_doc)
        
        # Extract tables if requested
        if self.detect_tables:
            self._extract_tables(pdf_doc, document)
        
        # Close the PDF
        pdf_doc.close()
        
        logger.info(f"Successfully parsed PDF with {len(document.sections)} top-level sections")
        return document
    
    def _extract_document_title(self, pdf_doc: fitz.Document, fallback_name: str) -> str:
        """
        Extract the document title from metadata or first page.
        
        Args:
            pdf_doc: PyMuPDF document
            fallback_name: Fallback title if none can be extracted
            
        Returns:
            Document title
        """
        # Try to get title from metadata
        metadata = pdf_doc.metadata
        if metadata and metadata.get("title"):
            title = metadata.get("title").strip()
            if title:
                logger.debug(f"Title extracted from metadata: {title}")
                return title
        
        # Try to extract title from first page
        if pdf_doc.page_count > 0:
            first_page = pdf_doc[0]
            text = first_page.get_text("text")
            
            # Take the first non-empty line as the title
            for line in text.split("\n"):
                line = line.strip()
                if line:
                    # Limit title length
                    title = line[:100] + ("..." if len(line) > 100 else "")
                    logger.debug(f"Title extracted from first page: {title}")
                    return title
        
        # Use fallback if nothing else works
        logger.debug(f"Using fallback title: {fallback_name}")
        return fallback_name
    
    def _extract_text_blocks(self, pdf_doc: fitz.Document) -> None:
        """
        Extract text blocks from all pages in the document.
        
        Args:
            pdf_doc: PyMuPDF document
        """
        logger.info("Extracting text blocks from document")
        
        self.text_blocks_by_page = {}
        
        for page_num in range(self.page_count):
            page = pdf_doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            
            # Filter and sort text blocks
            text_blocks = []
            
            for block in blocks:
                if block["type"] == 0:  # Text block
                    # Extract text and position
                    block_text = ""
                    max_font_size = 0
                    is_bold = False
                    is_italic = False
                    
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_text = span.get("text", "").strip()
                            if not span_text:
                                continue
                                
                            font_size = span.get("size", 0)
                            font_flags = span.get("flags", 0)
                            
                            # Check for bold (bit 0) and italic (bit 1)
                            if font_flags & 1:
                                is_bold = True
                            if font_flags & 2:
                                is_italic = True
                            
                            # Keep track of max font size in block
                            max_font_size = max(max_font_size, font_size)
                            
                            block_text += span_text + " "
                    
                    block_text = block_text.strip()
                    
                    if block_text:
                        # Store the block with its attributes
                        text_blocks.append({
                            "text": block_text,
                            "bbox": block["bbox"],  # (x0, y0, x1, y1)
                            "font_size": max_font_size,
                            "is_bold": is_bold,
                            "is_italic": is_italic,
                            "page_num": page_num + 1  # 1-indexed page numbers
                        })
            
            # Sort blocks by position (top to bottom, left to right)
            text_blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
            
            self.text_blocks_by_page[page_num + 1] = text_blocks
            
            logger.debug(f"Page {page_num + 1}: {len(text_blocks)} text blocks extracted")
    
    def _analyze_font_statistics(self) -> None:
        """
        Analyze font statistics to help with heading detection.
        """
        logger.info("Analyzing font statistics for heading detection")
        
        # Collect font size statistics
        font_sizes = []
        font_size_text_length = defaultdict(int)
        bold_sizes = []
        
        for page_num, blocks in self.text_blocks_by_page.items():
            for block in blocks:
                font_size = block["font_size"]
                text_length = len(block["text"])
                
                font_sizes.append(font_size)
                font_size_text_length[font_size] += text_length
                
                if block["is_bold"]:
                    bold_sizes.append(font_size)
        
        if not font_sizes:
            logger.warning("No font information found in document")
            return
        
        # Calculate statistics
        # Find the most common font size by text length
        if font_size_text_length:
            normal_size = max(font_size_text_length.items(), key=lambda x: x[1])[0]
        else:
            # Fallback to median
            font_sizes.sort()
            normal_size = font_sizes[len(font_sizes) // 2] if font_sizes else 12.0
        
        # Calculate heading thresholds
        heading_threshold = max(self.min_heading_size, normal_size * self.heading_size_threshold)
        
        # Store statistics
        self.font_stats = {
            "normal_size": normal_size,
            "heading_threshold": heading_threshold,
            "sizes": Counter(font_sizes),
            "bold_sizes": Counter(bold_sizes)
        }
        
        logger.debug(f"Font stats: Normal size={normal_size:.1f}, Heading threshold={heading_threshold:.1f}")
        
        # Identify heading candidates
        self.heading_candidates = {}
        
        for page_num, blocks in self.text_blocks_by_page.items():
            page_headings = []
            
            for block in blocks:
                is_heading = False
                heading_level = 0
                
                font_size = block["font_size"]
                is_bold = block["is_bold"]
                text = block["text"]
                
                # Check if this block might be a heading
                if font_size >= heading_threshold:
                    is_heading = True
                    
                    # Determine heading level (higher font size = lower level)
                    if font_size >= heading_threshold * 1.5:
                        heading_level = 1  # H1
                    elif font_size >= heading_threshold * 1.25:
                        heading_level = 2  # H2
                    elif is_bold:
                        heading_level = 3  # H3
                    else:
                        heading_level = 4  # H4
                
                # Additional heuristics for heading detection
                
                # Check for numbered headings (e.g., "1. Introduction")
                if re.match(r"^\d+(\.\d+)*\.\s+\w+", text):
                    is_heading = True
                    
                    # Determine level by number of dots
                    dots = text.split(" ")[0].count(".")
                    heading_level = min(dots + 1, 5)
                
                # Check for short, bold text
                if is_bold and len(text) < 100 and text.strip():
                    is_heading = True
                    heading_level = heading_level or 3
                
                # Check for all caps (often used for headings)
                if text.isupper() and 3 < len(text) < 50:
                    is_heading = True
                    heading_level = heading_level or 3
                
                if is_heading:
                    page_headings.append({
                        "text": text,
                        "level": heading_level,
                        "bbox": block["bbox"],
                        "font_size": font_size,
                        "is_bold": is_bold
                    })
            
            if page_headings:
                self.heading_candidates[page_num] = page_headings
                logger.debug(f"Page {page_num}: {len(page_headings)} heading candidates")
    
    def _create_document_structure(self, pdf_doc: fitz.Document) -> Document:
        """
        Create the document structure based on TOC or detected headings.
        
        Args:
            pdf_doc: PyMuPDF document
            
        Returns:
            Document structure
        """
        # Create basic document structure
        document = Document(
            title=self.doc_title,
            pages=self.page_count,
            sections=[]
        )
        
        # Try to use table of contents if available and requested
        toc = None
        if self.use_toc:
            toc = pdf_doc.get_toc()
            if toc:
                logger.info(f"Using document's table of contents ({len(toc)} entries)")
                self.toc_available = True
                document = self._create_structure_from_toc(document, toc)
            else:
                logger.info("No table of contents found in document")
        
        # Fall back to heading detection if no TOC or TOC extraction failed
        if not self.toc_available and self.detect_headings and self.heading_candidates:
            logger.info("Creating document structure from detected headings")
            document = self._create_structure_from_headings(document)
        
        # If still no structure, create a simple page-based structure
        if not document.sections:
            logger.info("No document structure detected, creating page-based structure")
            document = self._create_simple_structure(document)
        
        return document
    
    def _create_structure_from_toc(self, document: Document, toc: List[List]) -> Document:
        """
        Create document structure from table of contents.
        
        Args:
            document: Document model
            toc: Table of contents as returned by PyMuPDF
            
        Returns:
            Updated document model
        """
        if not toc:
            return document
        
        # Create sections from TOC
        section_stack = []
        current_pages = [set() for _ in range(100)]  # More than enough levels
        
        for entry in toc:
            level, title, page = entry
            
            # Adjust level to be 1-based (TOC levels are 1-based in PyMuPDF)
            level = max(1, level)
            
            # Clean up the title
            title = title.strip()
            if not title:
                continue
            
            # Adjust page number (PyMuPDF uses 0-based indexing for 'page')
            page = max(1, page)
            
            logger.debug(f"TOC entry: Level {level}, Title '{title}', Page {page}")
            
            # Create a new section
            new_section = Section(
                title=title,
                level=level,
                pages=[page],  # Initially just the starting page
                content="",
                tables=[],
                subsections=[]
            )
            
            # Add pages to this section
            current_pages[level].add(page)
            
            # Determine where to add this section
            if level == 1:
                # This is a top-level section
                document.sections.append(new_section)
                section_stack = [new_section]
            else:
                # Find the correct parent section
                while len(section_stack) >= level:
                    section_stack.pop()
                
                if section_stack:
                    parent = section_stack[-1]
                    parent.subsections.append(new_section)
                else:
                    # If no parent found, add as top-level
                    document.sections.append(new_section)
                
                section_stack.append(new_section)
        
        # Determine page ranges for sections
        if document.sections:
            self._calculate_section_page_ranges(document.sections, document.pages)
        
        # Finally, populate the content of each section
        self._populate_section_content(document)
        
        return document
    
    def _create_structure_from_headings(self, document: Document) -> Document:
        """
        Create document structure from detected headings.
        
        Args:
            document: Document model
            
        Returns:
            Updated document model
        """
        # Collect all heading candidates across pages
        all_headings = []
        
        for page_num, headings in sorted(self.heading_candidates.items()):
            for heading in headings:
                all_headings.append({
                    "title": heading["text"],
                    "level": heading["level"],
                    "page": page_num,
                    "bbox": heading["bbox"]
                })
        
        if not all_headings:
            logger.warning("No headings detected in document")
            return document
        
        # Sort headings by page and position
        all_headings.sort(key=lambda h: (h["page"], h["bbox"][1]))
        
        # Create sections from headings
        section_stack = []
        
        for heading in all_headings:
            title = heading["title"]
            level = heading["level"]
            page = heading["page"]
            
            # Create a new section
            new_section = Section(
                title=title,
                level=level,
                pages=[page],  # Initially just the starting page
                content="",
                tables=[],
                subsections=[]
            )
            
            # Determine where to add this section
            if level == 1:
                # This is a top-level section
                document.sections.append(new_section)
                section_stack = [new_section]
            else:
                # Find the correct parent section
                while section_stack and section_stack[-1].level >= level:
                    section_stack.pop()
                
                if section_stack:
                    parent = section_stack[-1]
                    parent.subsections.append(new_section)
                else:
                    # If no parent found, add as top-level
                    document.sections.append(new_section)
                
                section_stack.append(new_section)
        
        # Determine page ranges for sections
        if document.sections:
            self._calculate_section_page_ranges(document.sections, document.pages)
        
        # Finally, populate the content of each section
        self._populate_section_content(document)
        
        return document
    
    def _create_simple_structure(self, document: Document) -> Document:
        """
        Create a simple page-based structure if no TOC or headings available.
        
        Args:
            document: Document model
            
        Returns:
            Updated document model
        """
        # Create one section per page
        for page_num in range(1, self.page_count + 1):
            title = f"Page {page_num}"
            
            # Create content string from text blocks
            content = ""
            for block in self.text_blocks_by_page.get(page_num, []):
                content += block["text"] + "\n\n"
            
            section = Section(
                title=title,
                level=1,
                pages=[page_num],
                content=content.strip(),
                tables=[],
                subsections=[]
            )
            
            document.sections.append(section)
        
        return document
    
    def _calculate_section_page_ranges(self, sections: List[Section], total_pages: int) -> None:
        """
        Calculate page ranges for sections.
        
        Args:
            sections: List of sections to process
            total_pages: Total number of pages in the document
        """
        # Sort sections by their starting page
        sections.sort(key=lambda s: min(s.pages) if s.pages else float('inf'))
        
        # Update page ranges for each section
        for i, section in enumerate(sections):
            start_page = min(section.pages)
            
            # End page is either the start of the next section or the end of the document
            if i < len(sections) - 1:
                next_start = min(sections[i + 1].pages)
                end_page = next_start - 1
            else:
                end_page = total_pages
            
            # Update pages list to include all pages in range
            section.pages = list(range(start_page, end_page + 1))
            
            # Recursively process subsections
            if section.subsections:
                self._calculate_section_page_ranges(section.subsections, total_pages)
                
                # Ensure subsection pages are within parent section pages
                section_pages = set(section.pages)
                all_subsection_pages = set()
                
                for subsection in section.subsections:
                    all_subsection_pages.update(subsection.pages)
                
                # Adjust parent section if needed
                if not all_subsection_pages.issubset(section_pages):
                    missing_pages = all_subsection_pages - section_pages
                    section.pages = sorted(list(section_pages.union(missing_pages)))
                    logger.warning(f"Adjusting section '{section.title}' to include all subsection pages")
    
    def _populate_section_content(self, document: Document) -> None:
        """
        Populate the content of each section from text blocks.
        
        Args:
            document: Document model to update
        """
        # Process all sections, including subsections
        all_sections = document.get_all_sections()
        
        for section in all_sections:
            content = []
            
            for page_num in section.pages:
                # Skip content that belongs to subsections
                subsection_ranges = []
                for subsection in section.subsections:
                    subsection_ranges.extend(subsection.pages)
                
                if page_num in subsection_ranges:
                    # Only include content from the start of the section to the first subsection
                    if page_num == min(section.pages):
                        # Include content up to the first heading on this page
                        heading_blocks = []
                        for heading in self.heading_candidates.get(page_num, []):
                            if heading["text"] != section.title:
                                heading_blocks.append(heading["bbox"][1])  # Y-position
                        
                        blocks = self.text_blocks_by_page.get(page_num, [])
                        for block in blocks:
                            # Skip the heading itself
                            if block["text"] == section.title:
                                continue
                            
                            # Include blocks before subsection headings
                            y_pos = block["bbox"][1]
                            if not heading_blocks or y_pos < min(heading_blocks):
                                content.append(block["text"])
                else:
                    # Include all content from this page
                    blocks = self.text_blocks_by_page.get(page_num, [])
                    for block in blocks:
                        # Skip the heading itself
                        if block["text"] == section.title:
                            continue
                        
                        content.append(block["text"])
            
            # Join content with appropriate spacing
            section.content = "\n\n".join(content).strip()
    
    def _extract_tables(self, pdf_doc: fitz.Document, document: Document) -> None:
        """
        Extract tables from the document and associate them with sections.
        
        Args:
            pdf_doc: PyMuPDF document
            document: Document model to update
        """
        logger.info("Extracting tables from document")
        
        # Get all sections, including subsections
        all_sections = document.get_all_sections()
        section_by_page = defaultdict(list)
        
        # Create a mapping of pages to sections
        for section in all_sections:
            for page_num in section.pages:
                section_by_page[page_num].append(section)
        
        # Process each page
        for page_num in range(1, self.page_count + 1):
            page = pdf_doc[page_num - 1]  # PyMuPDF uses 0-based indexing
            
            try:
                # Detect tables on the page
                tables = self._detect_tables(page, page_num)
                
                if tables:
                    logger.debug(f"Page {page_num}: {len(tables)} tables detected")
                    
                    # Assign tables to sections
                    sections = section_by_page.get(page_num, [])
                    if not sections:
                        logger.warning(f"No sections found for page {page_num}, tables will be lost")
                        continue
                    
                    # Assign each table to the most specific section
                    for table in tables:
                        # Find the section that contains this table's position
                        best_section = None
                        min_section_size = float('inf')
                        
                        for section in sections:
                            # Prefer sections with smaller page ranges (more specific)
                            if len(section.pages) < min_section_size:
                                best_section = section
                                min_section_size = len(section.pages)
                        
                        if best_section:
                            best_section.tables.append(table)
                        else:
                            logger.warning(f"Could not assign table on page {page_num}")
            
            except TableExtractionError as e:
                logger.warning(f"Error extracting tables from page {page_num}: {str(e)}")
                continue
    
    def _detect_tables(self, page: fitz.Page, page_num: int) -> List[Table]:
        """
        Detect tables on a page using geometric analysis.
        
        Args:
            page: PyMuPDF page
            page_num: Page number (1-based)
            
        Returns:
            List of detected tables
            
        Raises:
            TableExtractionError: If an error occurs during table detection
        """
        tables = []
        
        try:
            # Get all lines on the page
            lines = page.get_drawings()
            
            # Get horizontal and vertical lines
            h_lines = []
            v_lines = []
            
            for line in lines:
                if line["type"] == "l":  # Line
                    p1, p2 = line["pts"]
                    x0, y0 = p1
                    x1, y1 = p2
                    
                    # Determine if horizontal or vertical
                    if abs(y1 - y0) < 2:  # Horizontal line
                        h_lines.append((min(x0, x1), y0, max(x0, x1), y1))
                    elif abs(x1 - x0) < 2:  # Vertical line
                        v_lines.append((x0, min(y0, y1), x1, max(y0, y1)))
            
            # If we have enough horizontal lines, we might have a table
            if len(h_lines) >= self.min_table_rows:
                # Group horizontal lines with similar y-coordinates
                h_groups = self._group_lines_by_position(h_lines, axis=1, tolerance=5)
                
                # Group vertical lines with similar x-coordinates
                v_groups = self._group_lines_by_position(v_lines, axis=0, tolerance=5)
                
                # If we have enough groups, this might be a table
                if len(h_groups) >= self.min_table_rows and len(v_groups) >= self.min_table_cols:
                    # Extract the table
                    for idx, (h_group, v_group) in enumerate(self._find_table_candidates(h_groups, v_groups)):
                        if len(h_group) < self.min_table_rows or len(v_group) < self.min_table_cols:
                            continue
                        
                        # Get table bounds
                        x0 = min(line[0] for line in v_group)
                        y0 = min(line[1] for line in h_group)
                        x1 = max(line[2] for line in v_group)
                        y1 = max(line[3] for line in h_group)
                        
                        # Extract table data
                        table_data = self._extract_table_data(
                            page, 
                            h_group, 
                            v_group, 
                            (x0, y0, x1, y1)
                        )
                        
                        if table_data and len(table_data) >= self.min_table_rows and len(table_data[0]) >= self.min_table_cols:
                            # Create table model
                            table = Table(
                                caption=f"Table on page {page_num}",
                                page=page_num,
                                position=(x0, y0, x1, y1),
                                data=table_data
                            )
                            
                            tables.append(table)
            
            return tables
        
        except Exception as e:
            raise TableExtractionError(f"Error detecting tables: {str(e)}")
    
    def _group_lines_by_position(self, lines, axis=0, tolerance=5):
        """
        Group lines that have similar positions along the specified axis.
        
        Args:
            lines: List of lines (x0, y0, x1, y1)
            axis: Axis to group by (0 for x, 1 for y)
            tolerance: Maximum distance to consider lines as part of the same group
            
        Returns:
            List of groups, each group being a list of lines
        """
        if not lines:
            return []
        
        # Sort lines by position
        sorted_lines = sorted(lines, key=lambda line: line[axis])
        
        groups = []
        current_group = [sorted_lines[0]]
        
        for line in sorted_lines[1:]:
            # Check if this line is close to the previous group
            prev_pos = current_group[-1][axis]
            curr_pos = line[axis]
            
            if abs(curr_pos - prev_pos) <= tolerance:
                # Add to current group
                current_group.append(line)
            else:
                # Start a new group
                groups.append(current_group)
                current_group = [line]
        
        # Add the last group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _find_table_candidates(self, h_groups, v_groups):
        """
        Find potential tables based on intersecting horizontal and vertical line groups.
        
        Args:
            h_groups: Groups of horizontal lines
            v_groups: Groups of vertical lines
            
        Returns:
            List of tuples (h_lines, v_lines) representing table candidates
        """
        if not h_groups or not v_groups:
            return []
        
        candidates = []
        
        # Check each combination of horizontal and vertical groups
        for h_group in h_groups:
            for v_group in v_groups:
                # Check if these groups intersect
                h_range = (min(line[0] for line in h_group), max(line[2] for line in h_group))
                v_range = (min(line[1] for line in v_group), max(line[3] for line in v_group))
                
                h_span = h_range[1] - h_range[0]
                v_span = v_range[1] - v_range[0]
                
                # Ensure the groups form a rectangular area
                if h_span > 0 and v_span > 0:
                    # Check if there are enough intersections
                    intersections = 0
                    
                    for h_line in h_group:
                        for v_line in v_group:
                            if (h_line[0] <= v_line[0] <= h_line[2] and 
                                v_line[1] <= h_line[1] <= v_line[3]):
                                intersections += 1
                    
                    # If enough intersections, consider this a table candidate
                    if intersections >= min(len(h_group), len(v_group)):
                        candidates.append((h_group, v_group))
        
        return candidates
    
    def _extract_table_data(self, page, h_lines, v_lines, table_bounds):
        """
        Extract table data from the given bounds.
        
        Args:
            page: PyMuPDF page
            h_lines: Horizontal lines defining rows
            v_lines: Vertical lines defining columns
            table_bounds: Table boundaries (x0, y0, x1, y1)
            
        Returns:
            List of rows, each row being a list of cell values
        """
        # Sort lines to determine row and column boundaries
        h_positions = sorted(set(line[1] for line in h_lines))
        v_positions = sorted(set(line[0] for line in v_lines))
        
        if len(h_positions) < 2 or len(v_positions) < 2:
            return []
        
        # Create cells
        rows = []
        
        for i in range(len(h_positions) - 1):
            row = []
            for j in range(len(v_positions) - 1):
                # Cell bounds
                cell_x0 = v_positions[j]
                cell_y0 = h_positions[i]
                cell_x1 = v_positions[j + 1]
                cell_y1 = h_positions[i + 1]
                
                # Extract text from this cell
                cell_text = page.get_text("text", clip=(cell_x0, cell_y0, cell_x1, cell_y1))
                cell_text = cell_text.strip()
                
                row.append(cell_text)
            
            if any(cell for cell in row):  # Skip empty rows
                rows.append(row)
        
        return rows