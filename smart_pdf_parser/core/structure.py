"""
Document structure detection for PDF documents.

This module provides functions for detecting and extracting the
logical structure of PDF documents, including TOC extraction and
heading detection based on visual attributes.
"""

import fitz  # PyMuPDF
import re
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional, Set, Union
import logging

from ..models.document import Section
from ..utils.exceptions import PDFStructureError, PDFTOCError
from ..utils.logger import get_logger

logger = get_logger(__name__)

class StructureDetector:
    """
    Class for detecting and extracting document structure from PDFs.
    """
    
    def __init__(self, 
                 use_toc: bool = True,
                 detect_headings: bool = True,
                 min_heading_size: float = 12.0,
                 heading_size_threshold: float = 1.2):
        """
        Initialize the structure detector.
        
        Args:
            use_toc: Whether to use the document's table of contents when available
            detect_headings: Whether to detect headings based on font size/style
            min_heading_size: Minimum font size to consider as a heading
            heading_size_threshold: Ratio above normal text size to consider as heading
        """
        self.use_toc = use_toc
        self.detect_headings = detect_headings
        self.min_heading_size = min_heading_size
        self.heading_size_threshold = heading_size_threshold
        
        # Additional parameters for heading detection
        self.min_heading_length = 2      # Minimum length of heading text
        self.max_heading_length = 200    # Maximum length of heading text
        self.heading_patterns = [        # Regex patterns for common heading formats
            r"^\s*(?:chapter|section|part)\s+\d+[\.:]\s+.+",  # "Chapter 1: Introduction"
            r"^\s*\d+(?:\.\d+)*\s+.+",                       # "1.2.3 Methods"
            r"^\s*[A-Z](?:\.\d+)*\s+.+",                     # "A.1 Appendix"
            r"^\s*[IVXLCDM]+\.\s+.+",                        # "IV. Results"
            r"^\s*Appendix\s+[A-Z]\s*:?\s+.+"                # "Appendix A: Data"
        ]
    
    def extract_toc(self, pdf_doc: fitz.Document) -> List[List]:
        """
        Extract table of contents from PDF document.
        
        Args:
            pdf_doc: PyMuPDF document
            
        Returns:
            List of TOC entries, each being [level, title, page]
            
        Raises:
            PDFTOCError: If TOC extraction fails
        """
        try:
            toc = pdf_doc.get_toc()
            
            if not toc:
                logger.info("No table of contents found in document")
                return []
            
            logger.info(f"Extracted TOC with {len(toc)} entries")
            
            # Validate and normalize TOC entries
            validated_toc = []
            
            for entry in toc:
                if len(entry) != 3:
                    logger.warning(f"Invalid TOC entry format: {entry}")
                    continue
                
                level, title, page = entry
                
                # Validate level
                if not isinstance(level, int) or level < 1:
                    logger.warning(f"Invalid TOC level: {level}")
                    level = 1
                
                # Validate title
                if not isinstance(title, str) or not title.strip():
                    logger.warning(f"Invalid TOC title: {title}")
                    continue
                
                # Validate page
                if not isinstance(page, int) or page < 1:
                    logger.warning(f"Invalid TOC page: {page}")
                    continue
                
                # Normalize title
                title = title.strip()
                
                validated_toc.append([level, title, page])
            
            return validated_toc
        
        except Exception as e:
            raise PDFTOCError(f"Failed to extract TOC: {str(e)}")
    
    def create_structure_from_toc(self, toc: List[List], total_pages: int) -> List[Section]:
        """
        Create document structure from table of contents.
        
        Args:
            toc: Table of contents entries [level, title, page]
            total_pages: Total number of pages in the document
            
        Returns:
            List of top-level sections
        """
        if not toc:
            return []
        
        # Create sections from TOC
        top_level_sections = []
        section_stack = []
        
        for entry in toc:
            level, title, page = entry
            
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
                top_level_sections.append(new_section)
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
                    top_level_sections.append(new_section)
                
                section_stack.append(new_section)
        
        # Calculate page ranges for all sections
        self._calculate_section_page_ranges(top_level_sections, total_pages)
        
        return top_level_sections
    
    def detect_headings_in_text_blocks(self, 
                                       text_blocks_by_page: Dict[int, List[Dict[str, Any]]]) -> Dict[int, List[Dict[str, Any]]]:
        """
        Detect headings in text blocks based on font size and style.
        
        Args:
            text_blocks_by_page: Dictionary mapping page numbers to lists of text blocks
            
        Returns:
            Dictionary mapping page numbers to lists of heading blocks
        """
        logger.info("Detecting headings in text blocks")
        
        # Step 1: Analyze font statistics
        font_stats = self._analyze_font_statistics(text_blocks_by_page)
        
        if not font_stats:
            logger.warning("No font statistics available for heading detection")
            return {}
        
        normal_size = font_stats.get("normal_size", 12.0)
        heading_threshold = max(self.min_heading_size, normal_size * self.heading_size_threshold)
        
        logger.debug(f"Font statistics: normal_size={normal_size:.1f}, heading_threshold={heading_threshold:.1f}")
        
        # Step 2: Identify heading candidates
        heading_candidates = {}
        
        for page_num, blocks in text_blocks_by_page.items():
            page_headings = []
            
            for block in blocks:
                if self._is_heading(block, heading_threshold):
                    heading_level = self._determine_heading_level(block, heading_threshold)
                    
                    # Store the heading
                    heading = {
                        "text": block["text"],
                        "level": heading_level,
                        "bbox": block["bbox"],
                        "font_size": block["font_size"],
                        "is_bold": block.get("is_bold", False)
                    }
                    
                    page_headings.append(heading)
            
            if page_headings:
                heading_candidates[page_num] = page_headings
                logger.debug(f"Page {page_num}: {len(page_headings)} heading candidates")
        
        return heading_candidates
    
    def create_structure_from_headings(self, 
                                      heading_candidates: Dict[int, List[Dict[str, Any]]], 
                                      total_pages: int) -> List[Section]:
        """
        Create document structure from detected headings.
        
        Args:
            heading_candidates: Dictionary mapping page numbers to lists of heading blocks
            total_pages: Total number of pages in the document
            
        Returns:
            List of top-level sections
        """
        if not heading_candidates:
            return []
        
        # Collect all heading candidates across pages
        all_headings = []
        
        for page_num, headings in sorted(heading_candidates.items()):
            for heading in headings:
                all_headings.append({
                    "title": heading["text"],
                    "level": heading["level"],
                    "page": page_num,
                    "bbox": heading["bbox"]
                })
        
        # Sort headings by page and position
        all_headings.sort(key=lambda h: (h["page"], h["bbox"][1]))
        
        # Create sections from headings
        top_level_sections = []
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
                top_level_sections.append(new_section)
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
                    top_level_sections.append(new_section)
                
                section_stack.append(new_section)
        
        # Calculate page ranges for all sections
        self._calculate_section_page_ranges(top_level_sections, total_pages)
        
        return top_level_sections
    
    def _analyze_font_statistics(self, text_blocks_by_page: Dict[int, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Analyze font statistics to help with heading detection.
        
        Args:
            text_blocks_by_page: Dictionary mapping page numbers to lists of text blocks
            
        Returns:
            Dictionary of font statistics
        """
        # Collect font size statistics
        font_sizes = []
        font_size_text_length = defaultdict(int)
        bold_sizes = []
        
        for page_num, blocks in text_blocks_by_page.items():
            for block in blocks:
                font_size = block.get("font_size", 0)
                is_bold = block.get("is_bold", False)
                text = block.get("text", "")
                
                if font_size <= 0 or not text:
                    continue
                
                font_sizes.append(font_size)
                font_size_text_length[font_size] += len(text)
                
                if is_bold:
                    bold_sizes.append(font_size)
        
        if not font_sizes:
            logger.warning("No font information found in document")
            return {}
        
        # Calculate statistics
        # Find the most common font size by text length
        if font_size_text_length:
            normal_size = max(font_size_text_length.items(), key=lambda x: x[1])[0]
        else:
            # Fallback to median
            font_sizes.sort()
            normal_size = font_sizes[len(font_sizes) // 2] if font_sizes else 12.0
        
        # Store statistics
        font_stats = {
            "normal_size": normal_size,
            "sizes": sorted(set(font_sizes)),
            "bold_sizes": sorted(set(bold_sizes))
        }
        
        return font_stats
    
    def _is_heading(self, block: Dict[str, Any], heading_threshold: float) -> bool:
        """
        Determine if a text block is a heading.
        
        Args:
            block: Text block
            heading_threshold: Font size threshold for headings
            
        Returns:
            True if the block is likely a heading, False otherwise
        """
        text = block.get("text", "").strip()
        font_size = block.get("font_size", 0)
        is_bold = block.get("is_bold", False)
        
        # Skip if text is empty or too short
        if not text or len(text) < self.min_heading_length:
            return False
        
        # Skip if text is too long
        if len(text) > self.max_heading_length:
            return False
        
        # Check font size
        if font_size >= heading_threshold:
            return True
        
        # Check if bold and reasonably large
        if is_bold and font_size >= heading_threshold * 0.8:
            return True
        
        # Check for all-caps (often used for headings)
        if text.isupper() and 3 < len(text) < 50:
            return True
        
        # Check for common heading patterns
        text_lower = text.lower()
        for pattern in self.heading_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _determine_heading_level(self, block: Dict[str, Any], heading_threshold: float) -> int:
        """
        Determine the heading level of a text block.
        
        Args:
            block: Text block
            heading_threshold: Font size threshold for headings
            
        Returns:
            Heading level (1 for top-level, 2 for subsection, etc.)
        """
        text = block.get("text", "").strip()
        font_size = block.get("font_size", 0)
        is_bold = block.get("is_bold", False)
        
        # Determine level based on font size
        if font_size >= heading_threshold * 1.5:
            level = 1  # H1
        elif font_size >= heading_threshold * 1.25:
            level = 2  # H2
        elif font_size >= heading_threshold:
            level = 3  # H3
        elif is_bold:
            level = 4  # H4
        else:
            level = 5  # H5
        
        # Check for numbered headings
        match = re.match(r"^\s*(\d+)(?:\.(\d+))*(?:\.\s|\s)", text)
        if match:
            # Count number of segments to determine level
            segments = match.group(0).count(".") + 1
            level = min(segments, 5)  # Cap at level 5
        
        # Check for appendix-style headings
        if text.lower().startswith("appendix"):
            level = 1
        
        return level
    
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