"""
Content organization functionality for PDF documents.

This module handles the organization and extraction of textual content from PDF documents,
ensuring proper ordering and association with the document structure.
"""

import fitz  # PyMuPDF
from typing import Dict, List, Any, Tuple, Optional, Set
import logging
from collections import defaultdict

from ..utils.logger import get_logger
from ..models.document import Section

logger = get_logger(__name__)

class ContentOrganizer:
    """
    Class for organizing and extracting content from PDF documents,
    ensuring proper association with the document structure.
    """
    
    def __init__(self):
        """Initialize the content organizer."""
        self.text_blocks_by_page = {}
    
    def extract_text_blocks(self, pdf_doc: fitz.Document) -> Dict[int, List[Dict[str, Any]]]:
        """
        Extract text blocks from all pages in the document.
        
        Args:
            pdf_doc: PyMuPDF document
            
        Returns:
            Dictionary mapping page numbers to lists of text blocks
        """
        logger.info("Extracting text blocks from document")
        
        text_blocks_by_page = {}
        
        for page_num in range(pdf_doc.page_count):
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
            
            text_blocks_by_page[page_num + 1] = text_blocks
            
            logger.debug(f"Page {page_num + 1}: {len(text_blocks)} text blocks extracted")
        
        self.text_blocks_by_page = text_blocks_by_page
        return text_blocks_by_page
    
    def populate_section_content(self, 
                                document_sections: List[Section], 
                                heading_candidates: Dict[int, List[Dict[str, Any]]] = None) -> None:
        """
        Populate the content of each section from text blocks.
        
        Args:
            document_sections: List of top-level sections
            heading_candidates: Dictionary mapping page numbers to lists of heading candidates
        """
        logger.info("Populating section content")
        
        # Get a flattened list of all sections
        sections = self._get_all_sections(document_sections)
        
        # Create a mapping of pages to sections
        section_by_page = defaultdict(list)
        for section in sections:
            for page_num in section.pages:
                section_by_page[page_num].append(section)
        
        # Create a mapping of headings to skip
        section_titles = {section.title for section in sections}
        
        # Process each page
        for page_num, blocks in self.text_blocks_by_page.items():
            # Find sections that include this page
            page_sections = section_by_page.get(page_num, [])
            if not page_sections:
                continue
            
            # Find headings on this page
            page_headings = []
            if heading_candidates:
                page_headings = [h["text"] for h in heading_candidates.get(page_num, [])]
            
            # Assign blocks to sections
            for block in blocks:
                block_text = block["text"]
                
                # Skip blocks that are section headings
                if block_text in section_titles:
                    continue
                
                # Find the most specific section for this block
                target_section = self._find_best_section_for_block(
                    block, page_sections, page_headings
                )
                
                if target_section:
                    # Add content to section
                    if target_section.content:
                        target_section.content += "\n\n" + block_text
                    else:
                        target_section.content = block_text
    
    def _get_all_sections(self, sections: List[Section]) -> List[Section]:
        """
        Get a flattened list of all sections, including subsections.
        
        Args:
            sections: List of top-level sections
            
        Returns:
            Flattened list of all sections
        """
        result = []
        
        def collect_sections(section_list, acc):
            for section in section_list:
                acc.append(section)
                collect_sections(section.subsections, acc)
        
        collect_sections(sections, result)
        return result
    
    def _find_best_section_for_block(self, 
                                    block: Dict[str, Any], 
                                    page_sections: List[Section],
                                    page_headings: List[str]) -> Optional[Section]:
        """
        Find the most specific section that should contain this text block.
        
        Args:
            block: Text block
            page_sections: Sections that include this page
            page_headings: Headings on this page
            
        Returns:
            Best section for this block, or None if no suitable section found
        """
        if not page_sections:
            return None
        
        block_text = block["text"]
        block_y = block["bbox"][1]  # Y-coordinate of the top of the block
        
        # Skip if the block is a heading
        if block_text in page_headings:
            return None
        
        # Sort sections by specificity (more specific sections have fewer pages)
        sorted_sections = sorted(page_sections, key=lambda s: (len(s.pages), -s.level))
        
        # Default to the most specific section
        best_section = sorted_sections[0]
        
        # If this is the only section, use it
        if len(sorted_sections) == 1:
            return best_section
        
        # Otherwise, try to find a more precise match based on position
        # This logic might need adjustment based on specific document layouts
        
        return best_section
    
    def extract_document_title(self, pdf_doc: fitz.Document, fallback_name: str) -> str:
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